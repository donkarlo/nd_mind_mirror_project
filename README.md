# nd_mind_mirror_project

`nd_mind_mirror_project` is an Ubuntu desktop writing/source-editing environment built with Python and PySide6, with LaTeX as its primary document format and a native SwiftUI/PencilKit iPad companion for drawing graphics directly into the document workflow.

The file on disk is always the canonical source. Visual editing, preview wrappers, search indexes, rendered PDFs, UI state, and iPad drawing sidecars are derived from that source and must not silently rewrite a document merely to display it.

## Current desktop features

### Workspace and Navigator

- Configurable workspace/search root.
- Navigator follows the active tab and reveals/highlights the corresponding file.
- Double-click opens editable files in Mind Mirror; PDFs/images can open in the system application.
- Navigator sort order is always **folders A–Z first, then files A–Z**.
- Navigator right-click commands are grouped into **Open**, **Copy / Share**, **Create**, and **Manage** submenus.
- GitHub actions derive the nearest Git repository and configured GitHub remote, including non-`origin` remotes such as `mghub`:
  - Copy GitHub URL
  - Open GitHub URL
- File/folder creation, rename, delete, clipboard-image paste, path copying, and file-manager reveal are supported.
- Pinned files can be opened/pinned from Navigator and are kept in the leading pinned-tab group.
- Navigator has two explicit tree-state buttons:
  - `−` **Collapse** remembers the exact current expansion state and collapses the tree.
  - `↶` **Restore Previous State** reopens only the folders that were expanded immediately before the last collapse.
- There is intentionally no **Expand All** behavior in this control; restoring the user's prior tree state is the goal.

### Structure panel

- LaTeX hierarchy recognizes `\part`, `\chapter`, `\section`, `\subsection`, `\subsubsection`, `\paragraph`, and `\subparagraph`.
- YAML receives a hierarchy-oriented Structure view as well.
- Clicking Structure moves the editor to the corresponding source position.
- Active-structure painting is deterministic: old backgrounds are cleared and only the deepest active structure row is highlighted.
- Qt row-selection painting is disabled so it cannot look like a second or third semantic highlight.
- Structure uses the same separate **Collapse** and **Restore Previous State** controls as Navigator.

### Fast file search

- Double Shift opens file search.
- Previous query is preserved and selected on reopen.
- Exact, prefix, substring, fuzzy, and hierarchical path matching are supported.
- Up/Down and Enter support keyboard-only navigation.
- Search rebuilds against the current workspace so external Dropbox/git/terminal changes appear without restarting.

### Tabs and session

- Multiple editor tabs with a configurable maximum count.
- `Ctrl+W` closes the current ordinary tab.
- `Ctrl+Tab` switches recent tabs.
- Tabs can be pinned; pinned files are persisted, reopened when available, protected from ordinary automatic eviction, and kept before unpinned tabs.
- Pin paths follow file renames and are removed when their target is deleted.
- Open files, active file, cursor/scroll positions, bookmarks, splitter sizes, window layout, pinned tabs, Preview state, and Auto Fit state are persisted.

## LaTeX editing

### Source mode

- LaTeX syntax highlighting.
- Configurable source font, size, line height, padding, tab size, indentation guides, soft wrapping, and wrap marker.
- Automatic Persian RTL/LTR line handling while keeping LaTeX command/setup lines usable.
- Smart Enter/list continuation.
- `Ctrl+Shift+F` formats LaTeX using the configured indentation hierarchy.
- `Ctrl+B` applies bold to the current selection.
- LaTeX completion and user snippets from `latex_shortcuts.yaml`.
- Clipboard-image insertion and relative figure paths.
- `é…` popup for accented Latin, German/European, mathematical, and typographic characters.
- `\iffalse … \fi` toolbar action wraps a selection; with no selection it inserts `\iffalse Dativ plural\fi` and selects `Dativ plural` for immediate replacement.

### Visual mode

Visual is an editable projection of the same canonical LaTeX source. Source and Visual share document/cursor mapping and do not maintain independent canonical documents.

- Common prose, headings, lists, styling, highlighting, inline symbols, and graphics are editable visually.
- Unsupported/raw LaTeX regions are preserved rather than silently discarded.
- The special-character popup inserts into Visual and serializes back to source.
- The `\iffalse` command maps the current Visual selection to canonical source, performs the raw-LaTeX wrapper operation, and returns to Visual.

### Undo and Redo

Undo/Redo is normalized before editor-specific handlers run:

- `Ctrl+Z` → Undo
- `Ctrl+Y` → Redo
- `Ctrl+Shift+Z` → Redo

The active controller uses Qt standard-key matching plus logical/native fallbacks so German/Swiss QWERTZ layouts do not reinterpret Y/Z into unrelated editor actions. The controller is instantiated by `EnhancedMainWindow`, so it is active in both Source and Visual editors.

## Bookmarks

- Source and Visual share one bookmark model.
- Bookmark gutter adds/removes markers.
- Bookmarks keep line/column and can be renamed or removed.
- Bookmark positions are persisted and relocate when content changes above them.
- The Bookmarks menu lists bookmarks across relevant files.

## Live PDF Preview

- LuaLaTeX live rendering.
- Multi-pass bibliography/citation rendering when required.
- Last valid PDF remains visible during transient compile failures.
- PDF text remains selectable/copyable.
- Ctrl+mouse-wheel zoom and panning are supported.
- Zoom percentage/page information is available in the Preview controls.
- PDF export is available.
- **Fit Once** performs content-aware fit.
- **Auto Fit** keeps fitting active while the Preview/splitter width changes; manual PDF zoom disables continuous Auto Fit.

### Permanent Preview toggle

The main window has an always-visible **Preview** toggle button in the **top-right corner of the menu bar**. It mirrors the existing checkable Preview action and is not a close/X button. The menu action and corner button remain synchronized.

## Keyboard shortcut settings

Application accelerators are separate from LaTeX snippet completion.

Shipped defaults:

```text
src/nd_mind_mirror/core/settings/defaults/keyboard_shortcuts.yaml
```

Persistent user copy after startup:

```text
/home/donkarlo/Dropbox/repo/data/nd_mind_mirror_project/keyboard_shortcuts.yaml
```

**Settings → Keyboard Shortcuts…** opens an Apply-based editor. Invalid sequences and duplicate non-empty bindings are rejected; Apply writes the YAML atomically and updates live `QAction` and `QShortcut` objects.

`latex_shortcuts.yaml` remains dedicated to LaTeX snippet/completion expansion.

## Persistent application data

All persistent Mind Mirror settings/state belong under:

```text
/home/donkarlo/Dropbox/repo/data/nd_mind_mirror_project/
```

Equivalent repository-relative path:

```text
/repo/data/nd_mind_mirror_project/
```

The directory contains or will contain:

- `settings.yaml` — general application/UI behavior.
- `keyboard_shortcuts.yaml` — application keyboard accelerators.
- `latex_shortcuts.yaml` — LaTeX completion/snippet shortcuts.
- `search_ignore.yaml` — workspace/search ignore rules.
- `session.ini` — lightweight session state such as Preview, pins, and Auto Fit.
- `ui_state.json` — window/splitter/navigation state.
- `templates/latex_preview_template.tex` — article/fragment preview wrapper.
- `templates/latex_preview_beamer_template.tex` — Beamer preview wrapper.

On the first run after this storage change, the application prefers existing user files from the older location

```text
~/Desktop/repo/data/nd_mind_mirror_project/
```

when present, copies/migrates them into the Dropbox data directory, and merges only missing shipped schema/default entries. Existing user values win.

## Native iPad drawing workflow

The iPad companion remains part of this repository. Editable Swift source is stored at:

```text
src/nd_mind_mirror/graphic/ipad/.source/nd_graphic.swiftpm/
```

The user-facing transfer artifact is:

```text
src/nd_mind_mirror/graphic/ipad/nd_graphic.zip
```

`nd_graphic.zip` is generated automatically from the hidden source package when the Ubuntu application starts and Swift source is newer than the existing archive. The ZIP contains one top-level package directory named `nd_graphic.swiftpm`.

### Opening the iPad app

1. Start/restart the Ubuntu Mind Mirror application so a fresh `nd_graphic.zip` is generated.
2. Wait for Dropbox sync.
3. In iPad Files, copy `nd_graphic.zip` from Dropbox to **On My iPad**.
4. Tap the ZIP once to extract it.
5. Open the resulting `nd_graphic.swiftpm` with Swift Playgrounds.

Do not rename a raw archive to `.swiftpm`; Swift Playgrounds requires the extracted package directory.

### iPad drawing controls

The active PencilKit toolbar exposes:

- Pencil
- Highlighter
- Eraser
- Lasso

Pencil and Highlighter maintain independent per-tool recent-color histories.

#### Persistent stroke defaults

- The last selected stroke color is stored in iPad `UserDefaults` and becomes the next launch's initial color.
- The last selected stroke thickness is stored in `UserDefaults` and becomes the next launch's initial thickness.
- Switching between Pencil and Highlighter restores that tool's own preferred recent color.
- Document-specific pencil metadata can still be loaded when a graphic document provides it.

#### Thickness control

- Thickness remains adjustable from 1 through 24.
- The toolbar shows the numeric thickness value.
- The slider uses a custom compact UIKit thumb instead of the oversized default center knob.

#### Recent-color matrix

- A grid button beside the Color Picker toggles the palette below the toolbar.
- The matrix displays only colors the user actually selected, newest first, up to the last 10 choices for the active color-capable tool.
- Colors are arranged in a compact five-column matrix.
- Selecting a matrix color moves it to the front of that tool's persisted history.

#### Zoom and canvas information

A status strip remains visible immediately above the canvas and shows:

- current zoom percentage;
- logical canvas width × height in pixels.

Zoom updates live while pinching and after automatic fit/reset.

#### Two-finger Undo

A single tap with **two fingers** on the drawing area performs exactly one PencilKit Undo. Toolbar Undo/Redo buttons remain available as well.

#### Lasso selection and movement

Selecting **Lasso** assigns PencilKit's native lasso selection tool. With Apple Pencil, draw a free curved boundary around existing PencilKit strokes, then drag the resulting selection to move those strokes. This manipulates editable PencilKit strokes rather than rasterizing the selected region.

#### Existing iPad workflow

- Pencil draws while direct finger gestures pan/pinch the outer scroll view.
- Highlighter uses marker rendering and its own recent-color history.
- Eraser uses vector erasing.
- Canvas presets and custom pixel dimensions are available.
- A background photo can be imported/removed.
- Drawing changes are autosaved through the Ubuntu/iPad bridge.
- Insert/update operations preserve PencilKit drawing data in the `.ndgraphic` sidecar and update the rendered graphic used by LaTeX.
- Bridge status and diagnostic log controls remain available.

## Running on Ubuntu

From the project root:

```bash
cd /home/donkarlo/Dropbox/repo/nd_mind_mirror_project
python nd_mind_mirror_project
```

or use the executable launcher when desired:

```bash
./nd_mind_mirror_project
```

The startup path also refreshes the iPad transfer ZIP before constructing the Qt window. `Ctrl+C` in the launching terminal requests a clean main-window close so normal shutdown handlers can stop timers/renderers/bridge resources.

## Project layout

- `src/nd_mind_mirror/app/` — application startup/lifetime.
- `src/nd_mind_mirror/core/` — settings, documents, rendering, search, completion, formatting, and workspace logic.
- `src/nd_mind_mirror/ui/` — Qt editors, panels, preview, window, toolbar, and UX controllers.
- `src/nd_mind_mirror/graphic/ipad/.source/nd_graphic.swiftpm/` — editable native iPad Swift Playgrounds source.
- `src/nd_mind_mirror/graphic/ipad/nd_graphic.zip` — regenerated iPad transfer artifact.
- `src/nd_mind_mirror/graphic/ipad/package_builder.py` — builds the transfer ZIP from source.
- `src/nd_mind_mirror/graphic/bridge/` — Ubuntu/iPad bridge and live graphic update signaling.
- `src/nd_mind_mirror/graphic/web/` — browser fallback.
- `src/nd_mind_mirror/graphic/native_future/` — archived/future native/Xcode work.
- `src/nd_mind_mirror/graphic/tikz_future/` — parked experimental drawing-to-TikZ work.
- `tests/` — automated tests.
- `tools/` — development/maintenance utilities.
- `/repo/data/nd_mind_mirror_project/` — persistent user settings and UI/session state.

## Code documentation rule

New and modified implementation files must begin with a concise one-line file/module description. New and modified classes/structs and methods/functions must have a concise one-line docstring/documentation comment describing responsibility. Legacy files are brought under this rule as they are touched rather than being mass-rewritten without a functional reason.
