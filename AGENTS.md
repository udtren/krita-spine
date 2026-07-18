# AGENTS.md

Guidance for Codex (and other AI assistants) when working in this repository.

## Project Overview

Krita Spine Export is a Krita Python plugin that exports document layers as PNG
attachments plus Spine JSON, modeled after Esoteric Software's
`PhotoshopToSpine.jsx` workflow.

## Repository Layout

```
spine_export.desktop     # Krita plugin descriptor
README.md                # User-facing documentation
CHANGELOG.md             # Release history
spine_export/
    __init__.py          # Extension entry point; registers the Tools menu action
    dialog.py            # Qt export dialog (PyQt5/PySide6)
    exporter.py          # Export orchestration, layer collection/preparation, JSON output
    models.py            # Shared dataclasses and SpineExportError
    tags.py              # Layer/group tag parsing and naming helpers
    image_writer.py      # PNG/template image writing and Qt image helpers
```

## Runtime & Environment

- The plugin runs **inside Krita's embedded Python interpreter**, not standalone.
- Imports such as `krita`, `PyQt5`, and `PySide6` are only resolvable at runtime
  inside Krita. Editor/lint "import could not be resolved" warnings for these are
  expected and should be ignored.
- Qt is imported with a `PyQt5` first, `PySide6` fallback pattern to support
  different Krita builds. Preserve this pattern when adding Qt imports.

## Architecture Notes

- `__init__.py` registers `KritaSpineExtension` and adds the
  "Export to Spine..." action under Tools > Scripts, opening `SpineExportDialog`.
- `dialog.py` (`SpineExportDialog`) collects an **export folder** and options,
  derives the export name via `active_group_export_name`, and constructs
  `ExportSettings` before running `SpineExporter`.
- `exporter.py` contains `active_group_export_name(document)` and
  `SpineExporter`. It validates the active group layer, walks the children of
  the active group layer, prepares `LayerInfo` records, coordinates image output,
  and writes Spine JSON.
- `models.py` owns the shared dataclasses: `ExportSettings`, `ExportResult`,
  `LayerInfo`, `BoneInfo`, and `SlotInfo`, plus `SpineExportError`.
- `tags.py` owns layer/group name tag parsing and name derivation. This includes
  `[folder]`, `[skin]`, `[bone]`, `[slot]`, `[path]`, `[scale]`, `[trim]`,
  `[name]`, and the parent-prefixed attachment name rule.
- `image_writer.py` owns PNG output, template output, `InfoObject` configuration,
  and the `QImage` fast path for RGBA/U8 layer projections.
- `_collect_layers` starts from the active group layer (not the document root)
  and exports all layers inside it, both visible and hidden.

## Conventions

- Keep changes minimal and focused; do not refactor unrelated code.
- Do not add docstrings, comments, or type annotations to code you did not
  change.
- Update `README.md` and `CHANGELOG.md` when user-facing behavior changes.
- There is no automated test suite; validate logic changes by reasoning about the
  Krita API and, where possible, by testing manually inside Krita.
