# Mind Mirror iPad TikZ editor

The active iPad package has two independent workspaces:

- **Image** keeps the existing PencilKit/raster workflow unchanged.
- **TikZ** edits canonical `.tikz` files and `.tex` files that contain a `tikzpicture`.

The workspace switch is a compact **Image / TikZ** control beside the Image header settings gear. The TikZ file browser is optional and starts collapsed; normal use begins from the desktop Source/Visual context menu.

The Ubuntu desktop starts a separate WebSocket TikZ bridge on port `8765`. The iPad treats the connection as live only after receiving the bridge `hello` handshake. Older saved `ws://ubuntu.local:8765/ws` defaults are migrated to `ws://donkarlo-uni-laptop.local:8765/ws`; the address can still be changed from the TikZ connection sheet.

## Desktop-driven workflow

Right-click in a LaTeX **Source** or **Visual** editor:

- **Create TikZ in iPad…** creates a collision-safe `tikz.tex`, `tikz_2.tex`, ... beside the parent `.tex`, inserts the matching `\input{...}` at the clicked source location, and asks the connected iPad to open the new child.
- **Edit TikZ in iPad…** appears when the clicked `\input{...}`/`\include{...}` resolves to a child source containing `\begin{tikzpicture}`; it opens that existing child on the iPad without changing the parent document.

The child file starts as:

```latex
\begin{tikzpicture}

\end{tikzpicture}
```

and the parent receives, for example:

```latex
\input{tikz.tex}
```

The same resolver supports normal relative inputs, workspace-rooted `/project/...` inputs relative to `search.default_path`, and real absolute paths as a fallback.

## Canonical source workflow

The TikZ source file itself remains canonical. The bridge writes each accepted edit atomically and renders a temporary standalone preview without inserting wrapper code into the real file.

A parent LaTeX document can therefore include a diagram fragment directly:

```latex
\input{/nd_robotic_ai_learning_project/path/to/diagram.tex}
```

with `diagram.tex` containing only the diagram:

```latex
\begin{tikzpicture}
  \node[draw, rectangle] (input) at (2,8) {Input};
  \node[draw, ellipse] (output) at (10,4) {Output};
  \draw[->] (input) -- node[midway, fill=white] {process} (output);
\end{tikzpicture}
```

## Optional TikZ file browser

The collapsed sidebar is only a manual browser for already existing TikZ files. Open it when you want to search or switch to another diagram without going through the parent document. It is not required for Create/Edit from Mind Mirror.

## Visual operations

The TikZ workspace supports the conservative named-node subset intentionally, so unsupported complex TikZ is not rewritten by guesswork.

- Drag a named node to rewrite its `at (x,y)` coordinate.
- Add rectangle or ellipse nodes with generated stable names.
- Enter **Add edge**, tap a source node, then a target node.
- Add a label while creating an edge.
- Select existing edges from the Inspector and change their labels.
- Select a node and change its text label.
- Run **Auto layout**. DAGs receive deterministic layered placement; cyclic graphs receive deterministic circular placement.
- Open **Source** at any time for direct raw TikZ editing.
- Every accepted edit is saved back to the same canonical `.tex`/`.tikz` file and rerendered.

## Source-safety boundary

Visual node manipulation targets commands shaped like:

```latex
\node[options] (name) at (x,y) {label};
```

and visual edge manipulation targets simple named-node edges shaped like:

```latex
\draw[options] (source) -- node[...] {label} (target);
```

Other TikZ source remains visible in the rendered preview and raw Source editor but is not automatically normalized or rewritten.
