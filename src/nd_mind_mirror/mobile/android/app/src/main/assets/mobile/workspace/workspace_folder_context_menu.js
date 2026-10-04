"use strict";

/**
 * Phone-sized folder action sheet used by Navigator and Search long-press gestures.
 */
class WorkspaceFolderContextMenu {
  constructor(longPressController, onAction) {
    this.longPressController = longPressController;
    this.onAction = onAction;
    this.activeOverlay = null;
  }

  bindFolder(element, path) {
    this.longPressController.bind(element, () => this.showFolder(path));
  }

  async showFolder(path) {
    const label = path ? `/${path}` : "/";
    const action = await this.showActionList("Folder actions", label, [
      { id: "open_navigator", label: "Open in Navigator" },
      { id: "create_latex", label: "New LaTeX File…" },
      { id: "create_file", label: "New File…" },
      { id: "create_folder", label: "New Folder…" },
      { id: "recent_files", label: "Recent 30 Files…" },
    ]);
    if (action) {
      await this.onAction(action, path);
    }
  }

  showActionList(title, subtitle, actions) {
    return this.present(title, subtitle, (body, finish) => {
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.className = "workspace-sheet-action";
        button.textContent = action.label;
        button.addEventListener("click", () => finish(action.id));
        body.appendChild(button);
      });
    });
  }

  promptText(title, label, initialValue = "", placeholder = "") {
    return this.present(title, label, (body, finish) => {
      const input = document.createElement("input");
      input.className = "workspace-dialog-input";
      input.type = "text";
      input.value = initialValue;
      input.placeholder = placeholder;
      input.autocapitalize = "off";
      input.autocomplete = "off";

      const row = document.createElement("div");
      row.className = "workspace-dialog-buttons";

      const cancel = document.createElement("button");
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => finish(null));

      const create = document.createElement("button");
      create.className = "workspace-dialog-primary";
      create.textContent = "Create";
      create.addEventListener("click", () => {
        const value = input.value.trim();
        if (value) finish(value);
      });

      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          create.click();
        }
      });

      row.append(cancel, create);
      body.append(input, row);
      window.setTimeout(() => {
        input.focus();
        input.select();
      }, 0);
    }, false);
  }

  chooseItem(title, subtitle, items) {
    return this.present(title, subtitle, (body, finish) => {
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "workspace-dialog-empty";
        empty.textContent = "No items available.";
        body.appendChild(empty);
        return;
      }

      items.forEach((item) => {
        const button = document.createElement("button");
        button.className = "workspace-choice";

        const primary = document.createElement("span");
        primary.className = "workspace-choice-primary";
        primary.textContent = item.label;
        button.appendChild(primary);

        if (item.secondary) {
          const secondary = document.createElement("span");
          secondary.className = "workspace-choice-secondary";
          secondary.textContent = item.secondary;
          button.appendChild(secondary);
        }

        button.addEventListener("click", () => finish(item.value));
        body.appendChild(button);
      });
    });
  }

  showRecentFiles(files) {
    return this.chooseItem(
      "Recent 30 Files",
      "Open in Source",
      files.map((file) => ({
        value: file.path,
        label: file.name,
        secondary: this.compactPath(file.path),
      })),
    );
  }

  compactPath(path) {
    const parts = String(path || "").split("/").filter(Boolean);
    if (parts.length <= 4) return "/" + parts.join("/");
    return "…/" + parts.slice(-4).join("/");
  }

  present(title, subtitle, populate, includeCancel = true) {
    this.dismiss();

    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "workspace-dialog-overlay";

      const sheet = document.createElement("section");
      sheet.className = "workspace-dialog-sheet";

      const heading = document.createElement("div");
      heading.className = "workspace-dialog-heading";

      const titleNode = document.createElement("strong");
      titleNode.textContent = title;
      heading.appendChild(titleNode);

      if (subtitle) {
        const subtitleNode = document.createElement("div");
        subtitleNode.className = "workspace-dialog-subtitle";
        subtitleNode.textContent = subtitle;
        heading.appendChild(subtitleNode);
      }

      const body = document.createElement("div");
      body.className = "workspace-dialog-body";

      let completed = false;
      const finish = (value) => {
        if (completed) return;
        completed = true;
        this.dismiss();
        resolve(value);
      };

      populate(body, finish);

      if (includeCancel) {
        const cancel = document.createElement("button");
        cancel.className = "workspace-dialog-cancel";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", () => finish(null));
        body.appendChild(cancel);
      }

      sheet.append(heading, body);
      overlay.appendChild(sheet);
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay) finish(null);
      });

      document.body.appendChild(overlay);
      this.activeOverlay = overlay;
    });
  }

  dismiss() {
    if (!this.activeOverlay) return;
    this.activeOverlay.remove();
    this.activeOverlay = null;
  }
}
