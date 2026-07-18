# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-07-18

### Changed
- Layers named `_root_` anywhere in the document are now treated as non-exported
  origin markers; their
  visible center becomes Spine `0,0` for exported attachment and bone positions.
- Split exporter internals into `models.py`, `tags.py`, and `image_writer.py`
  while keeping the existing exporter API available.
- Exported image and attachment names now include the immediate parent group
  name as a prefix, for example `front_head.png`.
- Export now processes only the layers inside the **active group layer**, and
  both visible and hidden layers within it are exported.
- The export folder and Spine JSON are named after the active group layer
  (`activeGroupName/activeGroupName.json`) instead of a nested
  `parentGroupName/activeGroupName` structure.

## [1.0.0] - 2026-07-17

### Added
- Group-based export workflow: the active group layer defines the export name as
  `parentGroupName_activeGroupName` (layer tags stripped), falling back to just
  the active group name when it has no group parent.
- Export dialog now asks only for an **export folder**. The plugin automatically
  creates a `<combined name>` subfolder containing `<combined name>.json` and an
  `images` folder.

### Changed
- Hidden layers, and layers inside hidden groups, are now always ignored during
  export. Only visible layers are checked and exported.

### Removed
- Removed the "Ignore hidden layers" option and checkbox; hidden-layer filtering
  is now always on.

### Fixed
- Export is cancelled with a clear message when the active node is not a group
  layer, prompting the user to change the active node.
