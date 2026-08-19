# nd_mind_mirror_project

A PySide6/Qt LaTeX editor with a filesystem navigator, tabbed editor,
live LuaLaTeX preview, persistent state, fuzzy file search, and PDF export.

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
  line_height_percent: 120
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
