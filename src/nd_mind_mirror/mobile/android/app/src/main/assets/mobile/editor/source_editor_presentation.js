"use strict";

/**
 * Keeps the editable textarea, syntax mirror, and Ubuntu-style soft-wrap gutter aligned.
 */
class SourceEditorPresentation {
  constructor(textarea, highlightLayer, markerContent, shell) {
    this.textarea = textarea;
    this.highlightLayer = highlightLayer;
    this.markerContent = markerContent;
    this.shell = shell;
    this.highlighter = new AndroidSyntaxHighlighter();
    this.renderTimer = null;
    this.resizeTimer = null;

    this.textarea.addEventListener("scroll", () => this.syncScroll());
    window.addEventListener("resize", () => this.scheduleLayoutRefresh());
    this.shell.classList.add("highlight-enabled");
  }

  setSource(path, source) {
    this.highlighter.setPath(path);
    this.textarea.value = String(source ?? "");
    this.renderNow();
  }

  clear() {
    this.highlighter.setPath("");
    this.textarea.value = "";
    this.renderNow();
  }

  sourceChanged() {
    window.clearTimeout(this.renderTimer);
    this.renderTimer = window.setTimeout(() => this.renderNow(), 35);
  }

  refreshLayout() {
    this.syncScroll();
    this.renderWrapMarkers();
  }

  renderNow() {
    this.highlightLayer.innerHTML = this.highlighter.render(this.textarea.value);
    this.syncScroll();
    window.requestAnimationFrame(() => this.renderWrapMarkers());
  }

  scheduleLayoutRefresh() {
    window.clearTimeout(this.resizeTimer);
    this.resizeTimer = window.setTimeout(() => this.refreshLayout(), 80);
  }

  syncScroll() {
    this.highlightLayer.scrollTop = this.textarea.scrollTop;
    this.highlightLayer.scrollLeft = this.textarea.scrollLeft;
    this.markerContent.style.transform = `translateY(-${this.textarea.scrollTop}px)`;
  }

  renderWrapMarkers() {
    const style = window.getComputedStyle(this.textarea);
    const lineHeight = Number.parseFloat(style.lineHeight);
    if (!Number.isFinite(lineHeight) || lineHeight <= 0) return;

    const fragment = document.createDocumentFragment();
    this.highlightLayer.querySelectorAll(".source-line").forEach((line) => {
      const rowCount = Math.max(
        1,
        Math.round(line.getBoundingClientRect().height / lineHeight),
      );
      for (let row = 1; row < rowCount; row += 1) {
        const marker = document.createElement("span");
        marker.className = "source-wrap-marker";
        marker.textContent = "↳";
        marker.style.top = `${line.offsetTop + (row * lineHeight)}px`;
        fragment.appendChild(marker);
      }
    });

    this.markerContent.replaceChildren(fragment);
    this.markerContent.style.height = `${this.highlightLayer.scrollHeight}px`;
    this.syncScroll();
  }
}
