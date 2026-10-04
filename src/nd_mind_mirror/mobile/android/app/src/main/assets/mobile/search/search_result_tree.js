"use strict";

/**
 * Renders Android search hits as the same root/folder/file hierarchy used by desktop search.
 */
class SearchResultTree {
  constructor(container, openFile, bindFolderContext = null) {
    this.container = container;
    this.openFile = openFile;
    this.bindFolderContext = bindFolderContext;
  }

  render(results, kind) {
    this.container.replaceChildren();
    this.container.className = "search-tree";

    if (!results.length) return;

    const root = this.buildTree(results);
    const rootDetails = document.createElement("details");
    rootDetails.className = "search-tree-directory search-tree-root";
    rootDetails.open = true;

    const summary = document.createElement("summary");
    summary.textContent = "/";
    this.bindDirectoryContext(summary, root.path);
    rootDetails.appendChild(summary);

    const children = document.createElement("div");
    children.className = "search-tree-children";
    this.renderDirectoryChildren(root, children, kind);
    rootDetails.appendChild(children);
    this.container.appendChild(rootDetails);
  }

  showMessage(message, className = "empty-state") {
    this.container.replaceChildren();
    this.container.className = className;
    this.container.textContent = message;
  }

  buildTree(results) {
    const root = this.directoryNode("", "");

    results.forEach((result) => {
      const parts = String(result.path || "").split("/").filter(Boolean);
      if (!parts.length) return;

      let directory = root;
      let directoryPath = "";
      parts.slice(0, -1).forEach((part) => {
        directoryPath = directoryPath ? `${directoryPath}/${part}` : part;
        if (!directory.directories.has(part)) {
          directory.directories.set(
            part,
            this.directoryNode(part, directoryPath),
          );
        }
        directory = directory.directories.get(part);
      });

      const fileName = parts.at(-1);
      if (!directory.files.has(fileName)) {
        directory.files.set(fileName, {
          name: fileName,
          path: result.path,
          hits: [],
        });
      }
      if (result.line) {
        directory.files.get(fileName).hits.push({
          line: result.line,
          snippet: result.snippet || "",
        });
      }
    });

    return root;
  }

  directoryNode(name, path) {
    return {
      name,
      path,
      directories: new Map(),
      files: new Map(),
    };
  }

  bindDirectoryContext(element, path) {
    if (typeof this.bindFolderContext === "function") {
      this.bindFolderContext(element, path);
    }
  }

  renderDirectoryChildren(directory, container, kind) {
    [...directory.directories.values()]
      .sort((first, second) => first.name.localeCompare(second.name))
      .forEach((child) => {
        const details = document.createElement("details");
        details.className = "search-tree-directory";
        details.open = true;

        const summary = document.createElement("summary");
        summary.textContent = child.name;
        this.bindDirectoryContext(summary, child.path);
        details.appendChild(summary);

        const children = document.createElement("div");
        children.className = "search-tree-children";
        this.renderDirectoryChildren(child, children, kind);
        details.appendChild(children);
        container.appendChild(details);
      });

    [...directory.files.values()]
      .sort((first, second) => first.name.localeCompare(second.name))
      .forEach((file) => {
        if (kind === "text" && file.hits.length) {
          container.appendChild(this.renderTextFile(file));
        } else {
          container.appendChild(this.renderFileButton(file));
        }
      });
  }

  renderFileButton(file) {
    const button = document.createElement("button");
    button.className = "search-tree-file search-tree-hit";

    const icon = document.createElement("span");
    icon.className = "search-tree-icon";
    icon.textContent = "📄";

    const name = document.createElement("span");
    name.textContent = file.name;

    button.append(icon, name);
    button.addEventListener("click", () => this.openFile(file.path, null));
    return button;
  }

  renderTextFile(file) {
    const details = document.createElement("details");
    details.className = "search-tree-file-group";
    details.open = true;

    const summary = document.createElement("summary");
    summary.className = "search-tree-hit";
    summary.textContent = file.name;
    details.appendChild(summary);

    const occurrences = document.createElement("div");
    occurrences.className = "search-tree-occurrences";

    file.hits.forEach((hit) => {
      const button = document.createElement("button");
      button.className = "search-tree-occurrence";

      const line = document.createElement("span");
      line.className = "search-tree-line";
      line.textContent = `L${hit.line}`;

      const snippet = document.createElement("span");
      snippet.className = "search-tree-snippet";
      snippet.textContent = hit.snippet;

      button.append(line, snippet);
      button.addEventListener("click", () => this.openFile(file.path, hit.line));
      occurrences.appendChild(button);
    });

    details.appendChild(occurrences);
    return details;
  }
}
