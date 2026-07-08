"""Core logic for ComfyUI_EU_AI_Label — pure Pillow/stdlib, no ComfyUI imports.

Covers: visible-label compositing, XMP packet build/embed (PNG/JPEG/WebP),
and metadata extraction (XMP, EXIF, IPTC-IIM, C2PA detection).
Kept ComfyUI-free so tests can run headless.
"""

import json
import os
import re
import struct
import xml.etree.ElementTree as ET
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_PATH = os.path.join(ASSETS, "fonts", "DejaVuSans.ttf")

LANCZOS = getattr(Image, "Resampling", Image).LANCZOS

# ---------------------------------------------------------------- visible label

ICON_FILES = {
    "AI": "ai_{color}.png",
    "AI generated": "ai_generated_{color}.png",
    "AI modified": "ai_modified_{color}.png",
}

POSITIONS = [
    "top left", "top center", "top right",
    "middle left", "center", "middle right",
    "bottom left", "bottom center", "bottom right",
]


def load_icon(variant: str, color: str) -> Image.Image:
    path = os.path.join(ASSETS, "icons", ICON_FILES[variant].format(color=color))
    return Image.open(path).convert("RGBA")


def render_text(text: str, color: str, font_size: int = 200) -> Image.Image:
    """Render text tightly cropped, with a thin contrast outline for readability."""
    font = ImageFont.truetype(FONT_PATH, font_size)
    fill = (0, 0, 0, 255) if color == "black" else (255, 255, 255, 255)
    stroke = (255, 255, 255, 180) if color == "black" else (0, 0, 0, 180)
    stroke_w = max(2, font_size // 40)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=stroke_w)
    img = Image.new("RGBA", (r - l + 2 * stroke_w, b - t + 2 * stroke_w), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((stroke_w - l, stroke_w - t), text, font=font,
                             fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
    return img


def build_label(label_type: str, icon_variant: str, color: str,
                custom_text: str, custom_logo: Image.Image = None) -> Image.Image:
    """Compose the label artwork as RGBA (unscaled; apply_label scales it)."""
    if label_type == "EU Icon":
        return load_icon(icon_variant, color)
    if label_type == "Text":
        return render_text(custom_text or "KI-generiert", color)
    if label_type == "Text + EU Icon":
        icon = load_icon(icon_variant, color)
        h = 240
        icon = icon.resize((round(icon.width * h / icon.height), h), LANCZOS)
        text = render_text(custom_text or "KI-generiert", color, font_size=140)
        gap = h // 4
        out = Image.new("RGBA", (icon.width + gap + text.width, h), (0, 0, 0, 0))
        out.alpha_composite(icon, (0, 0))
        out.alpha_composite(text, (icon.width + gap, (h - text.height) // 2))
        return out
    if label_type == "Custom Logo":
        if custom_logo is None:
            raise ValueError("label_type 'Custom Logo' requires the custom_logo input")
        return custom_logo.convert("RGBA")
    raise ValueError(f"unknown label_type: {label_type}")


def apply_label(img: Image.Image, label: Image.Image, size_pct: float,
                margin_pct: float, opacity_pct: float, position: str) -> Image.Image:
    """Composite label onto img. size/margin are % of image width."""
    W, H = img.size
    target_w = max(1, min(W, round(W * size_pct / 100.0)))
    target_h = max(1, round(label.height * target_w / label.width))
    label = label.resize((target_w, target_h), LANCZOS)

    if opacity_pct < 100:
        alpha = label.getchannel("A").point(lambda a: round(a * opacity_pct / 100.0))
        label.putalpha(alpha)

    m = round(W * margin_pct / 100.0)
    xs = {"left": m, "center": (W - target_w) // 2, "right": W - target_w - m}
    ys = {"top": m, "middle": (H - target_h) // 2, "bottom": H - target_h - m}
    y_key, x_key = ("middle", "center") if position == "center" else position.split()
    x = max(0, min(W - target_w, xs[x_key]))
    y = max(0, min(H - target_h, ys[y_key]))

    out = img.convert("RGBA")
    out.alpha_composite(label, (x, y))
    return out.convert("RGB")


# ---------------------------------------------------------------- XMP writing

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
    "euai": "https://github.com/a-und-b/ComfyUI_EU_AI_Label/ns/1.0/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "x": "adobe:ns:meta/",
}

DIGITAL_SOURCE_TYPES = {
    "trainedAlgorithmicMedia":
        "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia":
        "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia",
    "algorithmicMedia":
        "http://cv.iptc.org/newscodes/digitalsourcetype/algorithmicMedia",
}

DST_LABELS = {
    "trainedAlgorithmicMedia": "fully AI-generated (trained algorithmic media)",
    "compositeWithTrainedAlgorithmicMedia": "AI-edited / composite with AI-generated content",
    "algorithmicMedia": "algorithmically generated (no AI training data)",
}


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def parse_custom_fields(text: str) -> dict:
    """'prefix:key=value' or 'key=value' per line -> {qualified_key: value}."""
    fields = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if ":" not in key or key.split(":", 1)[0] not in NS:
            key = "euai:" + re.sub(r"[^\w.-]", "_", key.replace(":", "_"))
        fields[key] = value.strip()
    return fields


def build_xmp(digital_source_type: str = "none", description: str = "",
              creator_tool: str = "", credit: str = "", custom_fields: dict = None) -> str:
    props = []
    if digital_source_type in DIGITAL_SOURCE_TYPES:
        props.append("   <Iptc4xmpExt:DigitalSourceType>%s</Iptc4xmpExt:DigitalSourceType>"
                     % DIGITAL_SOURCE_TYPES[digital_source_type])
    if creator_tool:
        props.append("   <xmp:CreatorTool>%s</xmp:CreatorTool>" % _esc(creator_tool))
    if credit:
        props.append("   <photoshop:Credit>%s</photoshop:Credit>" % _esc(credit))
    if description:
        props.append(
            "   <dc:description><rdf:Alt>"
            '<rdf:li xml:lang="x-default">%s</rdf:li>'
            "</rdf:Alt></dc:description>" % _esc(description))
    for key, value in (custom_fields or {}).items():
        props.append("   <%s>%s</%s>" % (key, _esc(value), key))

    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf="%(rdf)s">\n'
        '  <rdf:Description rdf:about=""\n'
        '    xmlns:dc="%(dc)s"\n'
        '    xmlns:xmp="%(xmp)s"\n'
        '    xmlns:photoshop="%(photoshop)s"\n'
        '    xmlns:Iptc4xmpExt="%(Iptc4xmpExt)s"\n'
        '    xmlns:euai="%(euai)s">\n'
        "%(props)s\n"
        "  </rdf:Description>\n"
        " </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>' % {**NS, "props": "\n".join(props)}
    )


def _inject_jpeg_xmp(jpeg: bytes, xmp: str) -> bytes:
    """Insert an XMP APP1 segment after SOI + any leading APP0/APP1 segments."""
    payload = b"http://ns.adobe.com/xap/1.0/\x00" + xmp.encode("utf-8")
    if len(payload) + 2 > 0xFFFF:
        raise ValueError("XMP packet too large for a single JPEG APP1 segment")
    seg = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    pos = 2
    while (pos + 4 <= len(jpeg) and jpeg[pos] == 0xFF
           and jpeg[pos + 1] in (0xE0, 0xE1)):
        pos += 2 + struct.unpack(">H", jpeg[pos + 2:pos + 4])[0]
    return jpeg[:pos] + seg + jpeg[pos:]


def save_with_metadata(img: Image.Image, path: str, fmt: str, xmp: str,
                       quality: int = 92, prompt_json: str = None,
                       workflow_json: str = None) -> None:
    """Save img with embedded XMP; optionally embed ComfyUI prompt/workflow.

    PNG: XMP as iTXt 'XML:com.adobe.xmp', workflow as tEXt (SaveImage-compatible).
    JPEG: XMP as APP1 segment, workflow in EXIF Make/Model (ComfyUI convention).
    WebP: XMP chunk via Pillow, workflow in EXIF (readable by ComfyUI drag&drop).
    """
    fmt = fmt.upper()
    if fmt == "PNG":
        info = PngInfo()
        if prompt_json:
            info.add_text("prompt", prompt_json)
        if workflow_json:
            info.add_text("workflow", workflow_json)
        info.add_itxt("XML:com.adobe.xmp", xmp, "", "")
        img.save(path, format="PNG", pnginfo=info, compress_level=4)
        return

    exif = Image.Exif()
    if workflow_json:
        exif[0x010F] = "workflow:" + workflow_json  # Make
    if prompt_json:
        exif[0x0110] = "prompt:" + prompt_json      # Model

    if fmt == "JPEG":
        buf = BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=quality,
                                exif=exif.tobytes() if len(exif) else None)
        with open(path, "wb") as f:
            f.write(_inject_jpeg_xmp(buf.getvalue(), xmp))
        return

    if fmt == "WEBP":
        kwargs = {"quality": quality, "xmp": xmp.encode("utf-8")}
        if len(exif):
            kwargs["exif"] = exif.tobytes()
        img.save(path, format="WEBP", **kwargs)
        return

    raise ValueError(f"unsupported format: {fmt}")


# ---------------------------------------------------------------- reading back

_RDF_DESC = "{%s}Description" % NS["rdf"]
_URI2PREFIX = {uri: p for p, uri in NS.items()}


def extract_xmp(data: bytes) -> str:
    """Find the raw XMP packet in a file, format-independent."""
    start = data.find(b"<x:xmpmeta")
    if start == -1:
        return ""
    end = data.find(b"</x:xmpmeta>", start)
    if end == -1:
        return ""
    return data[start:end + len(b"</x:xmpmeta>")].decode("utf-8", errors="replace")


def _localname(tag: str):
    if tag.startswith("{"):
        uri, local = tag[1:].split("}", 1)
        return _URI2PREFIX.get(uri, uri) + ":" + local
    return tag


def parse_xmp(xmp: str) -> dict:
    """Flatten rdf:Description properties (element and attribute form) to a dict."""
    fields = {}
    try:
        root = ET.fromstring(xmp)
    except ET.ParseError:
        return fields
    for desc in root.iter(_RDF_DESC):
        for k, v in desc.attrib.items():
            if not k.startswith("{%s}" % NS["rdf"]):
                fields[_localname(k)] = v
        for child in desc:
            key = _localname(child.tag)
            lis = [li.text or "" for li in child.iter()
                   if li.tag.endswith("}li") and li.text]
            text = "; ".join(lis) if lis else (child.text or "").strip()
            if text:
                fields[key] = text
    return fields


def read_exif(img: Image.Image) -> dict:
    from PIL.ExifTags import TAGS
    out = {}
    try:
        exif = img.getexif()
        items = list(exif.items())
        try:
            items += list(exif.get_ifd(0x8769).items())  # ExifIFD
        except Exception:
            pass
        for tag, value in items:
            name = TAGS.get(tag, hex(tag))
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            value = str(value)
            out[name] = value if len(value) <= 400 else value[:400] + "…"
    except Exception:
        pass
    return out


IPTC_NAMES = {
    (2, 5): "ObjectName", (2, 25): "Keywords", (2, 40): "SpecialInstructions",
    (2, 80): "By-line", (2, 105): "Headline", (2, 110): "Credit",
    (2, 115): "Source", (2, 116): "CopyrightNotice", (2, 120): "Caption",
}


def read_iptc(img: Image.Image) -> dict:
    from PIL import IptcImagePlugin
    out = {}
    try:
        info = IptcImagePlugin.getiptcinfo(img) or {}
        for key, value in info.items():
            name = IPTC_NAMES.get(key, str(key))
            if isinstance(value, list):
                value = b"; ".join(v if isinstance(v, bytes) else bytes(v) for v in value)
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            out[name] = str(value)
    except Exception:
        pass
    return out


def detect_c2pa(data: bytes) -> dict:
    """Detect (not verify) an embedded C2PA/JUMBF manifest."""
    found, where = False, []
    if data[:2] == b"\xff\xd8":  # JPEG: APP11 JUMBF segments
        pos = 2
        while pos + 4 <= len(data) and data[pos] == 0xFF and 0xE0 <= data[pos + 1] <= 0xEF:
            seglen = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            if data[pos + 1] == 0xEB and b"jumb" in data[pos + 4:pos + 4 + seglen]:
                found = True
                where.append("JPEG APP11 (JUMBF)")
                break
            pos += 2 + seglen
    elif data[:8] == b"\x89PNG\r\n\x1a\n":  # PNG: caBX chunk
        pos = 8
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            if ctype == b"caBX":
                found = True
                where.append("PNG caBX chunk")
                break
            pos += 12 + length
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WebP: C2PA chunk
        pos = 12
        while pos + 8 <= len(data):
            ctype = data[pos:pos + 4]
            length = struct.unpack("<I", data[pos + 4:pos + 8])[0]
            if ctype in (b"C2PA", b"JUMB"):
                found = True
                where.append("WebP %s chunk" % ctype.decode())
                break
            pos += 8 + length + (length % 2)
    if not found and (b"urn:c2pa" in data or b"c2pa.assertions" in data):
        found = True
        where.append("c2pa marker in file data (unstructured match)")
    return {"present": found, "location": where}


def inspect_file(path: str) -> dict:
    """Full metadata inspection -> dict (see build_report for the human version)."""
    with open(path, "rb") as f:
        data = f.read()
    img = Image.open(BytesIO(data))
    xmp_raw = extract_xmp(data)
    xmp_fields = parse_xmp(xmp_raw) if xmp_raw else {}

    dst_value = xmp_fields.get("Iptc4xmpExt:DigitalSourceType", "")
    dst_key = dst_value.rstrip("/").rsplit("/", 1)[-1] if dst_value else ""

    result = {
        "file": os.path.abspath(path),
        "format": img.format,
        "size": list(img.size),
        "xmp_present": bool(xmp_raw),
        "xmp": xmp_fields,
        "digital_source_type": dst_key,
        "digital_source_type_uri": dst_value,
        "exif": read_exif(img),
        "iptc": read_iptc(img),
        "c2pa": detect_c2pa(data),
        "comfyui_workflow_embedded": False,
    }

    if img.format == "PNG":
        text_chunks = getattr(img, "text", {}) or {}
        result["comfyui_workflow_embedded"] = "workflow" in text_chunks or "prompt" in text_chunks
    else:
        exif = result["exif"]
        result["comfyui_workflow_embedded"] = any(
            str(v).startswith(("workflow:", "prompt:")) for v in exif.values())

    ai_marked = bool(dst_key in DST_LABELS) or result["c2pa"]["present"]
    result["ai_labeling_found"] = ai_marked
    return result


def build_report(r: dict) -> str:
    lines = [
        "EU AI Label — Metadata Check",
        "=" * 60,
        f"File:   {r['file']}",
        f"Format: {r['format']}  ({r['size'][0]}x{r['size'][1]})",
        "",
        "AI labeling found: %s" % ("YES" if r["ai_labeling_found"] else "NO"),
    ]
    if r["digital_source_type"]:
        label = DST_LABELS.get(r["digital_source_type"], r["digital_source_type"])
        lines.append(f"  DigitalSourceType: {r['digital_source_type']} — {label}")
    if r["c2pa"]["present"]:
        lines.append("  C2PA manifest detected: " + "; ".join(r["c2pa"]["location"])
                     + " (detection only, signature not verified)")
    lines.append("")
    lines.append("XMP: " + ("present" if r["xmp_present"] else "none"))
    for k, v in r["xmp"].items():
        lines.append(f"  {k} = {v}")
    lines.append("EXIF: " + (f"{len(r['exif'])} tags" if r["exif"] else "none"))
    for k, v in list(r["exif"].items())[:15]:
        lines.append(f"  {k} = {v[:120]}")
    lines.append("IPTC-IIM: " + ("present" if r["iptc"] else "none"))
    for k, v in r["iptc"].items():
        lines.append(f"  {k} = {v}")
    lines.append("ComfyUI workflow embedded: %s"
                 % ("yes" if r["comfyui_workflow_embedded"] else "no"))
    return "\n".join(lines)
