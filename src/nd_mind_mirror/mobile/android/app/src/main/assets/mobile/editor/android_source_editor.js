"use strict";

/**
 * CodeMirror-backed Android Source editor with filename-aware modes and
 * Ubuntu-style soft-wrap continuation markers.
 */
class AndroidSourceEditor {
  constructor(textarea) {
    this.textarea = textarea;
    this.path = "";
    this.changeListeners = [];
    this.suppressChanges = false;
    this.wrapRefreshTimer = null;

    this.editor = CodeMirror.fromTextArea(textarea, {
      mode: null,
      lineWrapping: true,
      lineNumbers: false,
      gutters: ["source-wrap-gutter"],
      indentUnit: 3,
      tabSize: 3,
      indentWithTabs: false,
      viewportMargin: 18,
      inputStyle: "textarea",
      spellcheck: true,
      autocorrect: true,
      autocapitalize: false,
    });

    const wrapper = this.editor.getWrapperElement();
    wrapper.classList.add("android-source-codemirror");
    this.wrapMarkerLayer = document.createElement("div");
    this.wrapMarkerLayer.className = "cm-wrap-marker-layer";
    wrapper.appendChild(this.wrapMarkerLayer);

    this.editor.on("change", () => {
      this.scheduleWrapMarkers();
      if (this.suppressChanges) return;
      this.changeListeners.forEach((listener) => listener());
    });
    this.editor.on("scroll", () => this.scheduleWrapMarkers());
    this.editor.on("viewportChange", () => this.scheduleWrapMarkers());
    this.editor.on("refresh", () => this.scheduleWrapMarkers());
    window.addEventListener("resize", () => {
      this.refresh();
    });
  }

  onChange(listener) {
    this.changeListeners.push(listener);
  }

  getValue() {
    return this.editor.getValue();
  }

  setSource(path, source) {
    this.path = String(path || "");
    this.suppressChanges = true;
    try {
      this.editor.setOption("mode", this.modeForPath(this.path));
      this.editor.setValue(String(source ?? ""));
      this.editor.clearHistory();
      this.editor.setCursor({ line: 0, ch: 0 });
      this.editor.scrollTo(0, 0);
    } finally {
      this.suppressChanges = false;
    }
    this.refresh();
  }

  clear() {
    this.setSource("", "");
  }

  focus() {
    this.editor.focus();
  }

  jumpToLine(lineNumber) {
    const last = Math.max(this.editor.lineCount() - 1, 0);
    const line = Math.min(Math.max((Number(lineNumber) || 1) - 1, 0), last);
    this.editor.setCursor({ line, ch: 0 });
    this.editor.scrollIntoView({ line, ch: 0 }, 120);
    this.editor.focus();
  }

  refresh() {
    window.setTimeout(() => {
      this.editor.refresh();
      this.scheduleWrapMarkers(true);
    }, 0);
  }

  addLineWidget(line, node, options = {}) {
    const index = Math.min(
      Math.max(Number(line) || 0, 0),
      Math.max(this.editor.lineCount() - 1, 0),
    );
    return this.editor.addLineWidget(index, node, {
      above: false,
      coverGutter: false,
      noHScroll: true,
      ...options,
    });
  }

  modeForPath(path) {
    const name = String(path || "").split("/").pop().toLowerCase();
    const suffix = name.includes(".") ? name.split(".").pop() : "";

    if (["tex", "ltx", "tikz", "sty", "cls", "bib"].includes(suffix)) return "stex";
    if (["py", "pyw", "pyi"].includes(suffix)) return "python";
    if (["yaml", "yml"].includes(suffix)) return "yaml";
    if (["json", "jsonc"].includes(suffix)) return { name: "javascript", json: true };
    if (["js", "jsx", "mjs", "cjs"].includes(suffix)) return "javascript";
    if (["ts", "tsx"].includes(suffix)) return { name: "javascript", typescript: true };
    if (["java"].includes(suffix)) return "text/x-java";
    if (["kt", "kts"].includes(suffix)) return "text/x-kotlin";
    if (["c", "h"].includes(suffix)) return "text/x-csrc";
    if (["cc", "cpp", "cxx", "hpp"].includes(suffix)) return "text/x-c++src";
    if (["cs"].includes(suffix)) return "text/x-csharp";
    if (["sh", "bash", "zsh", "fish"].includes(suffix) || name === ".bashrc" || name === ".zshrc") {
      return "shell";
    }
    if (["html", "htm", "xhtml"].includes(suffix)) return "htmlmixed";
    if (["xml", "svg"].includes(suffix)) return "xml";
    if (["css", "scss", "less"].includes(suffix)) return "css";
    if (["md", "markdown"].includes(suffix)) return "markdown";
    if (suffix === "toml") return "toml";
    if (["ini", "cfg", "conf", "properties", "env"].includes(suffix) || name.startsWith(".env")) {
      return "properties";
    }
    if (suffix === "sql") return "text/x-sql";
    return null;
  }

  scheduleWrapMarkers(immediate = false) {
    window.clearTimeout(this.wrapRefreshTimer);
    this.wrapRefreshTimer = window.setTimeout(
      () => this.renderWrapMarkers(),
      immediate ? 0 : 45,
    );
  }

  renderWrapMarkers() {
    const editor = this.editor;
    const viewport = editor.getViewport();
    const scroll = editor.getScrollInfo();
    const lineHeight = editor.defaultTextHeight();
    const fragment = document.createDocumentFragment();

    for (let line = viewport.from; line < viewport.to; line += 1) {
      const text = editor.getLine(line) || "";
      const start = editor.charCoords({ line, ch: 0 }, "local");
      const end = editor.charCoords({ line, ch: text.length }, "local");
      const rows = Math.max(1, Math.round((end.bottom - start.top) / lineHeight));

      for (let row = 1; row < rows; row += 1) {
        const marker = document.createElement("span");
        marker.className = "cm-wrap-marker";
        marker.textContent = "↳";
        marker.style.top = `${start.top + row * lineHeight - scroll.top}px`;
        fragment.appendChild(marker);
      }
    }

    this.wrapMarkerLayer.replaceChildren(fragment);
  }
}
