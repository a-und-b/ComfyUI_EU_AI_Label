# ComfyUI_EU_AI_Label

**Label AI-generated images directly in your ComfyUI workflow — visible EU icon + machine-readable metadata, as required by Art. 50 EU AI Act (in force August 2, 2026).**

*Deutsche Version siehe unten → [Deutsch](#deutsch)*

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

An example workflow is included: [example_workflows/eu-ai-label-example.json](example_workflows/eu-ai-label-example.json) — `LoadImage → Visible Label → Metadata Writer & Save → Metadata Check`.

## ⚠️ The SaveImage trap

**Do not chain a regular `SaveImage` node after the Metadata Writer.** ComfyUI image tensors cannot carry file metadata, and `SaveImage` writes its own metadata — your AI labeling would be lost. The **Metadata Writer & Save** node is a save node: it writes the file (with metadata) to your `output/` folder itself. No `SaveImage` needed. (Same pitfall as with [comfyui_c2pa_signer](https://github.com/mikecaronna/comfyui_c2pa_signer).)

## Node reference

### EU AI Label (Visible)

Batch-capable. Composites the label with high-quality LANCZOS scaling, preserving the icon's aspect ratio.

- **label_type**: `EU Icon` | `Text` | `Text + EU Icon` | `Custom Logo` (via the optional `custom_logo` image input)
- **eu_icon_variant**: `AI` (base) | `AI generated` | `AI modified` — the three official EU icons, bundled in this repo
- **color_variant**: `black` | `white` (the official 50 %-opacity variants are covered by the opacity slider)
- **custom_text**: default `KI-generiert` (bundled DejaVu Sans font, free license)
- **size**: label width in % of image width (default 7)
- **margin**: distance to the edge in % of image width (default 3)
- **opacity**: 1–100 % (default 100)
- **position**: 9-point grid, default bottom right

### EU AI Label (Metadata Writer & Save)

- **digital_source_type** — the [IPTC DigitalSourceType](https://cv.iptc.org/newscodes/digitalsourcetype/), the machine-readable AI marker that Google and others read:
  - `trainedAlgorithmicMedia` — fully AI-generated
  - `compositeWithTrainedAlgorithmicMedia` — AI-edited / composite
  - `algorithmicMedia` — algorithmic without AI training
  - `none` — do not set
- **description** (`dc:description`), **creator_tool** (`xmp:CreatorTool`), **credit** (`photoshop:Credit`)
- **custom_xmp_fields** — one `key=value` per line; known prefixes (`dc:`, `xmp:`, `photoshop:`, `Iptc4xmpExt:`) map to their namespaces, everything else goes into a package-specific namespace
- **embed_workflow** — embeds the ComfyUI workflow/prompt like `SaveImage` does. **Privacy note: your prompts and node settings end up inside the image file.** Default on; PNG files remain drag-&-drop-restorable in ComfyUI, WebP via EXIF.
- **format** `PNG` | `JPEG` | `WebP`, **jpeg_quality** (also used for WebP), **filename_prefix**/**filename_suffix** (default `_ai-labeled`)
- Output **file_path** (STRING): the saved file path(s), one per line — wire it into the Check node for an immediate round-trip verification.

**Implementation note:** the XMP packet is generated as RDF/XML and embedded natively via Pillow (PNG: `iTXt XML:com.adobe.xmp`, JPEG: APP1 segment, WebP: XMP chunk). We deliberately avoid `python-xmp-toolkit` (needs the exempi C library) and `pyexiv2` (binary wheels, platform issues) — zero extra dependencies, runs everywhere ComfyUI runs. No network access at runtime.

### EU AI Label (Metadata Check)

Answers: *"Is there AI labeling in this file already?"* Input is a **file path** (tensors carry no metadata; relative paths resolve against the ComfyUI output folder — or wire the Writer's `file_path` output straight in). Outputs a human-readable report and a JSON string; reads XMP (incl. `DigitalSourceType`), EXIF, IPTC-IIM and **detects C2PA manifests** (JPEG APP11/JUMBF, PNG `caBX`, WebP `C2PA` chunk). Detection only — signature verification and C2PA **signing** are out of scope (signing requires a certificate; planned as v2, see [comfyui_c2pa_signer](https://github.com/mikecaronna/comfyui_c2pa_signer) in the meantime).

## Icon & font licenses

- The EU AI icons are the [official icons published by the European Commission](https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content) (June 2026). They are **free to use, no attribution required**.
- Bundled font: [DejaVu Sans](https://dejavu-fonts.github.io/) (free license, see `assets/fonts/LICENSE-DejaVu.txt`).

## Legal disclaimer

This tool does not constitute legal advice. Using the EU icons is voluntary; the obligation to label AI-generated or AI-manipulated content ("deep fakes" in the broad sense) under Art. 50 EU AI Act remains with you as the user/provider. Whether and how specific content must be labeled depends on your individual case.

---

<a name="deutsch"></a>
# Deutsch

**KI-generierte Bilder direkt im ComfyUI-Workflow kennzeichnen — sichtbares EU-Icon + maschinenlesbare Metadaten gemäß Art. 50 EU AI Act (gültig ab 2. August 2026).**

Dieses Node-Pack bringt den Funktionsumfang des Browser-Tools [KI-Label Studio](https://label.marketing-ki.de/KI-Label-Studio.html) in ComfyUI — als letzter Schritt jeder Bildgenerierung. Fachlicher Hintergrund: [Kennzeichnungspflicht für KI-Bilder ab 2026](https://marketing-ki.de/aktuelles/ki-bilder-kennzeichnungspflicht-ab-2026/).

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/a-und-b/ComfyUI_EU_AI_Label.git
pip install -r ComfyUI_EU_AI_Label/requirements.txt
```

ComfyUI neu starten — die Nodes erscheinen in der Kategorie **EU AI Label**. Beispiel-Workflow: `example_workflows/eu-ai-label-example.json`.

## ⚠️ Die SaveImage-Falle

**Nach dem Metadata Writer keinen normalen `SaveImage`-Node anschließen!** ComfyUI-Tensoren transportieren keine Datei-Metadaten, und `SaveImage` schreibt eigene Metadaten — die KI-Kennzeichnung ginge verloren. Der **Metadata Writer & Save** speichert selbst in den `output/`-Ordner.

## Die drei Nodes

1. **EU AI Label (Visible)** — brennt ein sichtbares Label ein: offizielles EU-Icon (drei Varianten: `AI`, `AI generated`, `AI modified`, jeweils schwarz/weiß), freier Text (Default „KI-generiert"), Text + Icon oder eigenes Logo. Größe/Rand in % der Bildbreite, Deckkraft, 9er-Positionsraster. Batch-fähig.
2. **EU AI Label (Metadata Writer & Save)** — schreibt den IPTC `DigitalSourceType` (der Standard, den u. a. Google ausliest) plus Beschreibung, CreatorTool, Credit und eigene XMP-Felder; speichert als PNG/JPEG/WebP. Der `file_path`-Output lässt sich direkt in den Check-Node stecken. **Privacy-Hinweis:** `embed_workflow` bettet den kompletten Workflow (inkl. Prompts) in die Datei ein.
3. **EU AI Label (Metadata Check)** — beantwortet: „Steckt schon eine KI-Kennzeichnung drin?" Liest XMP/EXIF/IPTC aus einer Datei und erkennt vorhandene C2PA-Manifeste (nur Erkennung; Signieren erfordert ein Zertifikat und ist für v2 geplant).

## Lizenzen & rechtlicher Hinweis

Die EU-Icons sind die [offiziellen Icons der EU-Kommission](https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content) — frei nutzbar, ohne Namensnennung. Schrift: DejaVu Sans (freie Lizenz).

**Dieses Tool ersetzt keine Rechtsberatung.** Die Nutzung der EU-Icons ist freiwillig; die Kennzeichnungspflicht nach Art. 50 EU AI Act verbleibt beim Nutzer bzw. Anbieter.
