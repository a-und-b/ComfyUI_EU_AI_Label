"""Roundtrip: write XMP metadata -> read it back with the inspector, per format.
Plus visible-label compositing checks. Runs without ComfyUI (see conftest.py)."""

import json

import pytest
from PIL import Image

import euai_core as core


@pytest.fixture
def base_image():
    return Image.new("RGB", (512, 384), (90, 120, 200))


XMP_KW = dict(
    digital_source_type="trainedAlgorithmicMedia",
    description="Enthält KI-generierte Inhalte — Kennzeichnung gemäß Art. 50 EU AI Act.",
    creator_tool="ComfyUI",
    credit="a&b <Test> GmbH",
    custom_fields=core.parse_custom_fields("dc:rights=© 2026 Test\nmy key=value"),
)


@pytest.mark.parametrize("fmt,ext", [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")])
def test_metadata_roundtrip(tmp_path, base_image, fmt, ext):
    path = str(tmp_path / f"labeled.{ext}")
    xmp = core.build_xmp(**XMP_KW)
    core.save_with_metadata(base_image, path, fmt, xmp, quality=92,
                            prompt_json=json.dumps({"1": {"class_type": "KSampler"}}),
                            workflow_json=json.dumps({"nodes": []}))

    r = core.inspect_file(path)
    assert r["ai_labeling_found"] is True
    assert r["digital_source_type"] == "trainedAlgorithmicMedia"
    assert r["xmp"]["xmp:CreatorTool"] == "ComfyUI"
    assert r["xmp"]["photoshop:Credit"] == "a&b <Test> GmbH"  # XML escaping roundtrip
    assert "Art. 50 EU AI Act" in r["xmp"]["dc:description"]
    assert r["xmp"]["dc:rights"] == "© 2026 Test"
    assert r["xmp"]["euai:my_key"] == "value"
    assert r["comfyui_workflow_embedded"] is True
    assert r["c2pa"]["present"] is False
    # report is human-readable and states the verdict
    assert "AI labeling found: YES" in core.build_report(r)


def test_no_labeling_detected(tmp_path, base_image):
    path = str(tmp_path / "plain.png")
    base_image.save(path)
    r = core.inspect_file(path)
    assert r["ai_labeling_found"] is False
    assert r["xmp_present"] is False
    assert "AI labeling found: NO" in core.build_report(r)


def test_dst_none_not_set(tmp_path, base_image):
    path = str(tmp_path / "none.png")
    core.save_with_metadata(base_image, path, "PNG",
                            core.build_xmp(digital_source_type="none",
                                           creator_tool="ComfyUI"))
    r = core.inspect_file(path)
    assert r["digital_source_type"] == ""
    assert r["ai_labeling_found"] is False
    assert r["xmp"]["xmp:CreatorTool"] == "ComfyUI"


def test_c2pa_detection_jpeg(tmp_path, base_image):
    """Synthetic APP11 JUMBF segment must be detected."""
    path = str(tmp_path / "c2pa.jpg")
    base_image.save(path, "JPEG")
    data = open(path, "rb").read()
    payload = b"JP\x00\x01" + b"\x00\x00\x00\x10jumb" + b"\x00" * 8
    seg = b"\xff\xeb" + (len(payload) + 2).to_bytes(2, "big") + payload
    open(path, "wb").write(data[:2] + seg + data[2:])
    r = core.inspect_file(path)
    assert r["c2pa"]["present"] is True
    assert r["ai_labeling_found"] is True


@pytest.mark.parametrize("label_type", ["EU Icon", "Text", "Text + EU Icon"])
@pytest.mark.parametrize("position", core.POSITIONS)
def test_visible_label_changes_expected_region(base_image, label_type, position):
    label = core.build_label(label_type, "AI generated", "white", "KI-generiert")
    out = core.apply_label(base_image.copy(), label, size_pct=20, margin_pct=3,
                           opacity_pct=100, position=position)
    assert out.size == base_image.size and out.mode == "RGB"
    # pixels changed somewhere, and the image corner opposite the label is untouched
    import numpy as np
    a, b = np.asarray(base_image), np.asarray(out)
    assert (a != b).any(), "label did not change any pixels"
    if position == "bottom right":
        assert (a[:20, :20] == b[:20, :20]).all(), "top-left corner should be untouched"
        assert (a[-60:, -60:] != b[-60:, -60:]).any(), "label not in bottom-right region"


def test_opacity_and_custom_logo(base_image):
    logo = Image.new("RGB", (100, 50), (255, 0, 0))
    label = core.build_label("Custom Logo", "AI", "black", "", custom_logo=logo)
    import numpy as np
    full = np.asarray(core.apply_label(base_image.copy(), label, 20, 3, 100, "bottom right"))
    half = np.asarray(core.apply_label(base_image.copy(), label, 20, 3, 50, "bottom right"))
    base = np.asarray(base_image)
    d_full = np.abs(full.astype(int) - base.astype(int)).sum()
    d_half = np.abs(half.astype(int) - base.astype(int)).sum()
    assert 0 < d_half < d_full, "50% opacity must change less than 100%"


def test_custom_logo_required():
    with pytest.raises(ValueError):
        core.build_label("Custom Logo", "AI", "black", "")


def test_all_bundled_icons_load():
    for variant in core.ICON_FILES:
        for color in ("black", "white"):
            icon = core.load_icon(variant, color)
            assert icon.mode == "RGBA" and icon.width == 1200
