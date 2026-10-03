"use strict";

/**
 * Resolves and renders LaTeX graphics asynchronously through the Android SAF
 * bridge so Dropbox-backed images never block the WebView UI thread.
 */
class LatexGraphicRenderer {
  constructor(bridge, inlineRenderer) {
    this.bridge = bridge;
    this.inlineRenderer = inlineRenderer;
    this.nextRequestId = 1;
    this.pending = new Map();
    this.cache = new Map();
  }

  create(sourcePath, rawPath, options = "", caption = "", onLayoutChanged = null) {
    const figure = document.createElement("figure");
    figure.className = "latex-graphic";

    const frame = document.createElement("div");
    frame.className = "latex-graphic-frame";

    const image = document.createElement("img");
    image.className = "latex-graphic-image";
    image.alt = String(rawPath || "");
    image.style.width = `${this.widthRatio(options) * 100}%`;
    image.hidden = true;

    const state = document.createElement("div");
    state.className = "latex-resource-state";
    state.textContent = `Loading ${rawPath}…`;

    frame.append(image, state);
    figure.appendChild(frame);

    if (caption) {
      const figcaption = document.createElement("figcaption");
      figcaption.appendChild(this.inlineRenderer.create(caption));
      figure.appendChild(figcaption);
    }

    this.request(
      sourcePath,
      rawPath,
      (data) => {
        if (data.available && data.data_url) {
          image.onload = () => {
            image.hidden = false;
            state.remove();
            if (typeof onLayoutChanged === "function") onLayoutChanged();
          };
          image.onerror = () => {
            image.hidden = true;
            state.textContent = `Unable to render graphic: ${rawPath}`;
            state.classList.add("error-state");
            if (typeof onLayoutChanged === "function") onLayoutChanged();
          };
          image.src = data.data_url;
          image.title = data.path || rawPath;
        } else {
          image.hidden = true;
          state.textContent = data.error
            ? `Graphic unavailable: ${rawPath} — ${data.error}`
            : `Graphic unavailable: ${rawPath}`;
          state.classList.add("latex-resource-missing");
          if (typeof onLayoutChanged === "function") onLayoutChanged();
        }
      },
    );

    return figure;
  }

  request(sourcePath, rawPath, callback) {
    const key = `${sourcePath}::${rawPath}`;
    if (this.cache.has(key)) {
      window.setTimeout(() => callback(this.cache.get(key)), 0);
      return;
    }

    const requestId = this.nextRequestId;
    this.nextRequestId += 1;
    this.pending.set(requestId, { key, callback });

    try {
      this.bridge.requestLatexGraphic(requestId, sourcePath, rawPath);
    } catch (error) {
      this.pending.delete(requestId);
      callback({
        available: false,
        error: error.message || String(error),
      });
    }
  }

  receive(requestId, rawResult) {
    const pending = this.pending.get(Number(requestId));
    if (!pending) return;
    this.pending.delete(Number(requestId));

    let data;
    try {
      data = JSON.parse(String(rawResult || "{}"));
    } catch (_error) {
      data = {
        ok: false,
        available: false,
        error: "Invalid graphic response from Android.",
      };
    }

    if (data.ok !== false) {
      this.cache.set(pending.key, data);
    }
    pending.callback(data);
  }

  clearCache() {
    this.cache.clear();
  }

  widthRatio(options) {
    const match = String(options || "").match(
      /(?:^|,)\s*width\s*=\s*([0-9]*\.?[0-9]+)\s*\\(?:textwidth|linewidth|columnwidth)\s*(?:,|$)/i,
    );
    if (!match) return 0.90;

    const ratio = Number.parseFloat(match[1]);
    if (!Number.isFinite(ratio)) return 0.90;
    return Math.max(0.05, Math.min(ratio, 4.0));
  }
}
