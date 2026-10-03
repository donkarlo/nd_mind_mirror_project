"use strict";

/**
 * Adds Source-mode previews as CodeMirror line widgets. Widgets reserve real
 * editor space, so graphics, formulas and tables never cover canonical source.
 */
class SourceLatexPreviewController {
  constructor(
    sourceEditor,
    extractor,
    mathRenderer,
    tableRenderer,
    graphicRenderer,
  ) {
    this.sourceEditor = sourceEditor;
    this.extractor = extractor;
    this.mathRenderer = mathRenderer;
    this.tableRenderer = tableRenderer;
    this.graphicRenderer = graphicRenderer;
    this.widgets = [];
    this.refreshTimer = null;
    this.path = "";
  }

  setSource(path, source) {
    this.path = String(path || "");
    this.refresh(source, true);
  }

  sourceChanged(source) {
    window.clearTimeout(this.refreshTimer);
    this.refreshTimer = window.setTimeout(() => this.refresh(source, false), 260);
  }

  clear() {
    window.clearTimeout(this.refreshTimer);
    this.clearWidgets();
    this.path = "";
  }

  refresh(source, immediate) {
    window.clearTimeout(this.refreshTimer);
    if (!this.isLatexPath(this.path)) {
      this.clearWidgets();
      return;
    }

    if (!immediate) {
      this.refreshTimer = window.setTimeout(() => this.rebuild(source), 0);
      return;
    }
    this.rebuild(source);
  }

  rebuild(source) {
    this.clearWidgets();

    const previews = this.extractor.extract(source).slice(0, MAX_SOURCE_PREVIEWS);
    previews.forEach((preview) => {
      const node = this.createPreviewNode(preview);
      if (!node) return;

      let widget = null;
      const onLayoutChanged = () => {
        widget?.changed();
        this.sourceEditor.scheduleWrapMarkers(true);
      };

      if (preview.kind === "graphic") {
        node.replaceChildren();
        preview.graphics.forEach((graphic, index) => {
          node.appendChild(
            this.graphicRenderer.create(
              this.path,
              graphic.path,
              graphic.options,
              index === preview.graphics.length - 1 ? preview.caption : "",
              onLayoutChanged,
            ),
          );
        });
      }

      widget = this.sourceEditor.addLineWidget(preview.anchorLine, node);
      this.widgets.push(widget);
    });

    this.sourceEditor.refresh();
  }

  createPreviewNode(preview) {
    const root = document.createElement("div");
    root.className = `source-latex-preview source-latex-preview-${preview.kind}`;

    if (preview.kind === "graphic") {
      return root;
    }

    if (preview.kind === "math") {
      root.appendChild(this.mathRenderer.create(preview.raw, true));
      return root;
    }

    if (preview.kind === "inline-math") {
      const row = document.createElement("div");
      row.className = "source-inline-math-row";
      preview.formulas.forEach((formula) => {
        row.appendChild(this.mathRenderer.create(formula, false));
      });
      root.appendChild(row);
      return root;
    }

    if (preview.kind === "table") {
      root.appendChild(this.tableRenderer.create(preview.raw));
      return root;
    }

    return null;
  }

  clearWidgets() {
    this.widgets.forEach((widget) => {
      try {
        widget.clear();
      } catch (_error) {
        // A CodeMirror document replacement can invalidate an old widget.
      }
    });
    this.widgets = [];
  }

  isLatexPath(path) {
    return /\.(tex|ltx|tikz)$/i.test(String(path || ""));
  }
}

const MAX_SOURCE_PREVIEWS = 180;
