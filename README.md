# nd_mind_mirror_project

`nd_mind_mirror_project` is an Ubuntu desktop writing/source-editing environment built with Python and PySide6, with LaTeX as its primary document format and a native SwiftUI/PencilKit iPad companion for drawing graphics directly into the document workflow.

The file on disk is always the canonical source. Visual editing, Preview wrappers, search indexes, rendered PDFs, UI state, and iPad drawing sidecars are derived from that source and must not silently rewrite a document merely to display it.

This README describes the active functional project: desktop Python/PySide6 source, the canonical Swift Playgrounds iPad package, settings/templates, launchers, tests, tools, and release documentation. Generated `.git` objects, `__pycache__`, compiled PDFs/images/ZIP payloads, and archived migration copies are artifacts rather than independent runtime features.

## Current desktop features

### Workspace and Navigator

- Configurable workspace/search root.
- Navigator follows the active tab and reveals/highlights the corresponding file.
- Every normal left-click in Source or Visual recenters the represented file vertically and horizontally in Navigator with the persistent blue/white selection. Clicking an `\includegraphics`/`\includepdf` reference in Source, or a rendered graphic in Visual, selects and centers that referenced image/PDF file instead of the surrounding `.tex` file.
- Create, rename, drag/move, and active-tab reveals remain deterministic; Source/Visual clicks intentionally force a centered reveal even when the same Navigator row is already selected.
- Double-click opens editable files in Mind Mirror; PDFs/images can open in the system application.
- Navigator sort order is folders A–Z first, then files A–Z.
- Navigator child indentation is independently configurable through `ui.navigator_child_indent_width` in `settings.yaml`; changing it through **Reload settings.yaml** updates the tree without restarting. Folder entries use a modern light-blue folder icon, configurable through `ui.navigator_folder_color`.
- Navigator right-click commands are grouped into **Open**, **Copy / Share**, **Create**, and **Manage** submenus.
- **Copy Absolute Path**, **Copy from Default Path**, file-name copy, GitHub URL copy/open, file-manager reveal, pinning, create, rename, delete, clipboard-image paste, and iPad graphic editing are supported. **Copy from Default Path** copies `/path/to/item` relative to `search.default_path`, and supports multi-selection with one path per line.
- Ctrl-click cherry-picks Navigator rows and Shift-click selects a contiguous range; file/folder Copy, Cut, Delete, and grouped operations use the complete top-level selected set.
- Navigator file/folder **Copy / Cut / Paste** are available both from the right-click menu and from `Ctrl+C` / `Ctrl+X` / `Ctrl+V`.
- Navigator clipboard keyboard handling is owned directly by a tree key-event filter rather than competing `QShortcut` objects: `Ctrl+C` stores the current selected set, `Ctrl+X` stores it for move, and `Ctrl+V` pastes it into the selected folder (or the selected file's parent). If there is no internal file/folder clipboard, `Ctrl+V` is deliberately left available to the existing clipboard-image paste workflow.
- A copy preserves files/folders recursively; a cut/paste uses the background workspace move/reference-maintenance pipeline.
- If a destination already contains the same file/folder name, Paste proposes collision-safe names such as `name_0`, `name_1`, ... while preserving file extensions and allows an explicit alternate name.
- Multi-delete and drag/move remain available independently of the clipboard workflow.
- **F2** renames the selected Navigator file/folder.
- File/folder rename and drag/move remap open editor tabs and renderer paths; stale queued/running Preview work against the old path is stopped before the filesystem move.
- After a successful background rename/move, Navigator explicitly refreshes its `QFileSystemModel` cache/watcher and restores expansion/selection, so an old filename cannot remain visible after the filesystem has already changed.
- Externally deleted open files are detected by the periodic disk synchronizer. Navigator refreshes its filesystem-model cache immediately, and autosave refuses to recreate a path that has disappeared from disk.
- Managed PNG/JPG/JPEG graphics move or rename together with their neighboring `.ndgraphic` sidecar. If that graphic is active in the iPad bridge, the bridge remaps its live identity to the new path/name without reloading the active iPad canvas or resetting Undo/Redo history.
- Deleting a managed raster through the Navigator also deletes its neighboring `.ndgraphic` companion so the project does not leave a stale editable sidecar behind.
- Rename/move detects a stale orphan destination sidecar: when the destination raster no longer exists but its old `.ndgraphic` remains and belongs to that managed graphic workflow, the new raster/sidecar pair can safely replace the orphan instead of failing with an `already exists` collision.
- Existing occurrence/preflight checks and delete-reference dialogs remain synchronous before a confirmed operation. After confirmation, repository-wide rename/move/delete reference maintenance runs in a separate child process so the editor stays responsive; consecutive operations are batched, open editor buffers are excluded from worker writes, and search-index refreshes are coalesced after the batch.
- Rename reference updating is semantic rather than a global text replacement. Ordinary prose that merely contains the old filename/path is left unchanged.
- Reference rewriting recognizes actual file-reference contexts such as LaTeX `\input`, `\include`, `\subfile`, `\includegraphics`, `\includepdf`, bibliography resources, listings/verbatim input, `\inputminted`, local `\href`/`\url`, and supported document-link forms.
- Local reference resolution uses one shared three-mode policy for Ctrl+B navigation, Preview/recursive input resolution, delete occurrence search/removal, and rename/move reference rewriting:
  1. a token **without** a leading `/` is resolved only relative to the file containing the reference;
  2. a token **with** a leading `/` is first resolved relative to `search.default_path` after removing that leading slash;
  3. if the default-rooted candidate does not exist, the same leading-slash token is tried as a real operating-system absolute path.
- With `search.default_path: /home/donkarlo/Dropbox/repo`, the portable reference to `/home/donkarlo/Dropbox/repo/nd_math_project/file.tex` is `/nd_math_project/file.tex`; `/repo/...` has no special alias semantics.
- The shared policy applies to LaTeX source/input files, images, PDFs, bibliography resources, local href/url targets, listings/verbatim inputs, and inputminted targets.
- Extensionless LaTeX references such as `\input{parts/chapter}` remain extensionless when the corresponding `.tex` file is renamed.
- Rename reference scanning uses the configured `search_ignore.yaml`; ignored files and ignored folders are not searched or rewritten.
- Navigator and Structure each provide explicit **Collapse** and **Restore Previous State** controls.

### Structure panel

- LaTeX hierarchy recognizes `\part`, `\chapter`, `\section`, `\subsection`, `\subsubsection`, `\paragraph`, and `\subparagraph`.
- The **Search heading titles (typos OK)** field filters Structure as you type, including case-insensitive matches and small spelling mistakes in Latin/Persian titles. Matches retain their ancestors as navigable context; press Enter to navigate to the first match, and clear the field to restore the unfiltered tree. Filtering never changes LaTeX text or reruns LaTeX compilation.
- Extended hierarchy parsing supports the preamble's `deep_structure.tex` commands `\DeepSection{1..10}{Title}`, `\ndsectionfour` through `\ndsectionten`, and the `\subsubsubsection` aliases defined by `extra_subsections.tex` (through level 10). Deep headings appear with their true nesting depth; the parser also retains figure/table descendants under them. Promotion/demotion beyond the standard heading model remains disabled to prevent invalid source rewrites.
- Structure also lists caption-aware `figure` graphics and `table`/`table*`/`longtable` content, plus standalone `tabular`, `tabular*`, and `tabularx` environments.
- LaTeX Structure rows are draggable. Dropping before/after another row reorders the complete canonical source span; dropping a heading onto another heading reparents the dragged subtree and shifts its heading levels consistently.
- Right-click a LaTeX heading in Structure for **Increase Hierarchy** (promote one level) or **Decrease Hierarchy** (demote one level). The selected heading and every nested heading move together; invalid moves at document-class depth boundaries are disabled, and non-heading leaves are unchanged.
- Figure/image and table rows move their complete owning environment instead of moving only `\includegraphics`, `\caption`, or `tabular` fragments.
- YAML has a hierarchy-oriented Structure view.
- `Ctrl+Shift+F` auto-formats `.yaml`/`.yml` indentation using the configured editor indent size while preserving comments, key order, quoting, and block-scalar text.
- Clicking Structure moves the editor to the corresponding source location.
- Only the deepest active structure row is semantically highlighted.

### Workspace search

- The Search window has two tabs: **Files & Folders** and **Text in Files**. Double Shift always opens **Files & Folders**.
- Both tabs have a read-only recursive search-root field backed by a native folder chooser; the initial root is `search.default_path`.
- The last query and root are persisted independently for each tab in the normal session state and restored on later use.
- File/folder search supports exact, prefix, substring, fuzzy fallback, and hierarchical-path matching. `parent > child` queries search an ordered ancestor/descendant hierarchy rather than treating the whole query as one filename. Literal matches are evaluated first so common searches do not pay the cost of fuzzy scoring every workspace entry.
- Pasting an existing full filesystem path or a workspace-root-relative path (e.g. `/nd_math_project/src/file.tex`) shows that file or folder directly, even outside the currently selected search scope. Direct paths can be opened without waiting for background indexing, and each result shows its full path in a tooltip.
- Double Shift reuses an already built in-memory index and previously displayed results rather than rescanning the entire workspace on every Search reopening.
- Folder search hits close the Search window and reveal/scroll/highlight the folder in the main Navigator; file hits open the file.
- Text search runs in a cancellable background worker, respects `search_ignore.yaml`, and searches supported source/text file types recursively without blocking the GUI.
- Text-search results are grouped as filesystem folders → file → active LaTeX `part`/`chapter`/`section`/`subsection`/`subsubsection`/`paragraph`/`subparagraph` hierarchy → every matching occurrence.
- Multiple occurrences in one file are preserved as separate result rows. Enter or double-click opens the file and places the editor cursor at the exact matched line and column.
- Navigator folder context menus expose scoped **Search Files / Folders Here** and **Search Text in Files Here** actions; each opens the matching Search tab with that folder already selected as the recursive root.
- Up/Down and Enter support keyboard-only navigation.
- Search indexes rebuild after Mind Mirror workspace changes or scope changes. For changes made externally by Dropbox, Git, or a terminal, **Refresh index** explicitly rescans the selected scope without restarting Mind Mirror.
- Search and rename-reference scanning both use the configured `search_ignore.yaml` rules.

- A canonical LaTeX Source file remains unchanged when simply switching to Visual and back; Visual preserves intentional line breaks and source indentation, including in windowed multi-hundred-kilobyte documents.

### Tabs and session

- Multiple editor tabs with a configurable maximum count.
- Tabs are shown in two rows: persistent pinned files above ordinary open files.
- Pinned and ordinary tabs can be drag-reordered and their order is persisted.
- `Ctrl+W` closes the current editor tab from either Source or Visual. An explicitly closed pinned tab is temporarily unpinned, goes through the normal unsaved-changes Save/Discard/Cancel workflow, and is re-pinned if closing is cancelled; automatic tab eviction still protects pinned files.
- `Ctrl+Tab` switches recent tabs.
- `Ctrl+Tab` and the Pinned/Open row dropdowns show the filename first, followed by smaller gray compact path context from the first folder under `repo` to the file's direct parent.
- Pinned paths follow renames and are removed when their targets are deleted.
- Open files, active file, cursor/scroll positions, bookmarks, splitter sizes, window layout, Preview state, and tab order are persisted.

## Supported editor types

- `.tex` and `.tikz` open in the LaTeX editor with **Source** and **Visual** modes.
- `.yaml` and `.yml` open in the YAML editor with YAML syntax highlighting, smart indentation, Structure parsing, and Auto Format.
- Other text/code files open in the generic text editor with the shared text-editor behaviors and Pygments-based highlighting where applicable.
- Large LaTeX documents automatically use the large-source architecture at the configured threshold while preserving the complete canonical file on disk.

## LaTeX editing

### Source mode

- LaTeX syntax highlighting.
- Spell checking is enabled by default for every LaTeX file and can be disabled independently for a file from the Source or Visual context menu; an explicit per-file disabled state remains persisted.
- Each file has exactly one spell-check language: English, German, or Persian. The default Auto mode detects that document language from prose while excluding LaTeX syntax; the context menu can lock a file to a language manually.
- Only the selected document dictionary is used for correctness, suggestions, and custom words. Persian therefore adds no cost to English/German documents and English words cannot be accepted merely because they exist in the German dictionary.
- Spell checking is debounced, cached, and bounded to the active Source/Visual viewport plus a small margin; when disabled, no spell-check scan runs.
- Misspellings receive a red spell-check underline. Right-clicking a misspelled word offers ranked corrections from that file's language only and replaces the clicked word when a suggestion is chosen.
- The spelling menu can add a word to the persistent user dictionary for the file's selected language. LaTeX commands and metadata, comments, math, references, URLs, and raw Visual blocks are excluded from normal prose checking.
- Configurable source font, size, line height, padding, tab size, indentation guides, soft wrapping, wrap marker, and incremental source-layout debounce.
- Logical line numbers count actual source lines rather than visual soft-wrap rows.
- Automatic Persian RTL/LTR line handling while keeping LaTeX command/setup lines usable.
- Persian/Arabic text uses the configured shared Persian font; the current default is `Noto Sans Arabic` so combining marks such as kasra remain visually separated from the base glyph.
- Smart Enter/list continuation.
- `Tab` / `Shift+Tab` use the shared configured indentation size; logical line numbers number real source lines rather than soft-wrap continuation rows.
- `Ctrl+Shift+D` deletes the complete current canonical line in Source; in Visual it deletes the corresponding canonical Source line.
- `Ctrl+Shift+F` formats LaTeX using the configured indentation hierarchy.
- `Ctrl+B` applies bold to the current selection.
- LaTeX completion and user snippets from `latex_shortcuts.yaml`.
- Clipboard and iPad image insertion use one collision-safe `img_N.png` sequence per folder.
- Image insertion keeps the complete LaTeX `figure`/`\includegraphics` source visible.
- The LaTeX toolbar provides grouped Unicode character insertion, an `\iffalse … \fi` helper, and a `_ → \_` action that escapes unescaped underscores in the current Source selection.
- Standard Source context-menu editing remains available without the retired bookmark actions.
- Ubuntu right-click menus use compact semantic icons for common actions, while the Navigator tree uses slightly wider child indentation for clearer hierarchy.
- Source and Visual keep native text Copy/Cut/Paste semantics while exposing current-document Open actions such as Open in Files and Pin File in Tabs.
- Source and Visual provide scroll-past-end breathing room: while typing near the bottom of the viewport, the caret stays above the lower edge and visually empty space remains available below it without adding characters to the canonical source.
- Dragging an image from Navigator into Source inserts the exact image path into a LaTeX figure rather than substituting a different clipboard image.
- Source graphic references can show the managed graphic preview/edit workflow without replacing the canonical `\includegraphics` source.

### Visual mode

Visual is an editable projection of the same canonical LaTeX source; it is not a second document.

- Common prose, headings, lists, styling, highlighting, symbols, and graphics can be edited visually.
- Simple and nested `\frac{...}{...}` expressions receive a readable projection while raw LaTeX remains canonical.
- Graphic projection respects relative widths such as `\textwidth`, `\linewidth`, and `\columnwidth`.
- Persian/Arabic-script text uses the same configured Persian font as Source and preserves shaping/combining marks.
- Large documents use a cursor-centered virtual Visual render window while preserving source mapping and untouched source outside that window.
- Visual render-window size, estimated characters/lines per page, edge threshold, and re-window delay are configurable in `settings.yaml` so projection cost can be tuned for speed.
- Unsupported/raw LaTeX regions are preserved rather than silently discarded.
- Visual normal prose/list blocks use LaTeX-like full justification while preserving the Source as canonical.
- Visual edits are committed back with a minimal Source diff; a pending Visual edit is flushed before returning to Source, where full formatting can run.
- Clipboard images pasted in Visual are routed through the same managed-image insertion workflow as Source.
- Selected Visual text supports native selection and LaTeX source editing without a separate bookmark command.
- Graphic context actions in Visual can target the represented image for the iPad editing workflow.
- A raw `\input{tikz.tex}` or `\include{...}` whose target contains `\begin{tikzpicture}` is rendered inline as a TikZ preview while its original input command remains the canonical source when Visual serializes changes back.

### Render-performance settings

Render-related limits that materially affect Source, Visual, or Preview work are exposed in `settings.yaml` rather than being fixed only in implementation code.

- Source: `source_layout_update_debounce_ms`, existing source update debounce values, and large-document thresholds control how aggressively source relayout/update work is coalesced.
- Source presentation/layout work is bounded around the visible/cursor region so long files do not continuously reformat every block while typing or scrolling.
- Large-document source buffering/autosave is chunk/snapshot based so autosave does not have to join or rewrite the whole visible editor synchronously on every interval.
- Visual: `visual_window_pages_above`, `visual_window_pages_below`, `visual_window_estimated_chars_per_page`, `visual_window_min_lines_per_page`, `visual_window_max_lines_per_page`, `visual_window_rewindow_delay_ms`, and `visual_window_scroll_edge_ratio` control the bounded Visual projection window.
- Preview: `min_zoom_percent` and `max_zoom_percent` bound PDF render scale. `fit_raster_width_px` and `fit_raster_sample_step_px` control the low-resolution content probe used by the explicit **Fit** command; Auto Fit keeps its separate settled-width behavior.

### Undo and Redo

- `Ctrl+Z` → Undo
- `Ctrl+Y` → Redo
- `Ctrl+Shift+Z` → Redo

The controller handles Qt standard-key matching and German/Swiss QWERTZ layouts.

## Bookmark interface retirement

- The former Bookmarks top menu, its `Ctrl+Shift+B` binding, configurable bookmark shortcut entry, and Source/Visual context-menu creation/removal commands have been retired.
- Existing persisted range-bookmark data is deliberately retained in session state for possible migration to a future design. Retirement does not alter LaTeX source files or destroy saved bookmark metadata.
- LaTeX `\label{...}` continues to be the recommended portable identifier for sections and other structural locations. A future selection-anchor system should store arbitrary prose ranges outside canonical LaTeX, with surrounding-text verification to withstand edits.

## Live PDF Preview

- LuaLaTeX live rendering.
- Multi-pass bibliography/citation rendering when required.
- The last valid PDF remains visible during transient compile failures.
- LaTeX compile failures open a structured diagnostics tree below the last valid PDF; the divider has a clearly visible drag handle, and the complete diagnostic (raw compiler output plus dependency/error tree) can be copied as plain text or YAML for ChatGPT/debugging.
- PDF text remains selectable/copyable.
- Ctrl+mouse-wheel zoom and panning are supported.
- Zoom percentage and page information are displayed.
- PDF export is available. Full LaTeX documents are compiled from the canonical source with LuaLaTeX plus Biber/BibTeX when required; fragment-style documents can be exported through the Preview wrapper.
- The Preview toolbar order is **Export PDF → Export TeX → Detach → Lock → Extend → Fit**. **Export TeX** saves the exact prepared LaTeX source that produced the PDF currently visible in Preview, including recursively resolved `\input` content, the selected Preview wrapper/profile, and Preview reference materialization. If a newer compile fails, it still exports the LaTeX corresponding to the last valid PDF that remains visible. The default output name is `<source>_preview.tex`.
- Preview can be detached into its own window and reattached without permanently stretching the editor layout.
- **Fit Once** performs content-aware fit.
- **Auto Fit** fits the page to the settled Preview width without continuously changing zoom while typing.
- Normal left-click on the PDF performs reverse SyncTeX and moves Source/Visual to the corresponding source location.
- Source/Visual cursor movement drives source-position synchronization/scrolling in Preview; when there is no explicit selection, the mapped location can be shown by the persistent Preview caret overlay.
- An explicit Source/Visual selection requests a PDF text highlight.
- Preview zoom limits and the explicit Fit command's low-resolution content-probe size are configurable in `settings.yaml`.
- Portable leading-slash workspace references in generated Preview source are materialized against `search.default_path` before compilation, so references such as `/nd_language_ai_project/...` remain portable in canonical source/templates while LuaLaTeX receives the actual filesystem path.

### Preview toggle and layout

- Preview has an always-visible toggle in the top-right menu-bar area.
- Preview visibility, window geometry, and splitter/pane sizes are persisted.
- **Preview Lock** prevents Source/Visual synchronization from moving the PDF and preserves the current zoom/scroll viewport through live reloads.
- **Preview Extend** hides Navigator and Source/Visual panes so Preview fills the main window, then restores the previous pane visibility when disabled.
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

Shipped configurable actions include Open (`Ctrl+O`), Save (`Ctrl+S`), Close tab (`Ctrl+W`), Auto Format (`Ctrl+Shift+F`), Find (`Ctrl+F`), Replace (`Ctrl+R`), Preview toggle (`Ctrl+Alt+P`), Bold (`Ctrl+B`), editor zoom reset (`Ctrl+0`), close Find/Replace (`Escape`), and Navigator Delete (`Delete`). Navigator file clipboard keys are handled by the dedicated Navigator key-event controller because they must coexist with clipboard-image paste.

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

- `settings.yaml` — application/UI behavior, including Source/Visual/Preview render-performance knobs, the shared Persian font, `graphic.canvas_width` / `graphic.canvas_height` for the default size of newly inserted iPad raster graphics, and `graphic.tikz.canvas_width` / `graphic.tikz.canvas_height` for the default TikZ canvas (760 × 980);
- `keyboard_shortcuts.yaml` — application accelerators;
- `latex_shortcuts.yaml` — LaTeX snippets/completions;
- `search_ignore.yaml` — search/Navigator/rename-scan ignore rules;
- `session.ini` — lightweight session state;
- `ui_state.json` — window/splitter/navigation state;
- `templates/latex_preview_template.tex` — article/fragment Preview wrapper;
- `templates/latex_preview_beamer_template.tex` — Beamer Preview wrapper.

Existing user values win when shipped defaults/schema are merged.

Runtime defaults currently include 1-second autosave, 350 ms external-file synchronization, configurable Source/Visual/Preview debounce thresholds, a 20-tab default maximum, 3-space indentation, Persian text-direction detection, and an automatically started graphic bridge. Autosave uses local cache staging so temporary autosave files are not created inside Dropbox.

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
- The top-right Gear settings sheet has a persistent **Show drawing toolbar** toggle. Hiding the drawing toolbar removes the Pencil/Highlighter/Eraser/Lasso/image-import row without disabling the Apple Pencil double-tap palette or photo import.
- The Gear settings sheet also owns one persistent drawing-tool order. Tap **Edit** and drag the reorder handles to arrange saved Pencil/Highlighter/Eraser presets, Lasso, and Import image; the top drawing toolbar and the Apple Pencil double-tap palette read the same order, so both change together.
- Double-tapping the raster canvas with the Apple Pencil tip opens a four-column quick-tool palette at the tap location. It contains the shared ordered drawing-tool items plus Redo and Undo, prefers placement above the Pencil, stays fully inside the visible canvas, reduces its row count when fewer than 16 items exist, and scrolls inside the same four-row panel if more items are configured.
- On first Apple Pencil contact after a configurable idle period, the raster canvas briefly shows only the active tool icon beside the contact point. Pencil and Marker icons use the selected tool color and opacity; Eraser and Lasso remain neutral. The Gear settings sheet provides a 1.0–10.0 second minimum idle interval in 0.5-second steps so continuous handwriting does not repeatedly show the icon. The indicator is transient and does not intercept drawing input.
- Saved drawing-tool presets can be added, edited, reordered by placement, or deleted; Pencil/Highlighter presets carry color, thickness, and opacity, while Eraser presets carry eraser mode and width.
- Independent recent-color history for Pencil and Highlighter.
- Persistent last stroke color and thickness.
- Thickness range 1–24.
- Floating recent-color matrix.
- The image header shows a color-matched icon for the selected tool, then the logical canvas dimensions, immediately to the left of Back; these no longer occupy a separate status strip.
- Explicit 100% zoom command.
- Two-finger tap Undo.
- PencilKit lasso movement plus proportional corner-handle resizing; an Apple Pencil tap outside the active selection box and its interaction handles deselects the current lasso selection.
- Finger pan/pinch with Pencil drawing.
- Background photo import/removal.
- Editable canvas sizes/presets, including A4 portrait, A4 landscape, square, and custom numeric dimensions; resizing is checked against existing drawing bounds so the requested canvas does not silently clip content.
- Independent measurement **Grid** and centimeter **Rulers** overlays are view-only and can be toggled from the toolbar.
- Autosave/live-save through the Ubuntu/iPad bridge with a configurable Ubuntu update rate in Live Sync settings; the rate is not displayed on the drawing canvas.
- The native iPad side listens on TCP port `8768`; Ubuntu connects to it, performs the bridge handshake, opens graphics, receives `update_graphic` payloads, and acknowledges saved revisions.
- Managed PNG graphics keep neighboring `.ndgraphic` sidecars.
- Existing managed figures can be updated from the iPad without replacing the surrounding LaTeX workflow.
- New `Insert image in iPad` documents take their logical canvas size from Ubuntu `graphic.canvas_width` and `graphic.canvas_height`; the shipped/current default is **760 × 980**. `Edit image in iPad` continues to use the existing image's native dimensions.
- The iPad header has a **Close image** button that closes only the active graphic and returns to the Ubuntu-waiting screen without disconnecting the bridge listener. The header background extends under the native system status-bar safe area, avoiding a separate launch-screen-colored band without overlapping the native time indicators.
- Save serialization keeps one save in flight and coalesces newer changes to the latest state. Unacknowledged state is retried every 0.8 s until acknowledgement or document reset; closing waits for the final state for a bounded interval before returning to the waiting screen.
- During a desktop rename/move of the active managed graphic, the iPad remaps the document identity without reloading the canvas or losing the current viewport/Undo/Redo state.
- Repeated same-path open messages do not replace the iPad-authoritative in-progress canvas.
- Existing-image update saves are blocked from replacing a valid desktop image with an accidental empty white bitmap when the required background is unavailable.

### Direct iPad TikZ editing

- `Create TikZ in iPad…` and `Edit TikZ in iPad…` operate on the canonical neighboring `.tex`/`.tikz` source. Visual mode can render a referenced TikZ child inline without replacing its `\input{...}` command.
- TikZ uses its own logical canvas size. The default is **760 × 980**, configured by `graphic.tikz.canvas_width` and `graphic.tikz.canvas_height`; the TikZ gear menu exposes **Canvas size…**, and an edited diagram carries its own `% nd_mind_mirror_canvas: WIDTHxHEIGHT` metadata.
- Apple Pencil/finger single tap selects a shape or connector; double tap enters label editing. Connector hit targets are deliberately wider than the visible stroke so thin lines remain selectable.
- A selected shape exposes eight resize handles plus a separate blue move handle, so movement and resizing cannot compete for the same gesture.
- Shape fill, border, label text, connector line, and connector-label text use native SwiftUI `ColorPicker` controls with arbitrary RGB colors rather than a fixed preset palette.
- The raster Image workspace is removed from the SwiftUI hierarchy while TikZ is active, preventing image-only floating controls or magnifier overlays from leaking into the TikZ canvas.

## Android companion

Mind Mirror includes a **standalone Android editor**. The installed app does not connect to the Ubuntu Mind Mirror process, does not use a LAN server, and does not require an IP address or access token.

The Android layout is intentionally single-pane for phone screens. **Navigator**, **Structure**, **Preview**, **Source**, **Visual**, and **Search** are separate tabs; selecting one hides the others. The gear button opens Android settings with two independently persisted roots: **Local Android** and **Dropbox**. Each root is selected through the Android Storage Access Framework folder picker and keeps its read/write permission across restarts. The active-root buttons switch instantly between the two saved locations, so Navigator/Search root `/` can point either to a local Android folder or to a Dropbox folder exposed by the installed Dropbox document provider.

Navigator operates directly on the selected Android document tree. Whenever a file is opened in Source, Navigator follows it to its parent folder and marks that file as the current selection, including files opened from Search or the recent-file list. Long-pressing a folder in Navigator or any folder node in Search opens the same Android folder action sheet with **New LaTeX File**, **New File**, **New Folder**, **Recent 30 Files**, and **Open in Navigator**. New LaTeX files ask for a file name and then present the same configured choices currently used by the Ubuntu editor: **Article (standard)**, **Beamer**, and **German learning**. The recent-file picker is persisted separately for each Android/Dropbox root and shows the file name plus the trailing part of its path before opening the selected entry in Source.

Search uses a persistent local SQLite index on Android. **Files** is the default mode and reuses indexed file-name metadata without waiting for text-content indexing; **Text in files** is a separate explicit mode. Both result modes are rendered as an expandable root/folder/file tree modeled after the Ubuntu Double-Shift search, with text occurrences nested below their files.

Source reads, edits, and autosaves the selected file directly through Android's document provider. The Android Source editor uses a bundled CodeMirror editor with filename-aware syntax highlighting for LaTeX/BibTeX, Python, YAML, JSON, JavaScript/TypeScript, Java/Kotlin/C-family languages, shell, HTML/XML, CSS, Markdown, TOML/INI/configuration files, SQL and other common source formats, with plain-text fallback. Long logical lines soft-wrap automatically and continuation rows show the same `↳` marker in the left gutter used by the Ubuntu editor. For LaTeX files, Source also uses real line widgets to reserve editor space and show rendered previews after the corresponding source constructs: normal `figure/includegraphics` resources, inline/display mathematics, and safe rectangular `tabular` content. These previews do not modify canonical source offsets.

Visual is a read-only Android projection modeled after the Ubuntu Visual block rules. It renders headings, paragraphs, itemized/enumerated lists, inline and display mathematics through bundled offline KaTeX, normal graphics resolved through the active Android/Dropbox SAF tree, captions, and safe rectangular tables. Raster images and SVG are loaded directly; PDF graphics are rendered from their first page with Android's PDF renderer. Legacy absolute paths below `/repo/` and ordinary source-relative graphic paths are both resolved against the selected workspace. Double-tapping a rendered Visual block jumps back to its Source line.

Android now embeds a native Tectonic/XeTeX compiler for `.tex` and `.ltx` documents. Preview compilation runs entirely on the Android device in a background worker: the editor materializes referenced project files from the active SAF/Dropbox tree into a private compile workspace, rewrites portable and legacy `/repo/` references for that workspace, compiles to a fresh PDF, and renders the resulting pages with Android's PDF renderer. The first compile can use the Internet to fetch TeX package resources directly from Tectonic's package relay; those resources are cached in the app's private storage and reused on later compiles. This network access is only for TeX packages and never connects to the Ubuntu Mind Mirror process.

The Preview tab has explicit **Compile** and **Export PDF** actions, and Source edits also trigger a debounced background compile. **Export PDF** compiles the current editor state and writes the resulting sibling PDF (for example `paper.tex` → `paper.pdf`) back through the active Android Storage Access Framework provider, including Dropbox. Existing PDFs can still be opened directly. Tectonic handles ordinary LaTeX, XeTeX, TikZ/PGF, bibliography workflows, graphics, and many TeX packages locally; workflows that require arbitrary external shell programs, such as some `minted` or Graphviz shell-escape configurations, are not guaranteed to behave identically to the full Ubuntu TeX toolchain.

Structure is generated locally for common LaTeX section commands. Android remains standalone: no Ubuntu server, IP address, or access token is involved in compile, preview, or PDF export.

The iPad/PencilKit graphic editor is deliberately not part of the Android application.

Build and install with:

```bash
cd /home/donkarlo/Dropbox/repo/nd_mind_mirror_project
./scripts/android/install_android.sh
```

The installer builds the standalone APK and installs it through an already-authorized USB or wireless ADB connection. If no device is connected, it can request the wireless-debugging address/port and pairing information.

The debug APK is produced at `src/nd_mind_mirror/mobile/android/app/build/outputs/apk/debug/app-debug.apk`.

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

The startup path refreshes the canonical iPad transfer package before constructing the Qt window. The launcher prefers `ND_MIND_MIRROR_PYTHON` when configured, otherwise `~/phd-venv/bin/python` when available. Python bytecode is redirected to `~/.local/state/nd_mind_mirror_project/pycache` so Dropbox is not filled with generated `__pycache__` files. Startup/crash diagnostics are written under `~/.local/state/nd_mind_mirror_project/`. `Ctrl+C` in the launching terminal requests a clean application shutdown.

Each desktop application session starts a bridge process from the current project source; bridge startup can select collision-safe ports when an older process still occupies the default desktop bridge port.

## Project layout

- `src/nd_mind_mirror/core/` — document, LaTeX, search, settings, rendering, and workspace logic.
- `src/nd_mind_mirror/core/workspace/operation/` — process-side services and worker entry points for batched workspace reference maintenance.
- `src/nd_mind_mirror/ui/` — Qt editors, panels, Preview, search UI, and main-window controllers.
- `src/nd_mind_mirror/mobile/android/` — standalone Android editor, local document-tree access, mobile UI assets, and wireless-ADB build/install tooling.
- `src/nd_mind_mirror/graphic/` — desktop/iPad graphic workflow and bridge.
- `src/nd_mind_mirror/graphic/ipad/` — editable Swift package and canonical transfer ZIP.
- `tests/` — automated/regression tests covering LaTeX/YAML parsing and formatting, large-document architecture, Preview safety/synchronization, Navigator selection/clipboard/reference operations, bookmarks/Undo, and Ubuntu↔iPad graphic transport/lifecycle behavior.
- `tools/` — development/maintenance utilities.
- `/repo/data/nd_mind_mirror_project/` — persistent user settings and session/UI state.

## Runtime architecture and safety guarantees

- The desktop is composed from focused controllers rather than a second independent editor state: the canonical editor buffer/file remains authoritative.
- Workspace reference scans and confirmed rename/move/delete maintenance have separate service/worker entry points so expensive repository-wide work can run out of the GUI thread/process.
- Open editor buffers are protected from background reference-worker writes and filesystem/external-change reconciliation is deferred while workspace operations are pending.
- Preview compilation uses generation tracking so an obsolete in-flight compile can be stopped after the typing debounce in favor of the newest generation.
- The Preview keeps the last valid PDF visible when a newer transient compile fails.
- Session list values are sanitized before restore/save to avoid invalid Qt settings values causing startup crashes.
- Idle memory compaction periodically runs garbage collection and, when available, returns unused glibc heap pages without disabling editor features.
- The iPad transfer package is rebuilt from the canonical Swift package; numbered/conflict package copies are not treated as editable source.
- A legacy browser graphic client remains under `graphic/web/` as an older/alternate artifact, but the canonical current iPad workflow is the native SwiftUI/PencilKit package under `graphic/ipad/nd_graphic.swiftpm/`.

## Repository hygiene

- Canonical source files are edited directly; backup/pre-change/duplicate implementation files are not part of the design.
- Generated Python `__pycache__` directories are not kept in the Dropbox project tree.
- Temporary files created by atomic/runtime operations must be cleaned up after use.
- `search_ignore.yaml` is the shared ignore policy for workspace searching and rename-reference scanning.

## Complete current feature index

The active source/tests/settings currently cover these functional areas:

1. Workspace root configuration, ignored-path policy, deterministic Navigator reveal/centering, explicit post-rename/external-delete filesystem-model refresh, horizontal scrolling, multi-selection, grouped context menus, copy/cut/paste, collision naming, create/rename/delete/drag/move, path copying/sharing, and iPad image/TikZ actions.
2. Semantic repository reference discovery/rewrite across relative, workspace-relative, absolute, `/repo/...`, extensionless LaTeX, graphics, bibliography, listing/verbatim, minted, URL/href, and supported document-link contexts.
3. Background reference scanning/maintenance and responsive filesystem workers, including managed raster + `.ndgraphic` lifecycle rules.
4. LaTeX Source editing, completion/snippets, indentation/formatting, RTL/LTR direction, logical line numbers, wrapping, selection-consistent bookmarks, image/TikZ insertion, special-character helpers, line deletion, and selection-aware context actions.
5. LaTeX Visual projection/editing, source mapping, graphics, inline source-backed TikZ previews, nested fractions, justified prose/lists, Persian typography, image paste, bookmarks, and bounded large-document windowing.
6. YAML editing, syntax highlighting, hierarchical Structure parsing, smart/shared indentation, and formatting that preserves YAML content structure.
7. Generic text/code editing with the shared source editor infrastructure.
8. Structure parsing/navigation/highlighting for LaTeX and YAML, including heading subtree spans, caption-aware images and tables, standalone tabular environments, and canonical-source drag/reorder/reparent operations.
9. Two-tab workspace search: Double-Shift file/folder search with exact/prefix/substring/fuzzy and ordered `>` hierarchy matching, plus recursive text-in-files search with selectable roots, persisted per-tab state, LaTeX structural grouping, exact occurrence navigation, and Navigator folder-scoped search actions.
10. Pinned/Open two-row tab management, drag ordering, persisted order, max-tab/LRU behavior, recent-file switching, `Ctrl+Tab`, `Ctrl+W`, path remapping, and session restoration.
11. Undo/Redo, current-line deletion, Find/Replace, bold, bookmarks, editor zoom reset, configurable application shortcuts, and user-editable LaTeX shorthand expansion.
12. LuaLaTeX live Preview, recursive input resolution, workspace-rooted Preview reference materialization, graphic dependencies, bibliography passes, generation cancellation, selectable PDF text, zoom/pan, Fit/Auto Fit, reverse SyncTeX, structured/copyable diagnostics, selection highlight/caret mapping, Lock, Extend, Detach/Attach, toggle, and PDF export.
13. Autosave, external-file synchronization, local autosave staging, deletion-safe autosave commit semantics, persisted UI/editor state, settings reload, and per-feature performance/debounce controls.
14. Native iPad PencilKit raster drawing plus direct source-backed TikZ editing, including reliable select/double-tap label edit, separate move/resize controls, arbitrary native colors, TikZ canvas sizing, Undo/Redo-compatible source updates, and shared transport.
15. Ubuntu↔iPad bridge transport, open/update/save acknowledgements, revision tracking, managed sidecars, background preservation, stale-path rename aliases, current-session bridge process ownership, and Source/Visual/Preview refresh after accepted graphic updates.
16. Startup/package tooling, canonical iPad ZIP generation, crash/startup diagnostics, preferred virtual environment selection, Python cache relocation, regression tests, examples, templates, icons, and release-history documentation.
17. Standalone Android editor with one-visible-panel tabs for Navigator, Structure, Preview, Source, Visual, and file/text Search; separately persisted Local Android and Dropbox root folders with instant active-root switching, direct document-provider editing/autosave, local sibling-PDF rendering, and wireless-ADB build/install tooling without an Ubuntu runtime connection.

## Code documentation rule

New and modified implementation files begin with a concise module description. New and modified classes/functions should have concise documentation describing responsibility. Legacy files are brought under this rule as they are touched rather than being mass-rewritten without a functional reason.

<!-- ND_IPAD_CURRENT_FEATURES_START -->
### Current iPad graphic and preview features

- LaTeX Structure includes `\includegraphics` entries. A graphic inside a `figure` uses its `\caption` text when present; otherwise Structure shows the image filename.
- Preview Auto Fit fits the complete physical PDF page width once for a newly opened LaTeX document, keeps that zoom fixed during typing/live reloads, and never raster-scans pages to calculate fit.
- Preview wheel/touchpad scrolling is handled directly by the PDF viewport. Source/Visual selection highlighting is applied only after the current SyncTeX mapping is ready, so highlighting does not control wheel scrolling or use stale PDF coordinates.
- Live Preview cancels an obsolete LaTeX compile after the normal typing debounce and immediately renders the newest editor generation instead of waiting indefinitely for an old compile.
- Portable leading-slash Preview references are resolved against `search.default_path` in the generated compile source while canonical LaTeX remains portable.
- Visual renders source-backed TikZ children referenced by `\input`/`\include` inline and preserves the original input command when serializing.
- The canonical editable Swift Playgrounds package is `src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/`; startup removes numbered `nd_graphic (N).swiftpm` transfer/conflict copies and never treats them as source.
- New Ubuntu `Insert image in iPad` graphics use the Ubuntu-configured logical canvas size (`graphic.canvas_width` × `graphic.canvas_height`, default 760 × 980); existing graphics opened with Edit keep their native dimensions. Both open at logical 100% with the canvas aligned to the top-left viewport, and two-finger pinch zoom remains enabled.
- TikZ has independent `graphic.tikz.canvas_width`/`canvas_height` defaults (760 × 980), gear-menu canvas editing, Rectangle, Triangle, a single icon-only Circle/Ellipse tool, Straight, Curve, and Polyline tools, single-tap selection, double-tap label editing, a separate move handle plus eight resize handles, and native arbitrary ColorPickers for shape/connector/text colors. A rounded shape turns between a circle and an ellipse according to the proportions produced by its resize handles; round shapes share one remembered style.
- TikZ tool names are hidden; each tool displays icon-only controls, saved appearance thumbnails (actual fill/border/text color or connector line properties), and an inline plus icon to store the current style. Apple Pencil double-tap opens a floating tool/style chooser. Pencil-drawn closed contours on empty canvas are recognized as rectangles, circles/ellipses, or triangles even without choosing a tool, and use the drawn dimensions and remembered appearance. Newly created shapes open an in-place Pencil Scribble label editor. TikZ retains its 200-step Undo/Redo history.
- TikZ Auto layout uses actual node dimensions and small inter-node gaps, centered instead of stretching nodes to the full canvas. The tool row scrolls horizontally on narrow iPad screens.
- The image workspace's quick Apple Pencil palette and active-tool icon are anchored to the visible viewport even after logical canvas enlargement, with automatic above/below placement where space permits.
- Source-mode rendered TikZ thumbnails have their own **Edit TikZ in iPad…** right-click action. Desktop TikZ events are monitored even when the shared bridge is owned by an external process. Live TikZ projections refresh at a bounded 80-ms interval while expensive PDF compilation remains idle-debounced.
- While TikZ is active the raster workspace stays alive but invisible and non-interactive, so its shared TCP listener survives Image↔TikZ transitions without letting hidden image controls overlap the TikZ canvas.
- iPad TikZ saves publish a tiny atomic desktop event immediately after the canonical source write; Source inline TikZ, Visual, and PDF Preview refresh from that event while the iPad preview render continues in the background.
- Source mode renders TikZ children referenced by standalone `\input{...}` or `\include{...}` directly below the canonical include line without rewriting the source.
- A managed graphic renamed or moved in the Ubuntu Navigator keeps its `.ndgraphic` companion; the active iPad session follows the new path/name while preserving the current canvas, viewport, and Undo/Redo history.
- Starting the iPad app or reconnecting the bridge does not reopen a stale previous insert/update request and does not create a new blank graphic. Opening an insert request no longer performs an eager blank save before the user changes the canvas.
- Existing update backgrounds are preserved during ordinary iPad autosaves even if SwiftUI briefly exposes a nil background while a document is loading, preventing a white canvas from overwriting the real PNG.
- Pencil and Highlighter toolbar buttons each open their own settings popup for color, thickness, and transparency. The popup can add a new tool immediately after the current tool, change the current tool, switch among same-kind saved tools, or delete one; the main toolbar no longer duplicates those three setting controls.
- JPG/JPEG and PNG `\includegraphics` targets can both be opened in iPad Edit mode; existing image edits use the native pixel size and save back in the target image format.
- Photos selected on iPad are inserted as editable image objects rather than replacing the document background. Image objects keep aspect ratio, start at a bounded top-left size, can be selected by finger or Apple Pencil Lasso, moved, proportionally resized, deleted, and support Undo/Redo for insert/delete/move/resize.
- Editable image-object metadata is stored in the graphic sidecar and returned by the bridge on later Edit operations, while the Ubuntu/base background remains a separate layer. The saved PNG composites base background, image objects, and PencilKit strokes.
- Lasso stroke selection keeps four proportional resize handles plus a smaller pale-gray move handle. Resizing changes geometry without scaling stroke thickness, and transformed stroke points are tested in canvas coordinates so moving a selection cannot silently move a different stroke.
- Canvas width and height are not capped at the former 8192 px limit. Existing PencilKit strokes define the minimum safe canvas dimensions, and the iPad reports when a requested canvas would clip the graphic.
- Custom canvas numeric fields request the ASCII-capable number pad so canvas dimensions are entered with English digits.
- The iPad measurement Grid and centimeter Rulers remain independent view-only overlays. The image header retains Rulers, Grid, and canvas options but omits Undo/Redo buttons; Undo/Redo remain available in the Pencil quick-tool palette, and two-finger tap performs Undo.
- PencilKit internal content geometry is synchronized with logical canvas resizing so the full A4 portrait drawing area accepts Apple Pencil input.
- Tapping the active source/image identity opens the ten most recently edited graphics and can request any of them from the Ubuntu bridge.
- The iPad image header provides Back/Forward navigation through graphics opened during the current session; opening a new graphic after going back clears the obsolete forward branch.
- The current canvas dimensions appear between the selected-tool icon and Back navigation in the primary image header; the former secondary status bar has been removed.
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
- The iPad can close the active graphic without disconnecting from Ubuntu; if a graphic save is still pending, the app waits for acknowledgement and retries only the latest state before returning to the waiting screen.
- Navigator keyboard file Copy/Cut/Paste uses direct tree key-event routing so `Ctrl+C`/`Ctrl+X`/`Ctrl+V` follows the same multi-path operations as the right-click menu; clipboard-image paste remains the fallback when no file/folder clipboard is active.
- Managed raster deletion removes its `.ndgraphic` companion, and rename/move can replace a valid stale orphan sidecar when the destination raster itself no longer exists.
<!-- ND_IPAD_CURRENT_FEATURES_END -->

### Unsaved LaTeX documents

Press **Ctrl+Shift+N** to open the default LaTeX template in a new, unsaved tab. No file is created and periodic autosave does not write this tab. **Ctrl+S** opens Save As, initially in the most recent directory chosen by this workflow. Closing the unsaved tab prompts to save, discard, or cancel. Once saved, the tab becomes a normal file and uses the existing autosave behavior. Existing files and their autosave behavior are unchanged.

### Preview PDF search

When focus is inside the Preview panel, **Ctrl+F** opens a separate PDF-text search field with previous/next buttons. Source and Visual continue to use their existing editor search.
