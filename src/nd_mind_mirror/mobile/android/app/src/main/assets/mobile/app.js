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
    this.compileTimer = null;
    this.compileRequestId = 0;

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
    this.folderContextMenu = new WorkspaceFolderContextMenu(
      new LongPressController(),
      (action, path) => this.handleFolderContextAction(action, path),
    );
    this.searchTree = new SearchResultTree(
      document.getElementById("search-results"),
      (path, line) => this.openFile(path, line),
      (element, path) => this.folderContextMenu.bindFolder(element, path),
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
    document.getElementById("preview-refresh").addEventListener("click", () => {
      if (this.isCompilableLatexPath()) {
        this.requestLatexCompile(false, true);
      } else {
        this.loadPreview(true);
      }
    });
    document.getElementById("preview-export").addEventListener("click", () => {
      this.requestLatexCompile(true, true);
    });
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
      document.getElementById("preview-pages").dataset.path = "";
      window.clearTimeout(this.autosaveTimer);
      this.autosaveTimer = window.setTimeout(() => this.saveCurrentFile(), 1000);
      this.scheduleLatexCompile();
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
      this.compileRequestId += 1;
      window.clearTimeout(this.searchTimer);
      window.clearTimeout(this.compileTimer);
      document.getElementById("search-results").replaceChildren();
      document.getElementById("preview-pages").replaceChildren();
      document.getElementById("preview-pages").dataset.path = "";

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

  loadNavigator(path, selectedPath = null) {
    try {
      const data = this.nativeJson(this.bridge.listDirectory(path || ""));
      this.navigatorPath = data.path || "";
      document.getElementById("navigator-path").textContent = "/" + this.navigatorPath;

      const currentSelection =
        selectedPath ||
        (
          this.currentPath &&
          this.parentPath(this.currentPath) === this.navigatorPath
            ? this.currentPath
            : null
        );
      this.renderNavigator(data.entries || [], currentSelection);
      this.setStatus(`Navigator: /${this.navigatorPath}`);
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  renderNavigator(entries, selectedPath = null) {
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
      button.classList.toggle(
        "current-file",
        !entry.is_directory && entry.path === selectedPath,
      );

      const icon = document.createElement("span");
      icon.textContent = entry.is_directory ? "📁" : "📄";
      const name = document.createElement("span");
      name.className = "primary";
      name.textContent = entry.name;

      button.append(icon, name);

      if (entry.is_directory) {
        this.folderContextMenu.bindFolder(button, entry.path);
      }

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

  async handleFolderContextAction(action, folderPath) {
    try {
      if (action === "open_navigator") {
        this.activateTab("navigator");
        this.loadNavigator(folderPath);
        return;
      }

      if (action === "create_latex") {
        await this.createLatexFileInFolder(folderPath);
        return;
      }

      if (action === "create_file") {
        await this.createFileInFolder(folderPath);
        return;
      }

      if (action === "create_folder") {
        await this.createFolderInFolder(folderPath);
        return;
      }

      if (action === "recent_files") {
        await this.openRecentFile();
      }
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  async createLatexFileInFolder(folderPath) {
    const fileName = await this.folderContextMenu.promptText(
      "New LaTeX File",
      "File name:",
      "",
      "document.tex",
    );
    if (!fileName) return;

    const templateData = this.nativeJson(this.bridge.latexTemplates());
    const templates = templateData.templates || [];
    const templateId = await this.folderContextMenu.chooseItem(
      "New LaTeX File",
      "LaTeX template:",
      templates.map((template) => ({
        value: template.id,
        label: template.label,
        secondary: "",
      })),
    );
    if (!templateId) return;

    const created = this.nativeJson(
      this.bridge.createLatexFile(folderPath, fileName, templateId),
    );
    this.activateTab("navigator");
    this.loadNavigator(folderPath, created.path);
    this.setStatus(`Created ${created.path}`);
  }

  async createFileInFolder(folderPath) {
    const fileName = await this.folderContextMenu.promptText(
      "New File",
      "File name:",
      "",
      "notes.txt",
    );
    if (!fileName) return;

    const created = this.nativeJson(
      this.bridge.createFile(folderPath, fileName),
    );
    this.activateTab("navigator");
    this.loadNavigator(folderPath, created.path);
    this.setStatus(`Created ${created.path}`);
  }

  async createFolderInFolder(folderPath) {
    const folderName = await this.folderContextMenu.promptText(
      "New Folder",
      "Folder name:",
      "",
      "folder",
    );
    if (!folderName) return;

    const created = this.nativeJson(
      this.bridge.createFolder(folderPath, folderName),
    );
    this.activateTab("navigator");
    this.loadNavigator(folderPath, created.path);
    this.setStatus(`Created ${created.path}`);
  }

  async openRecentFile() {
    const data = this.nativeJson(this.bridge.recentFiles());
    const path = await this.folderContextMenu.showRecentFiles(data.files || []);
    if (path) this.openFile(path);
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
      document.getElementById("preview-pages").dataset.path = "";
      this.bridge.rememberRecentFile(data.path);
      this.loadNavigator(this.parentPath(data.path), data.path);
      this.activateTab("source");
      if (line) this.jumpToLine(line);
      if (this.isCompilableLatexPath()) this.scheduleLatexCompile(true);
      this.setStatus(`Opened ${data.path}`);
    } catch (error) {
      this.setStatus(error.message, true);
    }
  }

  saveCurrentFile() {
    if (!this.currentPath || !this.dirty) return;
    try {
      this.nativeJson(this.bridge.writeFile(this.currentPath, this.sourceEditor.getValue()));
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

  isCompilableLatexPath() {
    return this.currentPath && /\.(tex|ltx)$/i.test(this.currentPath);
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
    this.sourceEditor.getValue().split("\n").forEach((line, index) => {
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
    this.sourceEditor.jumpToLine(lineNumber);
  }

  loadVisual() {
    const container = document.getElementById("visual-content");
    if (!this.isLatexPath()) {
      container.className = "visual-content empty-state";
      container.textContent = "Open a LaTeX file.";
      return;
    }

    this.visualRenderer.render(
      container,
      this.sourceEditor.getValue(),
      this.currentPath,
    );
  }

  scheduleLatexCompile(shortDelay = false) {
    window.clearTimeout(this.compileTimer);
    if (!this.isCompilableLatexPath()) return;

    this.compileTimer = window.setTimeout(
      () => this.runLatexCompile(false),
      shortDelay ? 420 : 1500,
    );
  }

  requestLatexCompile(exportPdf = false, immediate = false) {
    window.clearTimeout(this.compileTimer);
    if (!this.isCompilableLatexPath()) {
      if (exportPdf) this.setStatus("Open a .tex or .ltx file to export PDF.", true);
      return;
    }

    if (immediate) {
      this.runLatexCompile(exportPdf);
      return;
    }

    this.compileTimer = window.setTimeout(
      () => this.runLatexCompile(exportPdf),
      1500,
    );
  }

  runLatexCompile(exportPdf) {
    if (!this.isCompilableLatexPath()) return;

    this.compileRequestId += 1;
    const requestId = this.compileRequestId;
    const pages = document.getElementById("preview-pages");
    const state = document.getElementById("preview-state");
    const compileButton = document.getElementById("preview-refresh");
    const exportButton = document.getElementById("preview-export");

    compileButton.disabled = true;
    exportButton.disabled = true;
    state.textContent = exportPdf ? "Compiling for export…" : "Compiling locally…";

    if (this.currentTab === "preview") {
      pages.className = "preview-pages empty-state";
      pages.textContent =
        "Compiling locally with Tectonic… The first compile may download TeX packages once.";
    }

    try {
      this.bridge.requestLatexCompile(
        requestId,
        this.currentPath,
        this.sourceEditor.getValue(),
        Boolean(exportPdf),
      );
    } catch (error) {
      compileButton.disabled = false;
      exportButton.disabled = false;
      state.textContent = "Compile failed";
      this.setStatus(error.message, true);
    }
  }

  receiveCompileResult(requestId, rawResult) {
    let data;
    try {
      data = JSON.parse(String(rawResult || "{}"));
    } catch (_error) {
      data = {
        ok: false,
        exported: false,
        error: "Invalid compiler response from Android.",
        log: "",
      };
    }

    const isExport = Boolean(data.exported);
    if (!isExport && Number(requestId) !== this.compileRequestId) return;

    const compileButton = document.getElementById("preview-refresh");
    const exportButton = document.getElementById("preview-export");
    const state = document.getElementById("preview-state");
    compileButton.disabled = false;
    exportButton.disabled = false;

    if (!data.ok) {
      state.textContent = "Compile failed";
      if (data.source_path === this.currentPath || !data.source_path) {
        this.showCompileError(data.error || "Tectonic compilation failed.", data.log || "");
      }
      this.setStatus(data.error || "Tectonic compilation failed.", true);
      return;
    }

    if (data.source_path === this.currentPath && data.preview_available) {
      this.renderCompiledPreview(Number(data.page_count) || 0);
    }

    if (isExport) {
      const target = data.exported_path || "PDF";
      state.textContent = "Compiled and exported";
      this.setStatus(`Exported PDF: ${target}`);
    } else {
      state.textContent = `Compiled • ${data.page_count || 0} page${Number(data.page_count) === 1 ? "" : "s"}`;
      this.setStatus(`Compiled locally: ${this.currentPath}`);
    }
  }

  showCompileError(message, log) {
    const pages = document.getElementById("preview-pages");
    pages.replaceChildren();
    pages.className = "preview-pages compile-error-view";

    const heading = document.createElement("strong");
    heading.textContent = String(message || "Compile failed.");
    pages.appendChild(heading);

    const usefulLog = String(log || "").trim();
    if (usefulLog) {
      const details = document.createElement("details");
      details.className = "compile-log";
      const summary = document.createElement("summary");
      summary.textContent = "Compiler log";
      const pre = document.createElement("pre");
      pre.textContent = usefulLog;
      details.append(summary, pre);
      pages.appendChild(details);
    }
  }

  loadPreview(force) {
    const pages = document.getElementById("preview-pages");
    const state = document.getElementById("preview-state");
    const exportButton = document.getElementById("preview-export");

    if (!this.currentPath || !(/\.(tex|ltx|tikz|pdf)$/i.test(this.currentPath))) {
      pages.className = "preview-pages empty-state";
      pages.textContent = "Open a LaTeX file or PDF.";
      state.textContent = "";
      exportButton.disabled = true;
      return;
    }

    exportButton.disabled = !this.isCompilableLatexPath();

    if (!this.isCompilableLatexPath()) {
      this.loadStoredPdfPreview(force);
      return;
    }

    if (force) {
      this.runLatexCompile(false);
      return;
    }

    try {
      const compiled = this.nativeJson(this.bridge.compiledPreviewInfo(this.currentPath));
      if (compiled.available) {
        this.renderCompiledPreview(compiled.page_count || 0);
        return;
      }
    } catch (_error) {
      // A missing compiled preview is expected before the first local compile.
    }

    this.scheduleLatexCompile(true);
    pages.className = "preview-pages empty-state";
    pages.textContent = "Preparing local LaTeX preview…";
    state.textContent = "Waiting for local compile…";
  }

  renderCompiledPreview(pageCount) {
    const pages = document.getElementById("preview-pages");
    const state = document.getElementById("preview-state");

    pages.replaceChildren();
    pages.className = "preview-pages";
    pages.dataset.path = this.currentPath;
    pages.dataset.kind = "compiled";
    state.textContent = `Compiled • ${pageCount} page${pageCount === 1 ? "" : "s"}`;

    this.loadCompiledPreviewPagesSequentially(1, pageCount, pages, this.currentPath);
  }

  loadCompiledPreviewPagesSequentially(pageNumber, pageCount, container, sourcePath) {
    if (pageNumber > pageCount || sourcePath !== this.currentPath) return;

    window.setTimeout(() => {
      try {
        const data = this.nativeJson(
          this.bridge.compiledPreviewPage(sourcePath, pageNumber),
        );
        const image = document.createElement("img");
        image.className = "preview-page";
        image.alt = `Compiled preview page ${pageNumber}`;
        image.src = data.data_url;
        container.appendChild(image);
        this.loadCompiledPreviewPagesSequentially(
          pageNumber + 1,
          pageCount,
          container,
          sourcePath,
        );
      } catch (error) {
        this.setStatus(error.message, true);
      }
    }, 0);
  }

  loadStoredPdfPreview(force) {
    const pages = document.getElementById("preview-pages");
    const state = document.getElementById("preview-state");

    if (!force && pages.dataset.path === this.currentPath && pages.children.length) {
      return;
    }

    try {
      pages.className = "preview-pages";
      pages.textContent = "Loading local PDF…";
      const info = this.nativeJson(this.bridge.previewInfo(this.currentPath));
      pages.replaceChildren();

      if (!info.available) {
        pages.className = "preview-pages empty-state";
        pages.textContent = `No local PDF found at ${info.pdf_path}.`;
        state.textContent = "No PDF";
        return;
      }

      pages.dataset.path = this.currentPath;
      pages.dataset.kind = "stored";
      state.textContent = `${info.page_count} page${info.page_count === 1 ? "" : "s"}`;
      this.loadStoredPreviewPagesSequentially(
        1,
        info.page_count,
        pages,
        this.currentPath,
      );
    } catch (error) {
      pages.className = "preview-pages error-state";
      pages.textContent = error.message;
      state.textContent = "Preview failed";
    }
  }

  loadStoredPreviewPagesSequentially(pageNumber, pageCount, container, sourcePath) {
    if (pageNumber > pageCount || sourcePath !== this.currentPath) return;

    window.setTimeout(() => {
      try {
        const data = this.nativeJson(this.bridge.previewPage(sourcePath, pageNumber));
        const image = document.createElement("img");
        image.className = "preview-page";
        image.alt = `Preview page ${pageNumber}`;
        image.src = data.data_url;
        container.appendChild(image);
        this.loadStoredPreviewPagesSequentially(
          pageNumber + 1,
          pageCount,
          container,
          sourcePath,
        );
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
window.mindMirrorNativeLatexResource = (requestId, result) => {
  ui.graphicRenderer.receive(requestId, result);
};
window.mindMirrorNativeCompileResult = (requestId, result) => {
  ui.receiveCompileResult(requestId, result);
};
ui.start();
