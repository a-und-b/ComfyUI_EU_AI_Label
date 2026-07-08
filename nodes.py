"""ComfyUI nodes: EU AI Label (Visible / Metadata Writer & Save / Metadata Check)."""

import json
import os

import numpy as np
import torch
from PIL import Image

import folder_paths

from . import euai_core as core

try:
    from comfy.cli_args import args as _comfy_args
    _METADATA_DISABLED = bool(getattr(_comfy_args, "disable_metadata", False))
except Exception:
    _METADATA_DISABLED = False

CATEGORY = "EU AI Label"

# dropdown value -> internal key
DST_CHOICES = {
    "trainedAlgorithmicMedia (fully AI-generated)": "trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia (AI-edited / composite)":
        "compositeWithTrainedAlgorithmicMedia",
    "algorithmicMedia (algorithmic, no AI training)": "algorithmicMedia",
    "none (do not set)": "none",
}


def _to_pil(t: torch.Tensor) -> Image.Image:
    arr = np.clip(255.0 * t.cpu().numpy(), 0, 255).astype(np.uint8)
    if arr.shape[-1] == 4:
        return Image.fromarray(arr, "RGBA")
    return Image.fromarray(arr, "RGB")


def _to_tensor(img: Image.Image) -> torch.Tensor:
    return torch.from_numpy(np.array(img.convert("RGB")).astype(np.float32) / 255.0)


class EUAILabelVisible:
    """Burn a visible EU AI label (icon / text / logo) into the image."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "label_type": (["EU Icon", "Text", "Text + EU Icon", "Custom Logo"],),
                "eu_icon_variant": (["AI", "AI generated", "AI modified"],
                                    {"default": "AI generated"}),
                "color_variant": (["black", "white"], {"default": "white"}),
                "custom_text": ("STRING", {"default": "AI generated"}),
                "size": ("FLOAT", {"default": 7.0, "min": 1.0, "max": 100.0, "step": 0.5,
                                   "tooltip": "Label width in % of image width"}),
                "margin": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 45.0, "step": 0.5,
                                     "tooltip": "Distance to the edge in % of image width"}),
                "opacity": ("FLOAT", {"default": 100.0, "min": 1.0, "max": 100.0, "step": 1.0}),
                "position": (core.POSITIONS, {"default": "bottom right"}),
            },
            "optional": {
                "custom_logo": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Composites a visible AI-transparency label (official EU icon, text or "
                   "custom logo) onto every image in the batch — Art. 50 EU AI Act.")

    def apply(self, image, label_type, eu_icon_variant, color_variant, custom_text,
              size, margin, opacity, position, custom_logo=None):
        logo = _to_pil(custom_logo[0]) if custom_logo is not None else None
        label = core.build_label(label_type, eu_icon_variant, color_variant,
                                 custom_text, logo)
        out = [
            _to_tensor(core.apply_label(_to_pil(img), label, size, margin,
                                        opacity, position))
            for img in image
        ]
        return (torch.stack(out),)


class EUAILabelMetadataSave:
    """Write XMP AI-labeling metadata and save to the output folder (Save node).

    Must save itself: the stock SaveImage node rewrites metadata, and ComfyUI
    image tensors cannot carry file metadata between nodes.
    """

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "digital_source_type": (list(DST_CHOICES), {
                    "tooltip": "IPTC DigitalSourceType — the machine-readable AI marker "
                               "read by Google and others"}),
                "description": ("STRING", {"multiline": True, "default":
                    "Enthält KI-generierte Inhalte — Kennzeichnung gemäß Art. 50 EU AI Act."}),
                "creator_tool": ("STRING", {"default": "ComfyUI"}),
                "credit": ("STRING", {"default": ""}),
                "custom_xmp_fields": ("STRING", {"multiline": True, "default": "",
                    "tooltip": "Optional: one key=value per line "
                               "(e.g. dc:rights=© 2026 Example GmbH)"}),
                "embed_workflow": ("BOOLEAN", {"default": True,
                    "tooltip": "Embed the ComfyUI workflow/prompt in the file. "
                               "Privacy note: prompts and local paths end up in the image."}),
                "format": (["PNG", "JPEG", "WebP"],),
                "jpeg_quality": ("INT", {"default": 92, "min": 1, "max": 100,
                                         "tooltip": "Quality for JPEG and WebP"}),
                "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                "filename_suffix": ("STRING", {"default": "_ai-labeled"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("file_path",)
    OUTPUT_NODE = True
    FUNCTION = "save"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Writes machine-readable AI-labeling metadata (XMP DigitalSourceType etc.) "
                   "and saves the images itself. Do NOT chain a SaveImage node after this — "
                   "it would strip the metadata.")

    def save(self, images, digital_source_type, description, creator_tool, credit,
             custom_xmp_fields, embed_workflow, format, jpeg_quality,
             filename_prefix, filename_suffix, prompt=None, extra_pnginfo=None):
        ext = {"PNG": "png", "JPEG": "jpg", "WebP": "webp"}[format]
        xmp = core.build_xmp(
            digital_source_type=DST_CHOICES[digital_source_type],
            description=description, creator_tool=creator_tool, credit=credit,
            custom_fields=core.parse_custom_fields(custom_xmp_fields))

        prompt_json = workflow_json = None
        if embed_workflow and not _METADATA_DISABLED:
            if prompt is not None:
                prompt_json = json.dumps(prompt)
            if extra_pnginfo and "workflow" in extra_pnginfo:
                workflow_json = json.dumps(extra_pnginfo["workflow"])

        full_output_folder, filename, counter, subfolder, _ = \
            folder_paths.get_save_image_path(filename_prefix, self.output_dir,
                                             images[0].shape[1], images[0].shape[0])
        results, paths = [], []
        for batch_number, image in enumerate(images):
            img = _to_pil(image)
            fname = filename.replace("%batch_num%", str(batch_number))
            file = f"{fname}_{counter:05}{filename_suffix}.{ext}"
            path = os.path.join(full_output_folder, file)
            core.save_with_metadata(img, path, format, xmp, quality=jpeg_quality,
                                    prompt_json=prompt_json, workflow_json=workflow_json)
            results.append({"filename": file, "subfolder": subfolder, "type": "output"})
            paths.append(path)
            counter += 1

        return {"ui": {"images": results}, "result": ("\n".join(paths),)}


class EUAILabelMetadataCheck:
    """Inspect a saved file: is there AI-labeling metadata (XMP/EXIF/IPTC/C2PA)?"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_path": ("STRING", {"default": "", "tooltip":
                    "Path to the image file. Relative paths are resolved against the "
                    "ComfyUI output folder. Connect the file_path output of the "
                    "Metadata Writer here for a round-trip check."}),
            },
            "optional": {
                "image": ("IMAGE", {"tooltip": "Optional passthrough"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("report", "json", "image")
    OUTPUT_NODE = True
    FUNCTION = "check"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Reads XMP (incl. DigitalSourceType), EXIF and IPTC metadata from a file "
                   "and detects embedded C2PA manifests (detection only, no signing).")

    @classmethod
    def IS_CHANGED(cls, file_path, image=None):
        # file_path is None when fed by a link instead of the widget
        try:
            return os.path.getmtime(cls._resolve(file_path))
        except (OSError, TypeError):
            return float("nan")

    @staticmethod
    def _resolve(file_path):
        file_path = file_path or ""
        path = file_path.strip().splitlines()[0].strip() if file_path.strip() else ""
        path = os.path.expanduser(path)
        if path and not os.path.isabs(path):
            for base in (folder_paths.get_output_directory(),
                         folder_paths.get_input_directory()):
                candidate = os.path.join(base, path)
                if os.path.isfile(candidate):
                    return candidate
        return path

    def check(self, file_path, image=None):
        path = self._resolve(file_path)
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(
                f"EU AI Label (Metadata Check): file not found: {path or '(empty)'}")
        result = core.inspect_file(path)
        report = core.build_report(result)
        print("\n" + report + "\n")
        if image is None:
            image = torch.zeros((1, 1, 1, 3))
        return {"ui": {"text": [report]},
                "result": (report, json.dumps(result, indent=2, ensure_ascii=False), image)}


NODE_CLASS_MAPPINGS = {
    "EUAILabelVisible": EUAILabelVisible,
    "EUAILabelMetadataSave": EUAILabelMetadataSave,
    "EUAILabelMetadataCheck": EUAILabelMetadataCheck,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EUAILabelVisible": "EU AI Label (Visible)",
    "EUAILabelMetadataSave": "EU AI Label (Metadata Writer & Save)",
    "EUAILabelMetadataCheck": "EU AI Label (Metadata Check)",
}
