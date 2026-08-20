# nd_mind_mirror_project

`nd_mind_mirror_project` is a desktop writing and source-editing environment for Ubuntu built with Python and PySide6. It is designed around LaTeX documents, but it can also open and edit Markdown, YAML, plain text, source code, configuration files, and other text-based files inside one workspace.

The application keeps the original files as the source of truth. Visual editing, preview documents, temporary LaTeX wrappers, search indexes, and UI state are derived from those files and do not require rewriting the source merely to display it.

## Main features

### Workspace and File Navigator

- Configurable workspace root from `settings.yaml`.
- Tree-based File Navigator for files and directories.
- Navigator follows the active editor tab and reveals/highlights its file.
- Double-click opens editable text files inside the application.
- PDF and image files can be opened with the Ubuntu default application.
- Right-click **Open in Files** reveals a file or directory in the Ubuntu file manager.
- If the clipboard currently contains an image, the first click on a folder saves it there as `img.jpg`; later copied images use `img_2.jpg`, `img_3.jpg`, and so on. `Ctrl+V` and **Paste Clipboard Image Here** are also supported.
- Drag-and-drop can move files and directories inside the workspace.
- When a file is moved, textual relative/absolute references under the configured workspace can be updated automatically.
- `search_ignore.yaml` provides gitignore-like rules for search and workspace operations.
- Navigator and Structure panel sizes are persisted between sessions.

### Fast file search

- Double Shift opens the file search window.
- The previous query is preserved and automatically selected when search is reopened, so typing immediately replaces it.
- Exact, prefix, substring, fuzzy, and hierarchical path matching are supported.
- Keyboard navigation with Up/Down and Enter is supported.
- Search results open through the same file dispatcher as the Navigator.
- Opening search rebuilds the workspace index, so files/folders added, removed, or moved externally (Dropbox, git, terminal, another editor) are reflected without restarting Mind Mirror.

### Tabs and session restore

- Multiple editor tabs with a configurable maximum tab count.
- `Ctrl+W` closes the current tab.
- `Ctrl+Tab` provides recent-tab switching.
- Open files, active file, cursor position, scroll position, window geometry, splitter sizes, and bookmarks are persisted.
- Externally modified open files are detected and reloaded while preserving the current view as far as possible.

## LaTeX editing

### Source mode

- LaTeX syntax highlighting.
- Configurable font size, line height, tab size, indentation guides, and content padding.
- Soft wrapping with hanging indentation.
- Configurable per-line RTL/LTR layout.
- Smart Enter behavior.
- Inside `itemize`, `enumerate`, and `description`, pressing Enter after an existing `\item` creates the next sibling `\item` automatically.
- `Ctrl+Shift+F` formats LaTeX using the configured tab/indent size.
- `Ctrl+B` wraps the current selection in `\textbf{...}`.
- Toolbar controls for bold, italic, text color, highlight, headings, and lists.
- LaTeX command completion.
- User-defined snippets in `latex_shortcuts.yaml`.
- Pasting an image can create a relative LaTeX figure reference next to the source file.

### Visual LaTeX mode

LaTeX files can switch between **Source** and **Visual** modes. Source remains canonical; Visual is an editable projection of supported LaTeX structures.

Visual mode supports:

- Paragraph editing.
- Part/chapter/section/subsection/subsubsection/paragraph/subparagraph headings.
- Nested `itemize` and `enumerate` lists.
- Bold, italic, text colors, and highlights.
- Common inline mathematical symbols such as Greek letters while preserving their LaTeX representation.
- Raw LaTeX blocks for unsupported constructs so source is not silently discarded.
- Editing the LaTeX represented by a selected Visual range through **Update selected LaTeX source…**.
- A Raw LaTeX mini source editor with LaTeX completion and `latex_shortcuts.yaml` snippets.
- Independent Visual font size, line height, and padding settings.
- Coalesced Visual-to-source updates for large documents so ordinary typing does not serialize the complete document after every key press.

### Source / Visual cursor and selection synchronization

Source and Visual represent the same canonical source position.

- Switching Source → Visual keeps the cursor at the corresponding word/location.
- Switching Visual → Source maps the cursor back to the corresponding source position.
- A text selection is mapped to the other representation where possible.
- Structure navigation uses the currently visible mode.
- Visual scrolling and cursor movement participate in preview synchronization just like Source mode.

## Persian and RTL support

LaTeX source and Visual mode support Persian/Arabic right-to-left writing.

- Ordinary Persian prose can be laid out RTL automatically.
- LaTeX command/setup lines remain LTR where appropriate.
- Mixed Persian/English paragraphs use Qt bidirectional text layout.
- Visual paragraphs receive explicit RTL block direction so mouse hit-testing and caret placement follow the displayed Persian text.
- RTL behavior is configurable with `editor.latex_text_direction` and `editor.latex_rtl_persian_ratio`.
- Persian preview documents that already configure `polyglossia`, `xepersian`, or a Persian font setup are not rewritten merely for preview.

## Structure panel

For LaTeX, the Structure panel recognizes the normal section hierarchy:

- `\part`
- `\chapter`
- `\section`
- `\subsection`
- `\subsubsection`
- `\paragraph`
- `\subparagraph`

Clicking a Structure item moves the active Source or Visual editor to the corresponding location.

Included/input LaTeX fragments are resolved for preview without editing the fragment on disk. Fragment preview hierarchy can be derived from the surrounding document while the original `\input`/`\include` source files remain unchanged.

YAML files also receive a hierarchy-oriented Structure view.

## Bookmarks

LaTeX Source and Visual mode share one bookmark model.

- Click the thin vertical bookmark gutter to add or remove a bookmark.
- Bookmarks are drawn as subtle light-blue circles.
- Bookmarks store both source line and column, so they can distinguish positions inside long wrapped paragraphs.
- Right-click a bookmark marker to rename or remove it.
- Bookmark names and positions are saved automatically.
- The **Bookmarks** menu lists bookmarks across open and previously bookmarked files.
- Clicking a bookmark opens/reveals its file and moves Source or Visual to the stored location.
- Bookmark anchors relocate when lines are inserted or removed above them.

## Live LaTeX PDF preview

- LuaLaTeX-based live preview.
- Multi-pass rendering for citations/bibliographies when needed.
- BibTeX/Biber-aware rendering.
- The last valid PDF stays visible during transient LaTeX errors while typing.
- PDF text remains selectable and copyable.
- `Ctrl+Mouse Wheel` zooms around the pointer position.
- Middle-drag or Ctrl+left-drag pans the PDF.
- Zoom percentage and page number are displayed.
- PDF export is available from the preview toolbar.
- Horizontal and vertical scrollbars stay visible whenever the rendered document is larger than the Preview viewport.

### Fit mode

Fit is reading-oriented rather than physical-page-oriented:

- The widest rendered content is fitted to the configured percentage of Preview width.
- Large unused white A4 side margins do not determine the scale when content bounds can be detected.
- Vertical page height is not a Fit constraint.
- Fit stays active across live re-renders and Source/Visual switching until the user manually zooms.
- Source/Visual cursor synchronization preserves horizontal centering while Fit is active.

### Source-to-preview synchronization

- Source and Visual cursor movement can be mapped to the corresponding PDF location through SyncTeX.
- Scrolling either editing representation updates the preview location.
- The current editing phrase can be sent to Qt PDF's native text-search overlay after a short debounce, giving a lightweight preview highlight without adding another PDF renderer.
- The edit-location highlight can be disabled in `settings.yaml`.

## Apple Pencil graphic workflow

Mind Mirror includes a **native iPad companion app** written with SwiftUI and PencilKit. It is delivered as a Swift Playgrounds app package at:

```text
src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm
```

A Mac is not required. Install Apple's free **Swift Playgrounds** app on the iPad, copy `nd_graphic.swiftpm` to **On My iPad** or iCloud Drive in the Files app, then tap the package and run **ND Graphic**. Swift Playgrounds compiles and runs the app natively on the iPad. The older browser client remains under `src/nd_mind_mirror/graphic/web/` only as a fallback.

From either LaTeX Source or Visual mode, right-click and choose **Insert / update image in iPad…**:

- On a new location, Mind Mirror creates a PNG plus an editable `.ndgraphic` sidecar in the **same directory as the active `.tex` file** and inserts a complete `figure` block using `\includegraphics[width=0.9\textwidth]{...}`.
- On an existing Mind Mirror PNG reference, the same command opens that graphic for continued editing instead of creating another one.
- The Ubuntu graphic bridge pushes the requested document to the native iPad app immediately over WebSocket.
- The drawing surface uses PencilKit's **pencil** ink rather than a ballpoint/pen ink. Apple Pencil pressure and tilt are handled by PencilKit, so stronger pressure naturally makes the stroke darker and somewhat broader.
- Pencil color and base width are selectable. Eraser, Undo, Redo, and Clear are included.
- Drawing changes are autosaved after a short debounce. The bridge atomically updates both the editable `.ndgraphic` PencilKit state and its PNG.
- Because LaTeX includes the PNG directly, Visual mode and the live PDF preview refresh when the bridge rewrites the image. No TikZ conversion is involved in the active graphic workflow.
- The iPad client uses Network.framework WebSocket (`NWConnection` + `NWProtocolWebSocket`) for the direct LAN `ws://` bridge, avoiding URLSession App Transport Security blocking on local clear-text WebSockets.
- Dropbox can continue to synchronize the real PNG/sidecar files, while WebSocket is used for low-latency live editing.

Graphic settings include:

```yaml
graphic:
  directory: .
  latex_width_ratio: 0.90
  canvas_width: 1600
  canvas_height: 1000
  bridge_http_url: http://127.0.0.1:8766
  bridge_token: ""
```

Run the Ubuntu bridge from the project root:

```bash
TOKEN='choose-a-token' ./nd_graphic_bridge
```

Find the Ubuntu LAN address:

```bash
hostname -I
```

In the native iPad app, set the connection to:

```text
ws://UBUNTU_IP:8766/ws
```

and enter the same token. Both devices must be on the same local network. The app remembers the connection settings.

The previous Xcode project is archived under `src/nd_mind_mirror/graphic/native_future/`; it is not required for the Ubuntu+iPad workflow. The experimental drawing-to-TikZ code remains parked under `src/nd_mind_mirror/graphic/tikz_future/` for later development.

## Markdown and other text files

### Markdown

- `.md` and `.markdown` files open in the internal editor.
- Markdown receives a rendered preview.
- Relative Markdown images are resolved from the Markdown file directory.

### YAML

- YAML syntax highlighting.
- Smart indentation based on the configured tab size.
- YAML Structure hierarchy.

### Other text/source files

The editor attempts to open any decodable text file internally. Pygments is used for syntax highlighting when an appropriate lexer can be determined from the filename/extension. This includes common programming languages, configuration files, shell scripts, JSON/TOML/INI, SQL, HTML/CSS, BibTeX, logs, and plain text.

`.txt` files are editable but intentionally have no rendered preview.

## Find and replace

- `Ctrl+F` opens Find for the current tab.
- `Ctrl+R` opens Find/Replace.
- Matches are highlighted in the editor.
- Next/previous navigation and replace-current are available.
- Escape closes the search bar and clears editor match highlighting.

## Editor key behavior

- In any Source editor, when there is no selection, `Ctrl+C` copies the entire current line, `Ctrl+X` cuts the entire current line, and `Ctrl+D` duplicates the entire current line.
- `Ctrl+Z` is Undo and `Ctrl+Y` (or `Ctrl+Shift+Z`) is Redo in Source editors; Visual mode also explicitly supports the same Undo/Redo keys.
- Visual mode displays ordinary characters such as `_` and `"`, while serialization escapes them as `\_` and `\"` in canonical LaTeX source.
- The navigator context menu provides **Copy Absolute Path** and **Copy File Name** for both files and directories.

## Settings

Open **Settings → Edit settings.yaml** to edit application settings inside the editor. Saving the file alone does not apply it; press the **Apply** button shown for `settings.yaml`.

Important editor settings include:

```yaml
editor:
  font_size: 16
  line_height_percent: 200

  visual_font_size: 16
  visual_line_height_percent: 200

  source_padding_top: 10
  source_padding_left: 10
  source_padding_right: 10

  visual_padding_top: 14
  visual_padding_left: 16
  visual_padding_right: 16

  tab_size: 4

  visual_update_debounce_ms: 180
  visual_large_document_threshold_chars: 120000
  visual_large_document_debounce_ms: 650

  latex_text_direction: auto
  latex_rtl_persian_ratio: 0.35
```

Preview synchronization/highlight settings include:

```yaml
preview:
  auto_fit_on_open: true
  fit_width_percent: 95
  cursor_sync_enabled: true
  cursor_sync_debounce_ms: 120
  edit_location_highlight_enabled: true
  edit_location_highlight_debounce_ms: 220
```

## Running on Ubuntu

Create/activate a Python environment containing the project dependencies and run the launcher from the project root:

```bash
./nd_mind_mirror_project
```

or install the project in the environment and run its Python entry point according to your environment setup.

The project requires Python 3.10+ and uses:

- PySide6 / Qt 6.8+
- PyYAML
- Pygments
- a working LaTeX installation for PDF rendering (LuaLaTeX and the packages used by your documents)

## Project files

- `~/Desktop/repo/data/nd_mind_mirror_project/settings.yaml` — application behavior and UI settings.
- `~/Desktop/repo/data/nd_mind_mirror_project/latex_shortcuts.yaml` — user LaTeX snippets.
- `~/Desktop/repo/data/nd_mind_mirror_project/search_ignore.yaml` — workspace/search ignore rules.
- `~/Desktop/repo/data/nd_mind_mirror_project/templates/latex_preview_template.tex` — editable article/new-file preview template.
- `~/Desktop/repo/data/nd_mind_mirror_project/templates/latex_preview_beamer_template.tex` — editable Beamer/new-file preview template.
- `src/nd_mind_mirror/` — application source.
- `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/` — native SwiftUI/PencilKit iPad companion app, runnable directly in Swift Playgrounds.
- `src/nd_mind_mirror/graphic/bridge/` — Ubuntu HTTP/WebSocket server for the native iPad app and live autosave.
- `src/nd_mind_mirror/graphic/web/` — optional browser fallback client.
- `tests/` — automated tests.

Temporary preview documents are generated for rendering and do not require changing the original LaTeX fragment merely to make it compilable as a standalone preview.

### v0.30.1 startup stability

- The Ubuntu taskbar icon is now a packaged static PNG. Runtime QPainter-based icon generation was removed from startup so desktop integration cannot destabilize the Qt event loop.
- Native crash diagnostics are appended to `~/.local/state/nd_mind_mirror_project/crash.log` while ordinary errors still appear in the terminal.

### v0.30.2 Ubuntu 20.04 launcher stability

- `./nd_mind_mirror_project` now automatically re-executes with `~/phd-venv/bin/python` when that interpreter exists, so reopening a terminal or rebooting Ubuntu cannot silently launch the Qt application with a different system Python.
- Override the interpreter with `ND_MIND_MIRROR_PYTHON=/absolute/path/to/python` when needed.
- Desktop-file installation is no longer performed during GUI startup; taskbar integration is kept out of the critical startup path.
- Startup/lifetime diagnostics are appended to `~/.local/state/nd_mind_mirror_project/startup.log`. Native fatal-signal diagnostics remain in `crash.log`.

### v0.30.3 preview safety for malformed/sparse LaTeX documents

- Fit-to-preview is now hard-clamped to a safe 20%-500% range, including QML auto-fit paths.
- Sparse/near-empty pages no longer fit to a tiny page-number/glyph bounding box; they fall back to physical page width.
- A stale or invalid zoom is sanitized before every PDF reload, preventing giant Qt Quick PDF texture allocations.
- Files containing multiple complete standalone LaTeX documents are previewed using the most substantial complete document, without modifying the source file; leading line offsets are preserved for SyncTeX.

### v0.31.0 persistent settings, stable/faster preview, and LaTeX templates

- All live user configuration/state is stored under `~/Desktop/repo/data/nd_mind_mirror_project/` instead of the replaceable application directory. This includes `settings.yaml`, `latex_shortcuts.yaml`, `search_ignore.yaml`, editable LaTeX templates, `session.ini`, and `ui_state.json`.
- On first use, legacy YAML values are migrated when available. On later releases, new schema keys/default ignore rules are merged into the existing files while user values win. Existing template files are never overwritten.
- Source font size is explicitly `editor.source_font_size`; edit `settings.yaml` and press **Apply** to apply it to all open source editors.
- **New LaTeX File...** asks which configured template to use. The initial choices are Article and Beamer; more can be added under `new_latex_file.templates`.
- Live PDF updates no longer recompute content-aware Fit on every successful render. Fit is calculated once for a newly opened source (or when the user presses Fit), then zoom/scroll are preserved across live reloads.
- Cursor SyncTeX waits until the PDF generation matches the current source, avoiding jumps caused by mapping a new cursor location against an old PDF.
- Preview status/scrollbar housekeeping is less aggressive, and the default preview debounce is 120 ms (420 ms for large documents).
