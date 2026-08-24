# nd_mind_mirror_project

`nd_mind_mirror_project` is an Ubuntu desktop writing/source-editing environment built with Python and PySide6, with LaTeX as its primary document format and a native SwiftUI/PencilKit iPad companion for drawing graphics directly into the document workflow.

The file on disk is always the canonical source. Visual editing, preview wrappers, search indexes, rendered PDFs, UI state, and iPad drawing sidecars are derived from that source and must not silently rewrite a document merely to display it.

## Current desktop features

### Workspace and Navigator

- Configurable workspace/search root.
- Navigator follows the active tab and reveals/highlights the corresponding file.
- Navigator selection/reveal is single-pass and non-recentering: create, rename, drag/move, and active-tab reveals do not schedule repeated center-scroll passes that make the tree jump away and back.
- Routine create, rename, drag/move, delete, and clipboard-image filesystem updates rely on `QFileSystemModel` live row notifications instead of fully invalidating the proxy tree; full filter resets are reserved for real workspace-root or ignore-rule reconfiguration so scroll and expansion state stay stable.
- Double-click opens editable files in Mind Mirror; PDFs/images can open in the system application.
- Navigator sort order is always **folders A–Z first, then files A–Z**.
- Navigator right-click commands are grouped into **Open**, **Copy / Share**, **Create**, and **Manage** submenus.
- **Copy Dropbox Path** copies the selected item relative to `~/Dropbox` (for example `/repo/nd_mind_mirror_project/...`) while **Copy Absolute Path** remains available separately.
- GitHub actions derive the nearest Git repository and configured GitHub remote, including non-`origin` remotes such as `mghub`:
  - Copy GitHub URL
  - Open GitHub URL
- File/folder creation, rename, delete, clipboard-image paste, path copying, and file-manager reveal are supported.
- File/folder rename and drag/move operations remap open editor tabs and renderer paths to the new location; queued/running preview work against the old path is stopped before the move so stale-path compile errors are not emitted after the filesystem operation completes.
- **F2** renames the currently selected Navigator file or folder using the same rename workflow as the context menu.
- Pinned files can be opened/pinned from Navigator and are kept in a dedicated pinned-tab row.
- Navigator has two explicit tree-state buttons:
  - `−` **Collapse** remembers the exact current expansion state and collapses the tree.
  - `↶` **Restore Previous State** reopens only the folders that were expanded immediately before the last collapse.
- There is intentionally no **Expand All** behavior in this control; restoring the user's prior tree state is the goal.

### Structure panel

- LaTeX hierarchy recognizes `\part`, `\chapter`, `\section`, `\subsection`, `\subsubsection`, `\paragraph`, and `\subparagraph`.
- YAML receives a hierarchy-oriented Structure view as well.
- Clicking Structure moves the editor to the corresponding source position.
- Active-structure painting is deterministic: old backgrounds, Qt current-item state, and Qt selection state are cleared so only the deepest active structure row is highlighted.
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
- Tabs are displayed in **two rows**: the upper row contains persistent pinned files, while the lower row contains ordinary currently open files; pinned files are not duplicated in the ordinary row.
- Tabs in both the **Pinned** and **Open** rows can be drag-reordered; each row's order is saved immediately in `session.ini` and restored after restart.
- `Ctrl+W` closes the current ordinary tab.
- `Ctrl+Tab` switches recent tabs.
- Tabs can be pinned; pinned files are persisted, reopened when available, protected from ordinary automatic eviction, and shown in the saved pinned-row order.
- Pin and open-row paths follow file renames and are removed when their target is deleted.
- Open files, active file, cursor/scroll positions, bookmarks, splitter sizes, window layout, both tab-row orders, Preview state, and Auto Fit state are persisted.

## LaTeX editing

### Source mode

- LaTeX syntax highlighting.
- Configurable source font, size, line height, padding, tab size, indentation guides, soft wrapping, and wrap marker.
- `Tab` indents by one configurable `editor.tab_size` unit using spaces and `Shift+Tab` outdents by one unit; the shipped default is **3 spaces**, multi-line selections are handled together, and LaTeX Auto Format uses the same setting.
- All Source editors, including LaTeX, YAML, and generic text/code files, have a logical line-number gutter that numbers each actual source line exactly once; visual continuation rows produced by soft wrap do **not** receive extra line numbers.
- Automatic Persian RTL/LTR line handling while keeping LaTeX command/setup lines usable; fraction-oriented math lines are kept LTR when needed so `\frac` source is not visually reordered.
- Smart Enter/list continuation.
- `Ctrl+Shift+F` formats LaTeX using the configured indentation hierarchy.
- `Ctrl+B` applies bold to the current selection.
- LaTeX completion and user snippets from `latex_shortcuts.yaml`.
- Clipboard and iPad image insertion use the same monotonic per-folder `img_N.png` sequence. The next number is the highest existing `img_N` in the `.tex` file's folder plus one, so images are never silently overwritten and numbering is shared between clipboard paste and iPad insertion.
- Image insertion keeps the complete LaTeX `figure` environment visible in Source, including `\begin{figure}`, `\centering`, `\includegraphics[...]`, and `\end{figure}`. Clicking a managed figure can therefore be recognized as an iPad graphic update target.
- `é…` popup for accented Latin, German/European, mathematical, and typographic characters.
- `\iffalse … \fi` toolbar action wraps a selection; with no selection it inserts `\iffalse Dativ plural\fi` and selects `Dativ plural` for immediate replacement.

### Visual mode

Visual is an editable projection of the same canonical LaTeX source. Source and Visual share document/cursor mapping and do not maintain independent canonical documents.

- Common prose, headings, lists, styling, highlighting, inline symbols, and graphics are editable visually.
- Simple and nested `\frac{...}{...}` expressions receive a readable fraction-slash projection while the original raw LaTeX remains canonical for serialization.
- Graphic projection respects relative LaTeX widths such as `width=0.9\textwidth`, `\linewidth`, and `\columnwidth`; small raster images may be upscaled in Visual so their displayed width matches the source instruction rather than being capped at native pixel size.
- Persian/Arabic-script text has an independent configurable Visual font via `editor.visual_persian_font_family`; the shipped default is `Noto Naskh Arabic`, while Source and Latin Visual text keep their normal font.
- Large LaTeX documents use a cursor-centered virtual Visual window of approximately 20 rendered pages above and 20 below the active source position; scrolling near either edge recenters the window while preserving source-line mapping, cursor/viewport continuity, and untouched source outside the loaded window.
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
- In Source, bookmark ribbons are drawn in the logical line-number gutter; overlap with a line number is allowed so bookmark markers do not consume source-text width.
- Bookmark gutter clicks add/remove markers; bookmarks keep line/column and can be renamed or removed.
- Bookmark positions are persisted and relocate when content changes above them.
- The Bookmarks menu lists bookmarks across relevant files.
- **Bookmarks → Manage Bookmarks…** opens a popup listing bookmark name/anchor, file, line, and column across tracked files. The popup supports **Go To** and **Delete**, and deletions are written back through the existing persisted bookmark model.

## Live PDF Preview

- LuaLaTeX live rendering.
- Multi-pass bibliography/citation rendering when required.
- Last valid PDF remains visible during transient compile failures.
- PDF text remains selectable/copyable.
- Ctrl+mouse-wheel zoom and panning are supported.
- Zoom percentage/page information is available in the Preview controls.
- On a source-file switch, stale PDF page metadata is cleared immediately; page count is reported from the currently loaded PDF rather than a transient previous QML document.
- PDF export is available.
- **Fit Once** performs content-aware fit.
- **Auto Fit** fits the complete physical PDF page width once after the Preview width settles, then keeps that zoom unchanged through typing, PDF reloads, window/layout changes, and splitter moves. Toggle Auto Fit off/on to choose a new width; manual zoom disables Auto Fit.
- A normal left click on the rendered PDF performs **reverse SyncTeX** and moves the currently active LaTeX Source or Visual view to the corresponding source location.
- Source and Visual selections/caret targets are mirrored into the PDF search highlight, including Persian/Arabic-script text; the bridge writes the QML highlight target directly so the previous Arabic-script suppression no longer clears the active Preview highlight.
- Selection highlighting remains synchronized when switching between Source and Visual because both views map to the same canonical source locations.

### Permanent Preview toggle

The main window has one always-visible **Preview** toggle button in the **top-right corner of the menu bar**. The old Preview-panel × control is hidden. The button has a subtle light-gray background while Preview is open and returns to its normal appearance when Preview is closed; the menu action and corner button remain synchronized.

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
- `session.ini` — lightweight session state such as Preview, pins, pinned/open tab order, and Auto Fit.
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
src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/
```

The user-facing transfer artifact is:

```text
src/nd_mind_mirror/graphic/ipad/nd_graphic.zip
```

`nd_graphic.zip` is generated automatically from the visible editable source package when the Ubuntu application starts and Swift source is newer than the existing archive. The ZIP contains one top-level package directory named `nd_graphic.swiftpm`.

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

- The grid button beside the Color Picker opens the recent-color matrix as a floating popover anchored to the button, so opening the palette never pushes the canvas or status bar downward.
- The matrix displays only colors the user actually selected, newest first, up to the last 10 choices for the active color-capable tool.
- Colors are arranged in a compact five-column matrix.
- Selecting a matrix color moves it to the front of that tool's persisted history and automatically closes the popover.

#### Zoom and canvas information

A status strip remains visible immediately above the canvas and shows:

- current zoom percentage as a compact zoom menu;
- logical canvas width × height in pixels.

The zoom menu includes an explicit **100%** command that sets the underlying `UIScrollView` to logical scale `1.0` and recenters the canvas. Zoom updates live while pinching and after automatic fit/reset.

#### Two-finger Undo

A single tap with **two fingers** on the drawing area performs exactly one PencilKit Undo. Toolbar Undo/Redo buttons remain available as well.

#### Lasso selection, movement, and proportional resizing

Selecting **Lasso** keeps PencilKit's native lasso tool and also observes the same Apple Pencil lasso path without using newer `PKCanvasView.selection` or `PKStroke.id` APIs that are absent from the Swift Playgrounds SDK on some iPads. The selected editable strokes receive a thin rectangular frame with four small circular corner handles.

- Native PencilKit selection movement remains available.
- Drag any corner circle with one finger to scale only the selected strokes uniformly around the opposite corner.
- Width and height always use the same scale factor, so the selection remains proportional.
- A complete resize drag remains editable PencilKit data and is registered as one Undo/Redo operation.

#### Existing iPad workflow

- Pencil draws while direct finger gestures pan/pinch the outer scroll view.
- Highlighter uses marker rendering and its own recent-color history.
- Eraser uses vector erasing.
- Canvas presets and custom pixel dimensions are available.
- A background photo can be imported/removed.
- Drawing changes are autosaved through the Ubuntu/iPad bridge.
- New iPad graphics are created beside the active `.tex` file and use the same highest-index-plus-one `img_N.png` sequence as clipboard images; each managed PNG keeps its neighboring `.ndgraphic` sidecar.
- iPad insertion writes the complete `figure`/`\includegraphics` source block, while clicks inside an existing managed figure are treated as Update operations.
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
- `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/` — editable native iPad Swift Playgrounds source.
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

<!-- ND_IPAD_CURRENT_FEATURES_START -->
### Current iPad graphic and preview features

- The canonical editable Swift Playgrounds package is visible at `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/`; there is no separate hidden Swift source project.
- The native iPad graphic editor shows `source.tex > image.png` for the active managed figure.
- New managed iPad graphics use an A4 portrait canvas (1240 × 1754 px); the A4 portrait preset remains available for existing graphics.
- The iPad canvas has a visible 0.5 cm measurement grid plus numbered top and left centimeter rulers; the overlay is view-only and is never rendered into the saved PNG.
- Resizing the logical canvas preserves the current PencilKit drawing and background image instead of forcing a document reload.
- Editing an ordinary existing PNG on iPad preserves that PNG as the initial background when its sidecar has no PencilKit/background payload, so opening it no longer produces a blank white canvas.
- The recent-color grid opens as a floating popover anchored to its toolbar button, does not push the canvas, and closes automatically after a color is selected.
- The iPad zoom menu includes an explicit 100% command that sets the PencilKit viewport to logical zoom scale 1.0 and recenters the canvas.
- Navigator reveal operations avoid scrolling when the requested item is already visible, preserve pixel scroll offsets across proxy relayouts, and keep rename/drag viewport position stable.
- Visual mode accepts pasted clipboard images by routing them through the same managed-image insertion path as Source mode.
- Bookmark Go To waits for the target tab to become active before positioning the cursor.
- Preview edit highlighting keeps the last non-empty selection visible across Source/Visual/Preview switches.
- Delete confirmation focuses Yes for immediate keyboard confirmation while keeping the existing confirmation dialog.
- Idle memory compaction periodically releases unused Python/glibc heap pages without disabling editor features.
- Ubuntu uses one `Preview` button as the preview open/close toggle; the old × control is hidden and the active button has a light-gray background.
- Visual mode sizes `\includegraphics[width=N\textwidth|\linewidth|\columnwidth]` images from the visible text width and reapplies the size after layout/resize changes.
<!-- ND_IPAD_CURRENT_FEATURES_END -->
