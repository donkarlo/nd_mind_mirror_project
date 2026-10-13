# Mind Mirror iPad TikZ editor

TikZ editing uses the same ND Graphic iPad app and the same reverse TCP connection as image editing. Ubuntu chooses the editor automatically from the Source/Visual context command; there is no manual Image/TikZ mode switch.

## Desktop workflow

- **Create TikZ in iPad…** creates a collision-safe child such as `tikz.tex`, inserts the matching `\\input{...}`, and opens the iPad TikZ editor.
- **Edit TikZ in iPad…** opens the referenced child directly.
- The child source remains canonical. iPad edits are saved to that source over the shared TCP 8768 session.
- LaTeX Visual mode renders a TikZ child referenced through `\\input`/`\\include` while preserving the original input command when Visual is serialized back to Source.
- Preview materializes workspace-rooted references such as `/nd_language_ai_project/...` only in the temporary LuaLaTeX source; user files remain portable relative to `search.default_path`.

## Canvas and direct manipulation

The logical iPad TikZ canvas defaults are configured in `settings.yaml`:

```yaml
graphic:
  tikz:
    canvas_width: 760
    canvas_height: 980
```

The gear menu provides **Canvas size…**, **Auto layout**, and **Source**. There is no manual Render button.

- Rectangle and Triangle have their own tools. Circle/Ellipse share one icon-only tool: drawing or resizing a round shape selects circle versus ellipse automatically from its visible proportions. Dragging a circle's resize handle into a non-round proportion turns it into an ellipse, while restoring equal visible dimensions turns it back into a circle. Both use one saved style. A new shape immediately opens an inline Pencil Scribble text editor.
- The tool strip shows icon-only Rectangle, Circle/Ellipse, Triangle, Straight, Curve, and Polyline tools. Each tool has its own inline saved-style thumbnails, with the actual fill, border, and letter A in the label color, or the connector's line color/pattern. The adjacent small plus icon saves the current appearance without a Styles menu or naming dialog. Long-press a thumbnail to delete it; presets persist between sessions.
- Double-tapping the canvas with Apple Pencil opens a floating tool-and-saved-style palette next to the Pencil, similar to the Image workspace. Finger double-tap on an existing element still edits its label.
- The freehand stroke is shown while the Pencil moves, then a closed outline on empty TikZ canvas is classified as the nearest simple rectangle, circle/ellipse, or triangle regardless of the selected tool. The inserted node uses the hand-drawn bounding dimensions, the saved appearance for its detected shape, and immediately opens its Scribble label editor. Unclosed Pencil gestures retain explicit tool dragging behavior, and existing connector/resize gestures are not reinterpreted.
- **Undo / Redo** has an independent 200-step history of TikZ source revisions. Consecutive changes made while dragging a single item are grouped; commands also support Command-Z and Command-Shift-Z.
- **Auto layout** uses actual node sizes plus compact gaps rather than spreading nodes to the drawing area's entire width. The main toolbar scrolls on narrow screens.
- Single Pencil/finger tap always selects a shape or connector.
- Finger double-tap selects the element and opens a compact floating label editor at the top of the canvas. Pencil Scribble and keyboard input update the selected element without inserting a toolbar row or moving the drawing surface. Tapping elsewhere commits the draft; pressing Enter/Done is optional.
- The TikZ workspace ignores the keyboard safe-area inset. iPadOS may still show its own system input assistant, but that system overlay no longer pushes the Mind Mirror canvas upward.
- A selected shape has eight resize handles plus a distinct blue move handle.
- The toolbar provides adjacent icon-only Straight, Curve, and Polyline connector tools. Drag with Apple Pencil from one shape to another. Curve connectors expose two Bézier control handles when selected. Polyline connectors expose draggable bend points; long-press the connector and choose **Add bend point here**, and long-press a bend handle to remove it. Double tap remains reserved for label editing.
- The style toolbar keeps the most recently relevant shape/connector controls visible even after selection is cleared, so the canvas does not jump vertically.
- Shape and connector property rows use the same fixed toolbar height. Wide connector controls scroll horizontally instead of increasing the row height.
- Labels use the floating canvas editor only; the property toolbar does not contain a label field.
- Connector target hit testing has a Pencil-friendly tolerance, while ellipse selection uses ellipse geometry rather than only its bounding rectangle.
- Delete is intentionally kept out of the toolbar. Long-press the selected shape or connector and choose **Delete**; deleting a shape also removes its connected simple connectors.
- Long press opens one centralized context menu. Shapes support Edit label, Duplicate, Bring to Front, Send to Back, and Delete. Connectors support Edit label, Bring to Front, Send to Back, and Delete; Polyline connectors additionally support **Add bend point here**.
- Fill, border, connector line, and label text colors use the native SwiftUI color picker rather than a fixed preset palette.
- Connector stroke supports **Solid / Dashed** and arrowheads support **Filled / Empty**. Empty uses the same closed triangular outline as Filled but leaves the triangle interior unfilled.
- Style edits use explicit bindings for the selected element, so selecting an element no longer re-applies stale style state to another element.
- Arrow syntax generated by the editor automatically adds `\\usetikzlibrary{arrows.meta}` to the TikZ fragment. Ellipse syntax automatically adds `\\usetikzlibrary{shapes.geometric}`.
- Canvas size is written as `% nd_mind_mirror_canvas: WIDTHxHEIGHT` so a file can retain a per-diagram canvas size while newly opened diagrams inherit the configured default.
- The raster workspace remains alive but non-interactive behind TikZ so switching editors does not destroy the shared TCP listener.
- The iPad vector canvas updates immediately while canonical TikZ uploads are limited to 20 updates per second. The newest pending edit is always retained and flushed on explicit render/close, reducing TCP traffic and filesystem churn during continuous Pencil drags.
- A bridge `update_tikz` now performs only the atomic canonical save, desktop update event, and acknowledgement. It does not start LuaLaTeX for every intermediate drag revision. Full bridge rendering remains available for initial open or an explicit render request.
- Ubuntu reloads an already-open canonical TikZ Source tab immediately. Source/Visual graphic projections are throttled independently at about 80 ms so continuous movement still produces live frames, while the full PDF preview is compiled only after roughly 650 ms of edit inactivity.
- Source and Visual share one TikZ preview coordinator/cache. The conservative node/connector subset generated by the iPad is drawn directly with Qt, avoiding LuaLaTeX entirely during normal live manipulation. Unsupported complex TikZ falls back to one serialized LuaLaTeX worker, which retains only the newest pending generation and never allows an old render to overwrite a newer frame.
- Visual mode refreshes referenced TikZ images in place instead of requiring a Source→Visual view switch or a full Visual document rebuild.
- In Source mode, a standalone `\\input{...}` or `\\include{...}` that resolves to a TikZ child is rendered directly below that canonical source line.

## Source safety

Visual manipulation targets named nodes of the form:

```latex
\\node[options] (name) at (x,y) {label};
```

and named-node connector routes of these canonical forms:

```latex
\\draw[options] (source) -- node[...] {label} (target);
\\draw[options] (source) .. controls (c1x,c1y) and (c2x,c2y) .. node[...] {label} (target);
\\draw[options] (source) -- (x1,y1) -- (x2,y2) -- node[...] {label} (target);
```

The first is Straight, the second is a cubic Bézier Curve, and the third is a Polyline with any number of editable bend points. These are standard TikZ path syntaxes. Unrelated TikZ options are preserved. Unsupported complex TikZ remains editable through **Source** and is not normalized by guesswork.
