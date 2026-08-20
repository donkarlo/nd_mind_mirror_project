# nd_tikz_sketch v0.2.0

This bundle contains:

- `ipad/`: native iPadOS SwiftUI + PencilKit app for Apple Pencil.
- `bridge/`: Ubuntu WebSocket service that owns the real TikZ file, writes it atomically, renders it, and sends the clean result back to the iPad.
- It is compatible with `nd_mind_mirror_project v0.23.0`, which watches recursive `\\input`/`\\include` dependencies so the parent LaTeX preview rerenders when the iPad changes a `.tikz` file.

## Live data path

```text
Apple Pencil
    ↓
iPad nd_tikz_sketch
    ↓ WebSocket
Ubuntu nd_tikz_bridge
    ├─ writes ~/Dropbox/.../diagram.tikz
    ├─ LuaLaTeX → PNG → iPad clean preview
    └─ filesystem change → Mind Mirror parent LaTeX preview rerender
         ↓
       Dropbox syncs the real files normally
```

## v0.2 handwriting-to-node text

The app now has a **Handwriting text** tool. Write a word or short phrase with Apple Pencil and pause for about 0.9 seconds. Apple Vision recognizes the handwriting.

- If the handwriting center falls inside a normal editable TikZ `\\node[...] (...) at (...) {...};`, the recognized text is inserted into that node.
- Rectangle and ellipse strokes created by this app are now generated as real named TikZ nodes (`ndsketchNode1`, `ndsketchNode2`, ...), so handwriting can be inserted into them reliably.
- If the handwriting is not inside a parsed node, it becomes a standalone TikZ text node at the handwritten location.
- Existing complex TikZ that cannot be parsed is never rewritten just to guess a node; the fallback is a standalone label, preserving source safety.
- The original Pencil handwriting remains visible until Ubuntu returns the freshly rendered TikZ image, then the handwritten overlay is cleared and replaced by the clean render.

Example:

```latex
\node[draw, ellipse, minimum width=2cm, minimum height=1cm]
    (ndsketchNode1) at (5,4) {State};
```

The recognizer uses the on-device Apple Vision framework. Recognition quality depends on handwriting and the languages supported by the installed iPadOS version.
