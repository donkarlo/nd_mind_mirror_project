"use strict";

/**
 * Read-only Android Visual projection that follows the Ubuntu block rules for
 * headings, paragraphs, lists, graphics, formulas and safe tabular content.
 */
class LatexVisualRenderer {
  constructor(
    parser,
    inlineRenderer,
    mathRenderer,
    tableRenderer,
    graphicRenderer,
    onSourceLineRequested,
  ) {
    this.parser = parser;
    this.inlineRenderer = inlineRenderer;
    this.mathRenderer = mathRenderer;
    this.tableRenderer = tableRenderer;
    this.graphicRenderer = graphicRenderer;
    this.onSourceLineRequested = onSourceLineRequested;
  }

  render(container, source, sourcePath) {
    container.replaceChildren();
    container.className = "visual-content";

    const blocks = this.parser.parse(source);
    if (!blocks.length) {
      container.className = "visual-content empty-state";
      container.textContent = "No visual content found.";
      return;
    }

    blocks.forEach((block) => {
      const node = this.createBlock(block, sourcePath);
      if (!node) return;
      node.dataset.sourceLine = String(block.sourceLine || 1);
      node.classList.add("visual-source-block");
      node.addEventListener("dblclick", () => {
        if (typeof this.onSourceLineRequested === "function") {
          this.onSourceLineRequested(block.sourceLine || 1);
        }
      });
      container.appendChild(node);
    });
  }

  createBlock(block, sourcePath) {
    if (block.kind === "heading") {
      const heading = document.createElement(this.headingTag(block.command));
      heading.appendChild(this.inlineRenderer.create(block.text));
      return heading;
    }

    if (block.kind === "paragraph") {
      const paragraph = document.createElement("p");
      paragraph.appendChild(this.inlineRenderer.create(block.text));
      return paragraph;
    }

    if (block.kind === "list") {
      const list = document.createElement(block.ordered ? "ol" : "ul");
      list.className = "latex-list";
      block.items.forEach((item) => {
        const li = document.createElement("li");
        li.appendChild(this.inlineRenderer.create(item));
        list.appendChild(li);
      });
      return list;
    }

    if (block.kind === "math") {
      const wrapper = document.createElement("div");
      wrapper.className = "latex-display-block";
      wrapper.appendChild(this.mathRenderer.create(block.raw, true));
      return wrapper;
    }

    if (block.kind === "table") {
      const wrapper = document.createElement("figure");
      wrapper.className = "latex-table-figure";
      wrapper.appendChild(this.tableRenderer.create(block.raw));
      if (block.caption) {
        const caption = document.createElement("figcaption");
        caption.appendChild(this.inlineRenderer.create(block.caption));
        wrapper.appendChild(caption);
      }
      return wrapper;
    }

    if (block.kind === "graphic") {
      const group = document.createElement("div");
      group.className = "latex-graphic-group";
      block.graphics.forEach((graphic, index) => {
        group.appendChild(
          this.graphicRenderer.create(
            sourcePath,
            graphic.path,
            graphic.options,
            index === block.graphics.length - 1 ? block.caption : "",
          ),
        );
      });
      return group;
    }

    if (block.kind === "input") {
      const wrapper = document.createElement("div");
      wrapper.className = "latex-input-block";

      const raw = document.createElement("code");
      raw.className = "latex-input-source";
      raw.textContent = block.raw;
      wrapper.appendChild(raw);

      if (this.mayBeGraphicInput(block.path)) {
        wrapper.appendChild(
          this.graphicRenderer.create(sourcePath, block.path, "", ""),
        );
      }
      return wrapper;
    }

    if (block.kind === "raw") {
      const raw = document.createElement("pre");
      raw.className = "latex-raw";
      raw.textContent = block.raw;
      return raw;
    }

    return null;
  }

  headingTag(command) {
    if (command === "part" || command === "chapter" || command === "section") return "h1";
    if (command === "subsection") return "h2";
    if (command === "subsubsection") return "h3";
    if (command === "paragraph") return "h4";
    return "h5";
  }

  mayBeGraphicInput(path) {
    const value = String(path || "").toLowerCase();
    return (
      value.endsWith(".tikz") ||
      /(?:tikz|figure|graphic|diagram|plot|ontology|map|architecture)/.test(value)
    );
  }
}
