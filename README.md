# Trimsheet Plugin for Maya 2026

A Maya 2026 Python tool that generates an adjustable polygon **trim strip** along a
selected edge loop, with real-time width / normal-offset / UV-density controls and
one-click analytic **straight UVs** (world-scale, tileable) for trim-sheet texturing.

Built with OpenMaya API 2.0 + PySide6. The panel UI labels are in Chinese.

---

## Features

- Generate a surface-hugging strip from a single edge loop (open or closed)
- Real-time **width** and **normal offset** via sliders, with native undo/redo
- Analytic **straight UVs** — world-proportional and tileable, no Unfold needed
- Flip normals; one-click **finalize** (delete history + center pivot) for a clean static mesh
- Native undo/redo through an API 2.0 `MPxCommand` command plugin
- Frameless, dark-themed PySide6 tool window

## Requirements

- Autodesk **Maya 2026.3** (Python 3.11, PySide6 / shiboken6)

## Important: install on an ASCII-only path

Maya''s scripted-plugin loader fails to load a `.py` plugin when its file path contains
**non-ASCII characters** (e.g. a Chinese folder name) on localized Windows
(`UnicodeDecodeError ... invalid start byte`). Put this repo somewhere with an
**ASCII-only path**, for example `C:\maya\trimsheet-plugin-maya2026` — not a path like
`...\Maya<chinese>\...`.

## Install

1. Put the repo''s root folder on Maya''s `PYTHONPATH` (or drop the `trim_strip` package
   into your Maya `scripts` directory).
2. In the Maya Script Editor (Python tab):

   ```python
   from trim_strip.install import install
   install.install_shelf_button()
   ```

   This loads the command plugin (`ts_plugin.py`) and adds a **Trim** shelf button.

## Usage

1. Double-click to select an edge loop in the viewport.
2. Open the panel via the **Trim** shelf button.
3. Click **从所选边线生成面片** (Generate from selected edges).
4. Drag **宽度** (width) and **法线偏移** (normal offset) for live adjustment;
   tweak **UV 密度** (UV density); click **打直 UV** (straighten UVs).
5. Optionally tick **翻转法线** (flip normals).
6. Click **完成:删历史 + Center Pivot** (finalize) to bake a clean static mesh.

## Testing

The pure-Python geometry core (`trim_strip/core`) has **zero Maya dependencies** and is
unit-tested with plain pytest:

```bash
python -m pytest trim_strip/tests -v
```

## Project layout

```
trim_strip/
  core/          pure-Python geometry (vectors, loop ordering, frames, rails, UVs)
  maya_io/       OpenMaya: read selection, build/update mesh, cache frames, finalize
  ts_plugin.py   MPxCommand command plugin (tsGenerate / tsUpdate) with native undo
  tool.py        orchestration layer the UI calls
  ui/panel.py    frameless dark PySide6 tool window
  install/       shelf-button installer
  tests/         pytest unit tests for the core
docs/            design spec + implementation plan
```

## Architecture note

Adjustments only move existing vertices (topology is fixed), so the tool caches a base
"frame" `{P, N, W, arc-length}` per loop vertex on the strip transform and recomputes the
`2 x N` rail points with pure vector math — millisecond-fast live editing without a custom
DG node.

## License

MIT — see [LICENSE](LICENSE).
