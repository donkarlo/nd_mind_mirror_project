# nd_mind_mirror_project

## v0.20.0 citation, preview-fit, hierarchical search, and in-tab find/replace

- Natbib/BibTeX previews now wait for the complete `LuaLaTeX -> BibTeX -> LuaLaTeX -> LuaLaTeX` bibliography cycle before publishing a bibliography rebuild. This prevents a bibliography from appearing while its `\cite{...}` still renders as `?`.
- New LaTeX sources automatically fit to the preview width by default. `preview.fit_width_percent` defaults to `95`; page height is not used as the fit target. `preview.auto_fit_on_open` can disable this behavior, in which case `preview.default_zoom_percent` is used.
- `Ctrl + mouse wheel` keeps the PDF content point under the mouse as the zoom anchor.
- File search keeps the previous query when reopened. Multi-word queries can match hierarchically across path components, so a token can match a parent folder while another token matches a descendant file/folder. Adjacent-letter transpositions such as `nueral`/`neural` are tolerated without loosening exact filename searches such as `neuron.tex`.
- File System and Structure row height is configurable with `ui.navigator_row_height` (default `24`).
- `Ctrl+F` opens Find for the current tab and `Ctrl+R` opens Replace. All matches are highlighted, previous/next arrow buttons cycle matches, Replace changes only the current match, and Esc closes the bar and removes highlights.
- YAML hierarchy in Structure and YAML smart indentation remain enabled.

## v0.15.0 Persian preview compatibility and LaTeX structure navigator

- Full Persian documents that already use `polyglossia`, `xepersian`, or an existing Persian Babel setup are left untouched by the preview source builder. This prevents the preview-only Babel fallback from being mixed with Polyglossia.
- The navigator column is split vertically: the existing file/folder tree stays on top and a live LaTeX structure tree is shown below it.
- The structure tree shows `part`, `chapter`, `section`, `subsection`, `subsubsection`, `paragraph`, and `subparagraph` hierarchically and indented. Double-clicking a structure entry moves the current editor to that source line.
- The default `editor.line_height_percent` is now `200`.
- Release ZIPs must exclude `.idea/` (as well as cache/bytecode directories).

## v0.14.7 Persian preview and navigator fixes

- Navigator files open on an explicitly handled double-click; a single click only selects.
- LuaLaTeX preview injects temporary Babel Persian support when Persian text is detected and the source does not already configure Persian. The source `.tex` file is never changed.
- Pressing Enter after ordinary prose preserves only the current source indentation instead of adding a logical LaTeX hierarchy indent. Structural LaTeX lines still use smart indentation.


A PySide6/Qt LaTeX editor with a filesystem navigator, tabbed editor,
live LuaLaTeX preview, persistent state, fuzzy file search, and PDF export.

## v0.14.6 Persian/English bidirectional LaTeX editing

- LaTeX source blocks now have per-line visual direction without changing the
  source text saved to disk.
- Structural/setup commands such as `\section`, `\begin`, `\end`,
  `\documentclass`, `\usepackage`, `\input`, and `\includegraphics` stay
  left-to-right for predictable source-code editing.
- Ordinary Persian prose is laid out right-to-left. English terms inside a
  Persian sentence are left to Qt's Unicode bidirectional text engine, so the
  Latin run keeps its natural left-to-right order inside the RTL paragraph.
- Citation/reference keys are ignored for language detection so a long English
  BibTeX key does not incorrectly turn a short Persian sentence LTR.
- RTL blocks mirror hanging soft-wrap margins to the right side.

The behavior is configurable in `settings.yaml`:

```yaml
editor:
  latex_text_direction: "auto"
  latex_rtl_persian_ratio: 0.35
```

`latex_text_direction` accepts:

- `auto`: LaTeX control lines remain LTR and prose direction is detected.
- `rtl`: ordinary prose is forced RTL while LaTeX control lines remain LTR.
- `ltr`: all source lines remain LTR.

`latex_rtl_persian_ratio` is used only in `auto` mode. For mixed prose, a line
becomes RTL when Persian/Arabic-script strong letters reach the configured
fraction of all strong alphabetic characters.

## v0.13 preview, soft-wrap, and Ctrl+Tab fixes

- Live preview requests now snapshot the active source text and source path together.
  Older LuaLaTeX jobs are ignored as soon as a newer tab/edit render is requested.
- Every successful preview is published to a generation-specific PDF filename before
  it is handed to Qt Quick PDF. This avoids the stale `preview.pdf` URL cache that
  could leave the previous tab visible after switching or opening another `.tex`.
- Soft-wrapped continuation lines use a real hanging block margin based on the
  source line's leading spaces/tabs. QTextDocument layout notifications are no
  longer blocked, so wrapped continuations are relaid out at the same horizontal
  start as the original line's first non-whitespace character. The source text is
  never changed.
- `editor.line_height_percent` now uses proportional QTextBlockFormat line height,
  so the setting remains effective after font changes and settings hot reloads.
- The Ctrl+Tab recent-file window shows up to ten rows, is slightly taller, and
  always scrolls the selected item into view while Ctrl remains held.

## v0.7 interaction improvements

### Editor

- The text cursor is explicitly configured to blink and has a configurable width.
- The active logical line has a very light blue full-width highlight.
- Long lines use soft wrapping, so the file content itself is not changed.
- A gray `↳` marker is painted beside every visual continuation line created
  only by soft wrapping.
- `Ctrl + Mouse Wheel` changes editor font size.
- Smart Enter keeps the cursor at the new indentation position.
- `Ctrl+Shift+F` formats the current LaTeX file by changing indentation only.
  Heading hierarchy and LaTeX environments determine indentation.
- Clipboard images are saved beside the active `.tex` file as PNG and inserted
  with a relative `\includegraphics` path.
- Autosave saves every modified open tab every second by default.

### File navigator

Only the `Name` column is displayed.

When a tab becomes active, its file is automatically:

1. revealed by expanding its parent hierarchy,
2. selected,
3. highlighted,
4. scrolled to the vertical center of the navigator.

Folder indentation is reduced and configurable.

Right-click a file or folder for:

- `New LaTeX File...`
- `New File...`
- `New Folder...`
- `Rename...`
- `Delete...`

Renaming a folder also updates paths of open tabs below it. Deleting a file or
folder closes affected tabs.

### Search window

Press **Shift twice** to open the search window.

The window opens exactly centered over the main application window.

Search is fuzzy and tolerant:

- any substring from the middle of a name works,
- underscores, dashes and spaces are ignored for compact matching,
- subsequence matching is supported,
- small spelling mistakes are tolerated,
- results are ranked by match quality.

Search results keep their filesystem hierarchy. Double-clicking a `.tex` result
opens it as a tab and closes the search window.

### Settings

All requested UI behavior is configurable from the root-level:

```text
settings.yaml
```

Important settings include:

```yaml
editor:
  font_family: "DejaVu Sans Mono"
  font_size: 11
  cursor_width: 2
  cursor_flash_time_ms: 650
  soft_wrap: true
  wrap_marker: "↳"
  wrap_marker_color: "#9aa0a6"
  wrap_marker_margin: 18
  current_line_highlight: "#eaf4ff"

autosave:
  enabled: true
  interval_ms: 1000

search:
  default_path: "~/Dropbox/repo"
  fuzzy_threshold: 0.55
  window_width: 900
  window_height: 620
  tree_indent_width: 10

ui:
  navigator_indent_width: 10
  splitter_handle_width: 9
```

Use:

```text
Settings -> Reload settings.yaml
```

after editing the YAML file.

## Existing features kept

- up to 10 open/recent tabs
- close button on each tab
- fixed tab width
- hierarchical labels when duplicate filenames are open
- LaTeX syntax highlighting
- LaTeX completion and `Ctrl+Space`
- `Ctrl+O` open
- `Ctrl+S` save
- live PDF rendering
- `Ctrl + Mouse Wheel` PDF zoom
- PDF export
- persistent tab, active-file, folder-expansion, and splitter state
- relative and absolute `\input` / `\include`
- standalone child-document preamble merging
- child heading hierarchy normalization based on master `documentclass`
- no `__init__.py` files
- one class per class-containing Python source file

## Install

```bash
cd /home/donkarlo/Dropbox/repo/nd_mind_mirror_project
/home/donkarlo/phd-venv/bin/python -m pip install -e .
```

## Run

```bash
/home/donkarlo/phd-venv/bin/python nd_mind_mirror_project
```


## v0.9 search and fragment-preview improvements

### Faster and more relevant search

- The search root is indexed once in a background thread instead of walking the entire repository after every keystroke.
- Queries are matched against the file or folder name itself. A matching ancestor directory no longer causes every descendant to appear as a false-positive result.
- Ranking prefers exact names, prefixes, and literal substrings before typo-tolerant fuzzy matches.
- The default fuzzy threshold is stricter (`0.72`) and the default result limit is `250`.
- Underscores remain normal search characters. Using Shift to type `_` no longer counts as a standalone Shift tap.
- Re-activating the Double-Shift shortcut while the search window is already open no longer selects and replaces the current query.

### Template-based preview for LaTeX fragments

A `.tex` file without `\documentclass` is never modified on disk. For preview only, its content is inserted into a temporary document built from the configurable template:

```yaml
preview:
  latex_template_path: "resources/latex_preview_template.tex"
  shell_escape: true
```

The bundled template contains the requested packages, external macro inputs, author, and bibliography. Edit the template itself or point `latex_template_path` to another file.

The preferred insertion marker is:

```latex
% ND_MIND_MIRROR_CONTENT
```

If a custom template has no marker, the previewer inserts the fragment before the bibliography, or before `\end{document}` as a fallback.

For fragment files, the temporary preview title is inferred without changing the source. The highest structural level present is preferred according to:

```text
part -> chapter -> section -> subsection -> subsubsection -> paragraph -> subparagraph
```

Within that level, the first non-empty heading is used. This makes `\input`/`\include`-style fragment files render with a useful document title.

## v0.8 fixes

### Double Shift vs. Ctrl+Shift+F

The Double-Shift search trigger now accepts only two standalone Shift presses.
A Shift press while Ctrl, Alt, or Meta is held is ignored, and any non-Shift
key resets the Double-Shift sequence.

Therefore:

```text
Ctrl+Shift+F
```

runs the LaTeX formatter without opening the search window.

### Safer live-preview preamble handling

Preamble `\input` / `\include` commands are no longer expanded into the
generated `preview.tex`.

This is important for macro files such as:

```latex
\input{/absolute/path/to/macros.tex}
```

Previously, the macro file could be expanded and then merged line-by-line when
a standalone child document was embedded. That could damage multi-line TeX
definitions and produce errors such as:

```text
Missing $ inserted
```

The new behavior keeps preamble macro files as real LaTeX inputs. Relative
preamble input paths are resolved and rewritten to absolute paths so they remain
valid when the temporary preview document is compiled.

Child preambles still merge packages and libraries while duplicate package,
TikZ-library, graph-drawing-library, and identical preamble-input lines are
removed safely.

The renderer behavior was validated by generating a master document containing
a complete standalone child document and an external multi-line macro file, then
compiling the generated preview with LuaLaTeX successfully.

## v0.10 preview, search, navigator, and editor synchronization

### Citations in live preview

The preview renderer now runs the bibliography tool when the first LuaLaTeX pass
creates bibliography metadata, then runs LuaLaTeX twice more. It supports
`biber` for `.bcf` workflows and `bibtex`, `bibtexu`, or `bibtex8` for classic
`natbib`/`\\bibliography{...}` workflows. This prevents resolved citations from
remaining as `?` merely because the preview was compiled only once.

### Selectable PDF preview

The live preview now uses Qt Quick PDF's multi-page viewer. Rendered PDF text can
be selected with the mouse and copied with `Ctrl+C`; `Ctrl+A` selects the text on
the current PDF page. This requires PySide6/Qt 6.8 or newer.

### Editable LaTeX source and line height

The source editor is explicitly writable. Editor line height is configurable in
`settings.yaml`:

```yaml
editor:
  line_height_percent: 200
```

Reload `settings.yaml` from the Settings menu after changing it.

### Faster, stricter search

Search still indexes the configured root in the background, but per-query
matching is now stricter and cheaper. A query containing an extension, such as
`neuron.tex`, uses literal filename matching and does not fall back to fuzzy
matching, so unrelated names such as `sondern.tex` are not returned. The new
default fuzzy threshold is `0.86`, debounce is `70 ms`, and result limit is
`100`.

Only matching files/folders and the ancestor nodes needed to reach those matches
are added to the result tree; unrelated hierarchy branches are not populated.

### Search root and `search_ignore.yaml`

Both the navigator and search are scoped to `search.default_path`. The navigator
uses that directory as its visible root and does not expose sibling/parent
branches.

Ignore rules are stored in the file configured here:

```yaml
search:
  default_path: "~/Dropbox/repo"
  ignore_file: "search_ignore.yaml"
```

The bundled `search_ignore.yaml` uses gitignore-like patterns. For example:

```yaml
ignore:
  - ".git/"
  - "out/"
  - "**/build/**"
  - "*.aux"
```

A directory rule such as `out/` applies at any depth. Reload `settings.yaml` to
rebuild search and navigator filters after changing the ignore file.

### External-file synchronization

Every second, open files are checked for changes made by another program. If the
on-disk file changed, the editor reloads it while preserving cursor and scroll
position. External changes are checked before autosave so autosave does not
immediately overwrite a just-detected external write.

```yaml
external_file_sync:
  enabled: true
  interval_ms: 1000
```

### `Ctrl+Tab` recent-file switcher

Holding Control and pressing Tab opens a centered recent-file switcher. Repeated
Tab presses move forward through recently used open files; holding Shift moves
backward. Releasing Control activates the selected file and hides the switcher.


## v0.11 empty-bibliography preview fix

- A LaTeX document that declares `\bibliography{...}` but currently contains no `\cite{...}` no longer causes the live preview to show a BibTeX error instead of the generated PDF.
- BibTeX is now started only when the AUX file contains both bibliography data and an actual citation request.
- Ordinary LaTeX reruns still happen, so references and the PDF preview continue to update normally.

## v0.12 updates

- Soft-wrapped continuation lines use a hanging indent aligned with the first non-whitespace character of the source line.
- `editor.line_height_percent` is applied using a fixed line height derived from the active font and updates immediately when settings are applied.
- `Settings -> Edit settings.yaml` opens the settings file in the built-in editor. Saving valid YAML applies it immediately; invalid YAML is saved but not applied until it becomes valid.
- LaTeX preview is forced to reload even though the renderer reuses the same temporary `preview.pdf` path.
- Switching/opening a `.tex` tab requests an immediate render; typing still uses the normal render debounce.
- The Ctrl+Tab recent-file switcher has a narrow blue border and subtle drop shadow.


## v0.14 editor and preview updates

- The editor uses Qt rich document layout while still accepting/saving plain text only, so soft-wrapped continuation lines can use a real hanging indent and `editor.line_height_percent` is applied visually without modifying the `.tex`/YAML source.
- `settings.yaml` is syntax highlighted and remains hot-reloadable after save.
- `Ctrl+W` closes the active editor tab.
- `editor.max_open_tabs` defaults to 20. Opening beyond the limit closes the least-recently-used unmodified tab.
- Live LaTeX preview publishes the first successful LuaLaTeX pass immediately, then refines bibliography/cross-reference output only when needed. `preview.debounce_ms` controls typing debounce.


## v0.14.1 preview zoom fix

- `Ctrl` + mouse wheel now zooms the selectable live PDF preview.
- Zoom is handled at the `QQuickWidget` boundary and updates the `PdfMultiPageView.renderScale`, so normal wheel scrolling remains unchanged when Ctrl is not held.
- Zoom range is limited to 20% through 800%.

## v0.14.2 preview scrolling

- Native scrollbars inside the selectable multipage PDF preview are kept visible and interactive after zooming beyond the viewport.

## v0.14.3 preview panning and navigator activation

- Hold `Ctrl` and drag with the left mouse button in the PDF preview to pan without changing the current zoom level.
- Drag with the middle mouse button to pan without any keyboard modifier.
- A single click in the file navigator only selects an item; an editable `.tex`, `.yaml`, or `.yml` file opens in a tab only on double-click.
- Opening a file from the navigator no longer recenters the already-selected tree item, avoiding the previous jump-away/jump-back effect.


### Beamer fragment preview

When a fragment has no `\documentclass` but contains a Beamer `frame` environment,
the previewer automatically uses `preview.latex_beamer_template_path` instead of the
article fragment template. The source fragment is never modified.
## LaTeX shorthand shortcuts

`latex_shortcuts.yaml` contains user-editable shorthand expansions. For example,
typing `lis` shows matching shortcut names below the cursor. Use Up/Down to choose
and Enter or Tab to replace the typed shorthand. The special `{{cursor}}` marker in
a replacement controls where the editor caret is placed after expansion.

The file can be opened from **Settings -> Edit latex_shortcuts.yaml** and is reloaded
automatically after it is saved.

## Preview cursor synchronization

The LaTeX renderer compiles with SyncTeX enabled. When the editor cursor moves, the
PDF preview follows the corresponding source location without changing the current
preview zoom. This behavior can be disabled with `preview.cursor_sync_enabled`.

## v0.17.0

- Structure items activate on a single click; the selected source line is placed at the top of the editor viewport and Preview follows through SyncTeX.
- Editor scrolling now drives Preview source-position synchronization as well as cursor movement.
- Added a compact LaTeX formatting toolbar above the editor: square **B** button for `\textbf{...}` and a pastel highlight menu using `\colorbox{...}{...}`. `Ctrl+B` applies the same bold wrapper to the selected text.
- Preview-only package injection recognizes `algorithm`/`algorithmic` and toolbar `\colorbox` usage, adding `algorithm`, `algpseudocode`, or `xcolor` only to the temporary preview source when needed.
- Per-file cursor, horizontal scroll, and vertical scroll positions are remembered when tabs are switched/closed and persisted across application restarts.
- Large-file editor performance was improved by applying block direction/line-height/wrap layout only to changed blocks during normal typing instead of walking the entire document after every edit. Full layout is still applied when visual settings change.
- Default editor font size remains 16 and default line height remains 200%.

## v0.18.0

- Keeps a passive caret visible at the last editor cursor position when focus moves to another panel or application.
- Saves/restores main-window position and size together with the existing editor/tab/session state.
- `settings.yaml` changes are no longer applied by autosave or external-file reload; use the **Apply** button shown above the editor while `settings.yaml` is active.
- Keeps the last successful PDF visible when a transient live-LaTeX compile fails while typing.
- Coalesces live-render requests instead of repeatedly killing/restarting LuaLaTeX. Large documents use a longer configurable render debounce to reduce CPU spikes and editor slowdowns.
- Adds `preview.large_document_threshold_chars` and `preview.large_document_debounce_ms` settings.

## v0.18.2 notes

- PDF and image results open with Ubuntu's configured default desktop app.
- YAML files open in the built-in syntax-highlighted editor from Navigator/Search.
- Window geometry plus Navigator/Editor/Preview widths and Navigator/Structure heights are persisted under `~/.config/nd_mind_mirror_project/ui_state.json` with QSettings fallback.
- Live preview repairs incomplete one-line `\colorbox` wrappers only in the temporary preview source, preventing a transient `\color@b@x` runaway from permanently stopping preview.


## v0.19.0 additions

- PDF preview toolbar: Fit, editable zoom percentage, and current/total page status.
- Search: Down moves from the query field to results; Enter activates the highlighted result; double-click still activates files.
- Structure panel now understands both LaTeX headings and YAML key/list hierarchy.
- YAML editor applies nesting-aware indentation after Enter.
