# ComfyUI_EU_AI_Label

**Label AI-generated images directly in your ComfyUI workflow with the official EU icon and machine-readable metadata, as required by Art. 50 EU AI Act (in force August 2, 2026).**

Inspired by the browser tool [KI-Label Studio](https://label.marketing-ki.de/KI-Label-Studio.html), this node pack brings the same functionality into ComfyUI as the last step of every image generation:

| Node | Purpose |
|---|---|
| **EU AI Label (Visible)** | Burns a visible label into the image: official EU AI icon, text, text + icon, or your own logo |
| **EU AI Label (Metadata Writer & Save)** | Writes machine-readable XMP metadata (IPTC `DigitalSourceType` etc.) and **saves the file itself** |
| **EU AI Label (Metadata Check)** | Inspects any image file: XMP, EXIF, IPTC — and detects embedded C2PA manifests |

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/a-und-b/ComfyUI_EU_AI_Label.git
pip install -r ComfyUI_EU_AI_Label/requirements.txt   # Pillow + numpy, usually already present
```

Restart ComfyUI. The nodes appear under the category **EU AI Label**. Works with both the legacy renderer and Nodes 2.0.

An example workflow is included: [example_workflows/eu-ai-label-example.json](example_workflows/eu-ai-label-example.json)

> [!CAUTION]
> **Do not chain a regular `SaveImage` node after the Metadata Writer.** ComfyUI image tensors cannot carry file metadata, and `SaveImage` writes its own metadata. Your AI labeling metadata would be lost! The **Metadata Writer & Save** node is a save node: it writes the file (with metadata) to your `output/` folder itself. No `SaveImage` needed.

## Node reference

### EU AI Label (Visible)

Batch-capable. Composites the label with high-quality LANCZOS scaling, preserving the icon's aspect ratio.

- **label_type:** <br/> `EU Icon` | `Text` | `Text + EU Icon` | `Custom Logo` (via the optional `custom_logo` image input)
- **eu_icon_variant:** <br/> `AI` (base) | `AI generated` | `AI modified` (the three official EU icons)
- **color_variant:** <br/> `black` | `white` (the official 50 %-opacity variants are covered by the opacity slider)
- **custom_text:** <br/> Default `AI generated` (bundled DejaVu Sans font, free license)
- **size:** <br/> Label width in % of image width (default 7)
- **margin:** <br/> Distance to the edge in % of image width (default 3)
- **opacity:** <br/> 1–100 % (default 100)
- **position:** <br/> 9-point grid, default bottom right

### EU AI Label (Metadata Writer & Save)

- **digital_source_type:** <br/> [IPTC DigitalSourceType](https://cv.iptc.org/newscodes/digitalsourcetype/), the machine-readable AI marker that Google and others read:
  - `trainedAlgorithmicMedia`: fully AI-generated
  - `compositeWithTrainedAlgorithmicMedia`: AI-edited / composite
  - `algorithmicMedia`: algorithmic without AI training
  - `none`: do not set
- **description:** <br/> (`dc:description`), **creator_tool** (`xmp:CreatorTool`), **credit** (`photoshop:Credit`)
- **custom_xmp_fields:** <br/>  One `key=value` per line; known prefixes (`dc:`, `xmp:`, `photoshop:`, `Iptc4xmpExt:`) map to their namespaces, everything else goes into a package-specific namespace
- **embed_workflow:** <br/> Embeds the ComfyUI workflow/prompt like `SaveImage` does. **Privacy note: your prompts and node settings end up inside the image file.** Default on; PNG files remain drag-&-drop-restorable in ComfyUI, WebP via EXIF.
- **format:** <br/> `PNG` | `JPEG` | `WebP`, **jpeg_quality** (also used for WebP), **filename_prefix**/**filename_suffix** (default `_ai-labeled`)
- Output **file_path** (STRING) <br/> The saved file path(s), one per line — wire it into the Check node for an immediate round-trip verification.

> [!NOTE]
> The XMP packet is generated as RDF/XML and embedded natively via Pillow (PNG: `iTXt XML:com.adobe.xmp`, JPEG: APP1 segment, WebP: XMP chunk). We deliberately avoid `python-xmp-toolkit` (needs the exempi C library) and `pyexiv2` (binary wheels, platform issues) — zero extra dependencies, runs everywhere ComfyUI runs. No network access at runtime.

### EU AI Label (Metadata Check)

This node shows if there already is AI labeling in a file. Input is a **file path** (tensors carry no metadata; relative paths resolve against the ComfyUI output folder. Or wire the Writer's `file_path` output straight in). Outputs a human-readable report and a JSON string; reads XMP (incl. `DigitalSourceType`), EXIF, IPTC-IIM and **detects C2PA manifests** (JPEG APP11/JUMBF, PNG `caBX`, WebP `C2PA` chunk). Detection only — signature verification and C2PA **signing** are out of scope (signing requires a certificate; planned as v2, see [comfyui_c2pa_signer](https://github.com/mikecaronna/comfyui_c2pa_signer) in the meantime).

## Icon & font licenses

- The EU AI icons are the [official icons published by the European Commission](https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content) (June 2026). They are **free to use, no attribution required**. The original SVG sources ship under `assets/icons/svg-source/`; the PNGs the nodes actually load (`assets/icons/*.png`) are pre-rendered from these SVGs at 900px height via `rsvg-convert`, so the node runtime stays Pillow-only (no SVG-rendering dependency, which would drag in a native library like cairo and complicate Windows installs).
- Bundled font: [DejaVu Sans](https://dejavu-fonts.github.io/) (free license, see `assets/fonts/LICENSE-DejaVu.txt`).

## Legal disclaimer

This tool does not constitute legal advice. Using the EU icons is voluntary; the obligation to label AI-generated or AI-manipulated content ("deep fakes" in the broad sense) under Art. 50 EU AI Act remains with you as the user/provider. Whether and how specific content must be labeled depends on your individual case.

## Acknowledgements

- [**uncanny minds GmbH**](https://marketing-ki.de/) <br> The creators of [KI-Label Studio](https://label.marketing-ki.de/KI-Label-Studio.html), the browser tool this node pack's feature set is modeled on.
- [**comfyui_c2pa_signer**](https://github.com/mikecaronna/comfyui_c2pa_signer) by mikecaronna <br> Reference architecture for ComfyUI content-credential nodes, including the SaveImage-metadata pitfall this repo also documents.
- [**DejaVu Fonts project**](https://dejavu-fonts.github.io) (based on Bitstream Vera, designed by Jim Lyles/Bitstream, Inc.) <br> Bundled `DejaVuSans.ttf`, see `assets/fonts/LICENSE-DejaVu.txt`.
- [**European Commission**](https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content) <br> Official EU AI-labeling icons, bundled under `assets/icons/`.
