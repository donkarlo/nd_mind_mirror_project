"use strict";

class MindMirrorAndroidUi {
  constructor() {
    this.bridge = window.MindMirrorAndroid;
    this.currentPath = null;
    this.navigatorPath = "";
    this.currentTab = "navigator";
    this.previousTab = "navigator";
    this.searchKind = "files";
    this.searchTimer = null;
    this.searchRequestId = 0;
    this.searchDisplaySignature = "";
    this.dirty = false;
    this.autosaveTimer = null;

    this.currentFile = document.getElementById("current-file");
    this.statusBar = document.getElementById("status-bar");
    this.saveButton = document.getElementById("save-button");

    this.sourceEditor = new AndroidSourceEditor(
      document.getElementById("source-editor"),
    );
    this.mathRenderer = new LatexMathRenderer();
    this.inlineRenderer = new LatexInlineRenderer(this.mathRenderer);
    this.tableRenderer = new LatexTableRenderer(this.inlineRenderer);
    this.graphicRenderer = new LatexGraphicRenderer(this.bridge, this.inlineRenderer);
    this.sourcePreviewController = new SourceLatexPreviewController(
      this.sourceEditor,
      new SourceLatexPreviewExtractor(),
      this.mathRenderer,
      this.tableRenderer,
      this.graphicRenderer,
    );
    this.visualRenderer = new LatexVisualRenderer(
      new LatexDocumentParser(),
      this.inlineRenderer,
      this.mathRenderer,
      this.tableRenderer,
      this.graphicRenderer,
      (line) => {
        this.activateTab("source");
        this.jumpToLine(line);
      },
    );
    this.searchTree = new SearchResultTree(
      document.getElementById("search-results"),
      (path, line) => this.openFile(path, line),
    );

    this.bindEvents();
  }

  start() {
    if (!this.bridge) {
      this.setStatus("Native Android bridge is unavailable.", true);
      return;
    }
    const settings = this.nativeJson(this.bridge.workspaceSettings());
    const active = settings[settings.active_location];
    if (!active?.configured) {
      this.showSettings();
      this.setStatus("Choose a local or Dropbox root folder in Settings.");
      return;
    }
    this.updateSettingsDisplay(settings);
    this.loadNavigator("");
  }

  bindEvents() {
    document.querySelectorAll("#tab-bar [data-tab]").forEach((button) => {
      button.addEventListener("click", () => this.activateTab(button.dataset.tab));
    });

    document.getElementById("navigator-up").addEventListener("click", () => {
      this.loadNavigator(this.parentPath(this.navigatorPath));
    });
    this.saveButton.addEventListener("click", () => this.saveCurrentFile());
    document.getElementById("refresh-button").addEventListener("click", () => this.refreshActiveTab());
    document.getElementById("preview-refresh").addEventListener("click", () => this.loadPreview(true));
    document.getElementById("search-query").addEventListener("input", () => {
      this.scheduleSearch();
    });
    document.getElementById("search-query").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        this.scheduleSearch(true);
      }
    });
    document.querySelectorAll("[data-kind]").forEach((button) => {
      button.addEventListener("click", () => this.setSearchKind(button.dataset.kind));
    });

    this.sourceEditor.onChange(() => {
      this.sourcePreviewController.sourceChanged(this.sourceEditor.getValue());
      this.setDirty(true);
      window.clearTimeout(this.autosaveTimer);
      this.autosaveTimer = window.setTimeout(() => this.saveCurrentFile(), 1000);
    });

    document.getElementById("settings-button").addEventListener("click", () => this.showSettings());
    document.getElementById("settings-back").addEventListener("click", () => this.activateTab(this.previousTab));
    document.getElementById("choose-local-root").addEventListener("click", () => {
      this.bridge.chooseRootFolder("local");
    });
    document.getElementById("choose-dropbox-root").addEventListener("click", () => {
      this.bridge.chooseRootFolder("dropbox");
    });
    document.getElementById("use-local-root").addEventListener("click", () => {
      this.activateStoredRoot("local");
    });
    document.getElementById("use-dropbox-root").addEventListener("click", () => {
      this.activateStoredRoot("dropbox");
    });

    window.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        this.saveCurrentFile();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        this.activateTab("search");
        document.getElementById("search-query").focus();
      }
    });
  }

  nativeJson(raw) {
    let data;
    try {
      data = JSON.parse(String(raw || "{}"));
    } catch (_error) {
      throw new Error("Invalid response from Android.");
    }
    if (data.ok === false) throw new Error(data.error || "Android operation failed.");
    return data;
  }

  setStatus(message, isError = false) {
    const text = String(message || "");
    if (this.statusBar.textContent !== text) {
      this.statusBar.textContent = text;
    }
    this.statusBar.classList.toggle("error-state", Boolean(isError));
  }

  setDirty(dirty) {
    this.dirty = Boolean(dirty);
    document.body.classList.toggle("unsaved", this.dirty);
    this.saveButton.disabled = !this.currentPath || !this.dirty;
  }

  activateTab(name) {
    if (name !== "settings") this.previousTab = name;
    this.currentTab = name;

    document.querySelectorAll("#tab-bar [data-tab]").forEach((button) => {
      button.classList.toggle("active", button.dataset.tab === name);
    });
    document.querySelectorAll(".panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `panel-${name}`);
    });

    if (name === "structure") this.loadStructure();
    if (name === "visual") this.loadVisual();
    if (name === "preview") this.loadPreview(false);
    if (name === "source") this.sourceEditor.refresh();
    if (name === "search") this.scheduleSearch(true);
  }

  showSettings() {
    if (this.currentTab !== "settings") this.previousTab = this.currentTab;
    const settings = this.nativeJson(this.bridge.workspaceSettings());
    this.updateSettingsDisplay(settings);
    this.activateTab("settings");
  }

  updateSettingsDisplay(settings) {
    const local = settings.local || {};
    const dropbox = settings.dropbox || {};
    const active = settings.active_location || "local";

    document.getElementById("local-root-name").textContent =
      local.configured ? local.name : "No folder selected";
    document.getElementById("local-root-uri").textContent =
      local.configured ? local.uri : "";
    document.getElementById("dropbox-root-name").textContent =
      dropbox.configured ? dropbox.name : "No folder selected";
    document.getElementById("dropbox-root-uri").textContent =
      dropbox.configured ? dropbox.uri : "";

    const localButton = document.getElementById("use-local-root");
    const dropboxButton = document.getElementById("use-dropbox-root");
    localButton.disabled = !local.configured;
    dropboxButton.disabled = !dropbox.configured;
    localButton.classList.toggle("active", active === "local");
    dropboxButton.classList.toggle("active", active === "dropbox");
  }

  activateStoredRoot(location) {
    if (this.dirty) {
      this.saveCurrentFile();
      if (this.dirty) return;
    }

    try {
      const result = this.nativeJson(this.bridge.activateRoot(location));
      if (!result.activated) {
        this.setStatus(`No ${location} root folder has been selected yet.`, true);
      }
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  rootChanged() {
    try {
      const settings = this.nativeJson(this.bridge.workspaceSettings());
      const info = this.nativeJson(this.bridge.workspaceInfo());
      this.updateSettingsDisplay(settings);
      this.currentPath = null;
      this.sourcePreviewController.clear();
      this.sourceEditor.clear();
      this.graphicRenderer.clearCache();
      this.currentFile.textContent = "No file open";
      this.setDirty(false);
      this.navigatorPath = "";
      this.searchRequestId += 1;
      window.clearTimeout(this.searchTimer);
      document.getElementById("search-results").replaceChildren();

      if (!info.configured) {
        this.activateTab("settings");
        this.setStatus("Choose a root folder for the active location.");
        return;
      }

      this.activateTab("navigator");
      this.loadNavigator("");
      const label = info.active_location === "dropbox" ? "Dropbox" : "Local Android";
      this.setStatus(`${label} root: ${info.name}`);
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  loadNavigator(path) {
    try {
      const data = this.nativeJson(this.bridge.listDirectory(path || ""));
      this.navigatorPath = data.path || "";
      document.getElementById("navigator-path").textContent = "/" + this.navigatorPath;
      this.renderNavigator(data.entries || []);
      this.setStatus(`Navigator: /${this.navigatorPath}`);
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  renderNavigator(entries) {
    const container = document.getElementById("navigator-list");
    container.replaceChildren();
    if (!entries.length) {
      container.className = "list-view empty-state";
      container.textContent = "This folder is empty.";
      return;
    }

    container.className = "list-view";
    entries.forEach((entry) => {
      const button = document.createElement("button");
      button.className = "list-item";

      const icon = document.createElement("span");
      icon.textContent = entry.is_directory ? "📁" : "📄";
      const name = document.createElement("span");
      name.className = "primary";
      name.textContent = entry.name;

      button.append(icon, name);
      button.addEventListener("click", () => {
        if (entry.is_directory) {
          this.loadNavigator(entry.path);
        } else if (/\.pdf$/i.test(entry.path)) {
          this.currentPath = entry.path;
          this.currentFile.textContent = entry.path;
          this.activateTab("preview");
        } else {
          this.openFile(entry.path);
        }
      });
      container.appendChild(button);
    });
  }

  parentPath(path) {
    const parts = String(path || "").split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  openFile(path, line = null) {
    if (this.dirty && !window.confirm("Discard unsaved Source changes?")) return;

    try {
      const data = this.nativeJson(this.bridge.readFile(path));
      this.currentPath = data.path;
      this.sourceEditor.setSource(data.path, data.content || "");
      this.sourcePreviewController.setSource(data.path, data.content || "");
      this.currentFile.textContent = data.path;
      this.setDirty(false);
      this.activateTab("source");
      if (line) this.jumpToLine(line);
      this.setStatus(`Opened ${data.path}`);
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  saveCurrentFile() {
    if (!this.currentPath || !this.dirty) return;
    try {
      this.nativeJson(this.bridge.writeFile(this.currentPath, this.sourceEditor.value));
      this.setDirty(false);
      document.getElementById("preview-pages").dataset.path = "";
      this.setStatus(`Saved ${this.currentPath}`);
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  isLatexPath() {
    return this.currentPath && /\.(tex|ltx|tikz)$/i.test(this.currentPath);
  }

  loadStructure() {
    const container = document.getElementById("structure-list");
    if (!this.isLatexPath()) {
      container.className = "list-view empty-state";
      container.textContent = "Open a LaTeX file.";
      return;
    }

    const levelMap = {
      part: 0,
      chapter: 0,
      section: 0,
      subsection: 1,
      subsubsection: 2,
      paragraph: 3,
      subparagraph: 4,
    };
    const pattern = /\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\{([^}]*)\}/g;
    const items = [];
    this.sourceEditor.value.split("\n").forEach((line, index) => {
      pattern.lastIndex = 0;
      let match;
      while ((match = pattern.exec(line)) !== null) {
        items.push({
          title: match[2].trim() || "(untitled)",
          line: index + 1,
          level: levelMap[match[1]] ?? 0,
        });
      }
    });

    container.replaceChildren();
    container.className = "list-view";
    items.forEach((item) => {
      const button = document.createElement("button");
      button.className = "list-item structure-item";
      button.style.setProperty("--structure-level", item.level);
      const title = document.createElement("span");
      title.className = "primary";
      title.textContent = item.title;
      const line = document.createElement("span");
      line.className = "secondary";
      line.textContent = `L${item.line}`;
      button.append(title, line);
      button.addEventListener("click", () => {
        this.activateTab("source");
        this.jumpToLine(item.line);
      });
      container.appendChild(button);
    });
    if (!items.length) container.textContent = "No structural items found.";
  }

  jumpToLine(lineNumber) {
    const lines = this.sourceEditor.value.split("\n");
    const target = Math.min(Math.max(Number(lineNumber) || 1, 1), Math.max(lines.length, 1));
    let position = 0;
    for (let index = 0; index < target - 1; index += 1) {
      position += lines[index].length + 1;
    }
    this.sourceEditor.focus();
    this.sourceEditor.setSelectionRange(position, position);
    const ratio = lines.length > 1 ? (target - 1) / (lines.length - 1) : 0;
    this.sourceEditor.scrollTop =
      ratio * Math.max(0, this.sourceEditor.scrollHeight - this.sourceEditor.clientHeight);
    this.sourcePresentation.syncScroll();
  }

  loadVisual() {
    const container = document.getElementById("visual-content");
    if (!this.isLatexPath()) {
      container.className = "visual-content empty-state";
      container.textContent = "Open a LaTeX file.";
      return;
    }

    container.className = "visual-content";
    container.innerHTML = this.renderLatexProjection(this.sourceEditor.value);
  }

  renderLatexProjection(source) {
    const escape = (value) => String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");

    const inline = (value) => {
      let text = escape(value);
      text = text.replace(/\\textbf\{([^{}]*)\}/g, "<strong>$1</strong>");
      text = text.replace(/\\(?:emph|textit)\{([^{}]*)\}/g, "<em>$1</em>");
      text = text.replace(/\$([^$]+)\$/g, '<span class="math">$1</span>');
      return text;
    };

    const result = [];
    let inList = false;
    for (const rawLine of String(source).split("\n")) {
      const line = rawLine.replace(/(^|[^\\])%.*/, "$1").trim();
      if (!line) {
        if (inList) {
          result.push("</ul>");
          inList = false;
        }
        continue;
      }

      const heading = line.match(/^\\(section|subsection|subsubsection)\*?\{([^}]*)\}/);
      if (heading) {
        if (inList) {
          result.push("</ul>");
          inList = false;
        }
        const tag = heading[1] === "section" ? "h1" : heading[1] === "subsection" ? "h2" : "h3";
        result.push(`<${tag}>${inline(heading[2])}</${tag}>`);
        continue;
      }

      const item = line.match(/^\\item\s*(.*)$/);
      if (item) {
        if (!inList) {
          result.push("<ul>");
          inList = true;
        }
        result.push(`<li>${inline(item[1])}</li>`);
        continue;
      }

      if (/^\\(begin|end)\{(document|itemize|enumerate|figure|table)\}/.test(line)) continue;
      result.push(`<p>${inline(line)}</p>`);
    }
    if (inList) result.push("</ul>");
    return result.join("");
  }

  loadPreview(force) {
    const pages = document.getElementById("preview-pages");
    const state = document.getElementById("preview-state");

    if (!this.currentPath || !(/\.(tex|ltx|tikz|pdf)$/i.test(this.currentPath))) {
      pages.className = "preview-pages empty-state";
      pages.textContent = "Open a LaTeX file or PDF.";
      state.textContent = "";
      return;
    }
    if (!force && pages.dataset.path === this.currentPath && pages.children.length) return;

    try {
      pages.className = "preview-pages";
      pages.textContent = "Loading local PDF…";
      const info = this.nativeJson(this.bridge.previewInfo(this.currentPath));
      pages.replaceChildren();

      if (!info.available) {
        pages.className = "preview-pages empty-state";
        pages.textContent =
          `No local PDF found at ${info.pdf_path}. Android works standalone and does not compile LaTeX on Ubuntu.`;
        state.textContent = "No PDF";
        return;
      }

      pages.dataset.path = this.currentPath;
      state.textContent = `${info.page_count} page${info.page_count === 1 ? "" : "s"}`;
      this.loadPreviewPagesSequentially(1, info.page_count, pages);
    } catch (error) {
      pages.className = "preview-pages error-state";
      pages.textContent = error.message;
      state.textContent = "Preview failed";
    }
  }

  loadPreviewPagesSequentially(pageNumber, pageCount, container) {
    if (pageNumber > pageCount) return;
    window.setTimeout(() => {
      try {
        const data = this.nativeJson(this.bridge.previewPage(this.currentPath, pageNumber));
        const image = document.createElement("img");
        image.className = "preview-page";
        image.alt = `Preview page ${pageNumber}`;
        image.src = data.data_url;
        container.appendChild(image);
        this.loadPreviewPagesSequentially(pageNumber + 1, pageCount, container);
      } catch (error) {
        this.setStatus(error.message, true);
      }
    }, 0);
  }

  setSearchKind(kind) {
    this.searchKind = kind === "files" ? "files" : "text";
    document.querySelectorAll("[data-kind]").forEach((button) => {
      button.classList.toggle("active", button.dataset.kind === this.searchKind);
    });
    this.scheduleSearch(true);
  }

  scheduleSearch(immediate = false) {
    window.clearTimeout(this.searchTimer);
    const delay = immediate ? 0 : 280;
    this.searchTimer = window.setTimeout(() => this.runSearch(), delay);
  }

  scheduleSearchAfterIndexProgress() {
    window.clearTimeout(this.searchTimer);
    this.searchTimer = window.setTimeout(() => {
      const query = document.getElementById("search-query").value.trim();
      if (this.currentTab === "search" && query) this.runSearch(true);
    }, 900);
  }

  runSearch(backgroundRefresh = false) {
    const query = document.getElementById("search-query").value.trim();

    if (!query) {
      this.searchRequestId += 1;
      this.searchTree.showMessage("Type to search.");
      this.setStatus("Type to search.");
      return;
    }

    this.searchRequestId += 1;
    const requestId = this.searchRequestId;
    if (!backgroundRefresh) {
      this.searchTree.showMessage("Searching…");
      this.searchDisplaySignature = "";
      this.setStatus(`Searching ${this.searchKind === "files" ? "file names" : "text"}…`);
    }

    try {
      this.bridge.searchAsync(requestId, query, this.searchKind);
    } catch (error) {
      this.searchTree.showMessage(error.message, "error-state");
      this.setStatus(error.message, true);
    }
  }

  receiveSearchResults(requestId, rawResult) {
    if (Number(requestId) !== this.searchRequestId) return;

    try {
      const data = this.nativeJson(rawResult);
      const results = data.results || [];
      const resultCount = results.length;
      const displaySignature = JSON.stringify({
        indexing: Boolean(data.indexing),
        kind: this.searchKind,
        results: results.map((result) => [
          result.path,
          result.line || 0,
          result.snippet || "",
        ]),
      });

      if (displaySignature !== this.searchDisplaySignature) {
        this.searchDisplaySignature = displaySignature;
        if (resultCount) {
          this.searchTree.render(results, this.searchKind);
        } else if (data.indexing) {
          this.searchTree.showMessage("Indexing search data in background…");
        } else {
          this.searchTree.showMessage("No results.");
        }
      }

      if (data.indexing) {
        this.setStatus(
          resultCount
            ? `${resultCount} result(s) • indexing continues in background`
            : "Indexing search data in background…"
        );
        this.scheduleSearchAfterIndexProgress();
      } else {
        this.setStatus(`${resultCount} search result(s)`);
      }
    } catch (error) {
      this.searchTree.showMessage(error.message, "error-state");
      this.setStatus(error.message, true);
    }
  }

  refreshActiveTab() {
    if (this.currentTab === "navigator") return this.loadNavigator(this.navigatorPath);
    if (this.currentTab === "structure") return this.loadStructure();
    if (this.currentTab === "visual") return this.loadVisual();
    if (this.currentTab === "preview") return this.loadPreview(true);
    if (this.currentTab === "search") return this.runSearch();
    if (this.currentTab === "settings") return this.showSettings();
    if (this.currentTab === "source" && this.currentPath) {
      if (this.dirty && !window.confirm("Reload from storage and discard unsaved changes?")) return;
      return this.openFile(this.currentPath);
    }
  }
}

const ui = new MindMirrorAndroidUi();
window.mindMirrorNativeRootChanged = () => ui.rootChanged();
window.mindMirrorNativeSearchResults = (requestId, result) => {
  ui.receiveSearchResults(requestId, result);
};
ui.start();
