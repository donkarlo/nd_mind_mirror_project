# nd_mind_mirror_project

`nd_mind_mirror_project` is an Ubuntu desktop writing/source-editing environment built with Python and PySide6, with LaTeX as its primary document format and a native SwiftUI/PencilKit iPad companion for drawing graphics directly into the document workflow.

The file on disk is always the canonical source. Visual editing, Preview wrappers, search indexes, rendered PDFs, UI state, and iPad drawing sidecars are derived from that source and must not silently rewrite a document merely to display it.

## Current desktop features

### Workspace and Navigator

- Configurable workspace/search root.
- Navigator follows the active tab and reveals/highlights the corresponding file.
- Navigator selection/reveal is single-pass and non-recentering so create, rename, drag/move, and active-tab reveals do not repeatedly jump the tree.
- Double-click opens editable files in Mind Mirror; PDFs/images can open in the system application.
- Navigator sort order is folders A–Z first, then files A–Z.
- Navigator right-click commands are grouped into **Open**, **Copy / Share**, **Create**, and **Manage** submenus.
- **Copy Absolute Path**, **Copy Dropbox Path**, file-name copy, GitHub URL copy/open, file-manager reveal, pinning, create, rename, delete, clipboard-image paste, and iPad graphic editing are supported.
- Ctrl/Shift multi-selection, multi-delete, and drag/move are supported.
- **F2** renames the selected Navigator file/folder.
- File/folder rename and drag/move remap open editor tabs and renderer paths; stale queued/running Preview work against the old path is stopped before the filesystem move.
- Rename reference updating is semantic rather than a global text replacement. Ordinary prose that merely contains the old filename/path is left unchanged.
- Reference rewriting recognizes actual file-reference contexts such as LaTeX `\input`, `\include`, `\subfile`, `\includegraphics`, `\includepdf`, bibliography resources, listings/verbatim input, `\inputminted`, local `\href`/`\url`, and supported document-link forms.
- Rename reference resolution supports all three path forms:
  1. paths relative to the file that contains the reference;
  2. paths relative to the configured Navigator/search root;
  3. absolute operating-system paths.
- Extensionless LaTeX references such as `\input{parts/chapter}` remain extensionless when the corresponding `.tex` file is renamed.
- Rename reference scanning uses the configured `search_ignore.yaml`; ignored files and ignored folders are not searched or rewritten.
- Navigator and Structure each provide explicit **Collapse** and **Restore Previous State** controls.

### Structure panel

- LaTeX hierarchy recognizes `\part`, `\chapter`, `\section`, `\subsection`, `\subsubsection`, `\paragraph`, and `\subparagraph`.
- YAML has a hierarchy-oriented Structure view.
- `Ctrl+Shift+F` auto-formats `.yaml`/`.yml` indentation using the configured editor indent size while preserving comments, key order, quoting, and block-scalar text.
- Clicking Structure moves the editor to the corresponding source location.
- Only the deepest active structure row is semantically highlighted.

### Fast file search

- Double Shift opens file search.
- Previous query is preserved and selected on reopen.
- Exact, prefix, substring, fuzzy, and hierarchical-path matching are supported.
- Up/Down and Enter support keyboard-only navigation.
- Search rebuilds against the current workspace so external Dropbox/git/terminal changes appear without restarting.
- Search and rename-reference scanning both use the configured `search_ignore.yaml` rules.

### Tabs and session

- Multiple editor tabs with a configurable maximum count.
- Tabs are shown in two rows: persistent pinned files above ordinary open files.
- Pinned and ordinary tabs can be drag-reordered and their order is persisted.
- `Ctrl+W` closes the current ordinary tab.
- `Ctrl+Tab` switches recent tabs.
- `Ctrl+Tab` and the Pinned/Open row dropdowns show the filename first, followed by smaller gray compact path context from the first folder under `repo` to the file's direct parent.
- Pinned paths follow renames and are removed when their targets are deleted.
- Open files, active file, cursor/scroll positions, bookmarks, splitter sizes, window layout, Preview state, and tab order are persisted.

## LaTeX editing

### Source mode

- LaTeX syntax highlighting.
- Configurable source font, size, line height, padding, tab size, indentation guides, soft wrapping, wrap marker, and incremental source-layout debounce.
- Logical line numbers count actual source lines rather than visual soft-wrap rows.
- Automatic Persian RTL/LTR line handling while keeping LaTeX command/setup lines usable.
- Persian/Arabic text uses the configured shared Persian font; the current default is `Noto Sans Arabic` so combining marks such as kasra remain visually separated from the base glyph.
- Smart Enter/list continuation.
- `Ctrl+Shift+F` formats LaTeX using the configured indentation hierarchy.
- `Ctrl+B` applies bold to the current selection.
- LaTeX completion and user snippets from `latex_shortcuts.yaml`.
- Clipboard and iPad image insertion use one collision-safe `img_N.png` sequence per folder.
- Image insertion keeps the complete LaTeX `figure`/`\includegraphics` source visible.
- Special-character insertion and `\iffalse … \fi` helpers are available.

### Visual mode

Visual is an editable projection of the same canonical LaTeX source; it is not a second document.

- Common prose, headings, lists, styling, highlighting, symbols, and graphics can be edited visually.
- Simple and nested `\frac{...}{...}` expressions receive a readable projection while raw LaTeX remains canonical.
- Graphic projection respects relative widths such as `\textwidth`, `\linewidth`, and `\columnwidth`.
- Persian/Arabic-script text uses the same configured Persian font as Source and preserves shaping/combining marks.
- Large documents use a cursor-centered virtual Visual render window while preserving source mapping and untouched source outside that window.
- Visual render-window size, estimated characters/lines per page, edge threshold, and re-window delay are configurable in `settings.yaml` so projection cost can be tuned for speed.
- Unsupported/raw LaTeX regions are preserved rather than silently discarded.

### Render-performance settings

Render-related limits that materially affect Source, Visual, or Preview work are exposed in `settings.yaml` rather than being fixed only in implementation code.

- Source: `source_layout_update_debounce_ms`, existing source update debounce values, and large-document thresholds control how aggressively source relayout/update work is coalesced.
- Visual: `visual_window_pages_above`, `visual_window_pages_below`, `visual_window_estimated_chars_per_page`, `visual_window_min_lines_per_page`, `visual_window_max_lines_per_page`, `visual_window_rewindow_delay_ms`, and `visual_window_scroll_edge_ratio` control the bounded Visual projection window.
- Preview: `min_zoom_percent` and `max_zoom_percent` bound PDF render scale. `fit_raster_width_px` and `fit_raster_sample_step_px` control the low-resolution content probe used by the explicit **Fit** command; Auto Fit keeps its separate settled-width behavior.

### Undo and Redo

- `Ctrl+Z` → Undo
- `Ctrl+Y` → Redo
- `Ctrl+Shift+Z` → Redo

The controller handles Qt standard-key matching and German/Swiss QWERTZ layouts.

## Bookmarks

- Source and Visual share one persisted bookmark model.
- Source bookmark ribbons are drawn in the logical line-number gutter.
- A bookmark created while text is selected stores the selected source range together with readable selected text; ordinary bookmarks continue to work as line anchors.
- Clicking an existing bookmark restores its saved selection in both Source and Visual and requests the corresponding Preview text highlight; clicking an empty gutter location creates a bookmark, while rename/remove remain available from the bookmark context menu.
- Bookmark labels prefer a custom name, then the saved selected text, then the source anchor, so the Bookmarks menu and **Manage Bookmarks…** show what was highlighted.
- Bookmarks keep line/column information, can be renamed/removed, are persisted, and relocate when preceding content changes. Saved selection endpoints move with the relocated bookmark anchor.
- The Bookmarks menu lists bookmarks across files.
- **Bookmarks → Manage Bookmarks…** provides Go To and Delete operations and preserves the saved selection payload when navigating.

## Live PDF Preview

- LuaLaTeX live rendering.
- Multi-pass bibliography/citation rendering when required.
- The last valid PDF remains visible during transient compile failures.
- PDF text remains selectable/copyable.
- Ctrl+mouse-wheel zoom and panning are supported.
- Zoom percentage and page information are displayed.
- PDF export is available.
- **Fit Once** performs content-aware fit.
- **Auto Fit** fits the page to the settled Preview width without continuously changing zoom while typing.
- Normal left-click on the PDF performs reverse SyncTeX and moves Source/Visual to the corresponding source location.
- Source/Visual cursor movement drives source-position synchronization/scrolling in Preview; when there is no explicit selection, the mapped location can be shown by the persistent Preview caret overlay.
- An explicit Source/Visual selection requests a PDF text highlight, including a range restored from a selection-aware bookmark.
- Preview zoom limits and the explicit Fit command's low-resolution content-probe size are configurable in `settings.yaml`.

### Preview toggle and layout

- Preview has an always-visible toggle in the top-right menu-bar area.
- Preview visibility, window geometry, and splitter/pane sizes are persisted.
- Re-enabling Preview restores the last valid visible pane widths instead of persisting a collapsed width.

## Keyboard shortcut settings

Application accelerators are separate from LaTeX snippet completion.

Shipped defaults:

```text
src/nd_mind_mirror/core/settings/defaults/keyboard_shortcuts.yaml
```

Persistent user copy:

```text
/home/donkarlo/Dropbox/repo/data/nd_mind_mirror_project/keyboard_shortcuts.yaml
```

**Settings → Keyboard Shortcuts…** validates and applies shortcut changes at runtime.

`latex_shortcuts.yaml` remains dedicated to LaTeX snippet/completion expansion.

## Persistent application data

Persistent Mind Mirror settings/state belong under:

```text
/home/donkarlo/Dropbox/repo/data/nd_mind_mirror_project/
```

Equivalent Dropbox/repository-relative path:

```text
/repo/data/nd_mind_mirror_project/
```

Important files include:

- `settings.yaml` — application/UI behavior, including Source/Visual/Preview render-performance knobs and the shared Persian font;
- `keyboard_shortcuts.yaml` — application accelerators;
- `latex_shortcuts.yaml` — LaTeX snippets/completions;
- `search_ignore.yaml` — search/Navigator/rename-scan ignore rules;
- `session.ini` — lightweight session state;
- `ui_state.json` — window/splitter/navigation state;
- `templates/latex_preview_template.tex` — article/fragment Preview wrapper;
- `templates/latex_preview_beamer_template.tex` — Beamer Preview wrapper.

Existing user values win when shipped defaults/schema are merged.

## Native iPad drawing workflow

The iPad companion remains part of this repository. Editable Swift source is stored at:

```text
src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/
```

The canonical transfer artifact is:

```text
src/nd_mind_mirror/graphic/ipad/nd_graphic.zip
```

There is no second root-level copy of `nd_graphic.zip` in the project. The canonical ZIP above is generated from the editable Swift package when needed.

### iPad drawing controls

- Pencil, Highlighter, Eraser, and Lasso.
- Independent recent-color history for Pencil and Highlighter.
- Persistent last stroke color and thickness.
- Thickness range 1–24.
- Floating recent-color matrix.
- Zoom percentage and logical canvas dimensions.
- Explicit 100% zoom command.
- Two-finger tap Undo.
- PencilKit lasso movement plus proportional corner-handle resizing.
- Finger pan/pinch with Pencil drawing.
- Background photo import/removal.
- Editable canvas sizes/presets.
- Autosave through the Ubuntu/iPad bridge.
- Managed PNG graphics keep neighboring `.ndgraphic` sidecars.
- Existing managed figures can be updated from the iPad without replacing the surrounding LaTeX workflow.

## Running on Ubuntu

From the project root:

```bash
cd /home/donkarlo/Dropbox/repo/nd_mind_mirror_project
python nd_mind_mirror_project
```

or:

```bash
./nd_mind_mirror_project
```

The startup path refreshes the iPad transfer package before constructing the Qt window. `Ctrl+C` in the launching terminal requests a clean application shutdown.

## Project layout

- `src/nd_mind_mirror/core/` — document, LaTeX, search, settings, rendering, and workspace logic.
- `src/nd_mind_mirror/ui/` — Qt editors, panels, Preview, search UI, and main-window controllers.
- `src/nd_mind_mirror/graphic/` — desktop/iPad graphic workflow and bridge.
- `src/nd_mind_mirror/graphic/ipad/` — editable Swift package and canonical transfer ZIP.
- `tests/` — automated tests.
- `tools/` — development/maintenance utilities.
- `/repo/data/nd_mind_mirror_project/` — persistent user settings and session/UI state.

## Repository hygiene

- Canonical source files are edited directly; backup/pre-change/duplicate implementation files are not part of the design.
- Generated Python `__pycache__` directories are not kept in the Dropbox project tree.
- Temporary files created by atomic/runtime operations must be cleaned up after use.
- `search_ignore.yaml` is the shared ignore policy for workspace searching and rename-reference scanning.

## Code documentation rule

New and modified implementation files begin with a concise module description. New and modified classes/functions should have concise documentation describing responsibility. Legacy files are brought under this rule as they are touched rather than being mass-rewritten without a functional reason.

<!-- ND_IPAD_CURRENT_FEATURES_START -->
### Current iPad graphic and preview features

- LaTeX Structure includes `\includegraphics` entries. A graphic inside a `figure` uses its `\caption` text when present; otherwise Structure shows the image filename.
- Preview Auto Fit fits the complete physical PDF page width once for a newly opened LaTeX document, keeps that zoom fixed during typing/live reloads, and never raster-scans pages to calculate fit.
- Preview wheel/touchpad scrolling is handled directly by the PDF viewport. Source/Visual selection highlighting is applied only after the current SyncTeX mapping is ready, so highlighting does not control wheel scrolling or use stale PDF coordinates.
- Live Preview cancels an obsolete LaTeX compile after the normal typing debounce and immediately renders the newest editor generation instead of waiting indefinitely for an old compile.
- The canonical editable Swift Playgrounds package is `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/`; startup removes numbered `nd_graphic (N).swiftpm` transfer/conflict copies and never treats them as source.
- New Ubuntu `Insert image in iPad` graphics reuse the last edited iPad canvas size; both new and existing graphics open at logical 100% with the canvas aligned to the top-left viewport. Two-finger pinch zoom remains enabled after opening.
- Starting the iPad app or reconnecting the bridge does not reopen a stale previous insert/update request and does not create a new blank graphic. Opening an insert request no longer performs an eager blank save before the user changes the canvas.
- Existing update backgrounds are preserved during ordinary iPad autosaves even if SwiftUI briefly exposes a nil background while a document is loading, preventing a white canvas from overwriting the real PNG.
- Pencil and Highlighter toolbar buttons each open their own settings popup for color, thickness, and transparency. The popup can add a new tool immediately after the current tool, change the current tool, switch among same-kind saved tools, or delete one; the main toolbar no longer duplicates those three setting controls.
- JPG/JPEG and PNG `\includegraphics` targets can both be opened in iPad Edit mode; existing image edits use the native pixel size and save back in the target image format.
- Photos selected on iPad are inserted as editable image objects rather than replacing the document background. Image objects keep aspect ratio, start at a bounded top-left size, can be selected by finger or Apple Pencil Lasso, moved, proportionally resized, deleted, and support Undo/Redo for insert/delete/move/resize.
- Editable image-object metadata is stored in the graphic sidecar and returned by the bridge on later Edit operations, while the Ubuntu/base background remains a separate layer. The saved PNG composites base background, image objects, and PencilKit strokes.
- Lasso stroke selection keeps four proportional resize handles plus a smaller pale-gray move handle. Resizing changes geometry without scaling stroke thickness, and transformed stroke points are tested in canvas coordinates so moving a selection cannot silently move a different stroke.
- Canvas width and height are not capped at the former 8192 px limit. Existing PencilKit strokes define the minimum safe canvas dimensions, and the iPad reports when a requested canvas would clip the graphic.
- Custom canvas numeric fields request the ASCII-capable number pad so canvas dimensions are entered with English digits.
- The iPad measurement Grid and centimeter Rulers have independent toolbar switches and remain view-only overlays.
- PencilKit internal content geometry is synchronized with logical canvas resizing so the full A4 portrait drawing area accepts Apple Pencil input.
- Tapping the active source/image identity opens the ten most recently edited graphics and can request any of them from the Ubuntu bridge.
- The current canvas dimensions are shown at the top of the canvas-size menu rather than permanently occupying the status bar.
- `Ctrl+Shift+Delete` deletes the file represented by the current editor tab, using the normal delete confirmation workflow.
- Pinned tabs have close buttons; closing one explicitly unpins it and closes the file.
- Preview Lock prevents Source/Visual synchronization from moving the PDF and preserves the current zoom/scroll view through live reloads.
- Preview Extend hides Navigator and Source/Visual panes so Preview alone fills the main window, and restores the previous pane visibility when toggled off.
- Auto Fit no longer performs delayed multi-pass zoom/recenter restoration after each reload; QML preserves the view directly, reducing preview jumps and UI stalls.
- Visual mode accepts pasted clipboard images through the same managed-image insertion workflow as Source mode, while explicit LaTeX image widths continue to track the visible text width.
- Folder hits in Double-Shift Search close Search and are revealed, scrolled to, and highlighted in the main Navigator.
- Small LaTeX files begin their first Preview compile immediately; Auto Fit no longer raster-scans PDF pages on the GUI thread.
- Preview edit synchronization renders only the current/nearest search result as the visible highlight even when the same phrase occurs more than once.
- `latex_shortcuts.yaml` is excluded from periodic autosave and is validated as a non-empty shortcut mapping before an explicit save can overwrite it.
- Navigator selection, rename, drag, bookmarks, autosave, and idle memory compaction remain enabled.
<!-- ND_IPAD_CURRENT_FEATURES_END -->
