"use strict";

/**
 * Offline LaTeX math renderer backed by the KaTeX assets bundled in the APK.
 */
class LatexMathRenderer {
  create(raw, display = false) {
    const container = document.createElement(display ? "div" : "span");
    container.className = display ? "latex-math-display" : "latex-math-inline";

    const expression = this.expression(raw);
    try {
      window.katex.render(expression, container, {
        displayMode: Boolean(display),
        throwOnError: false,
        strict: "ignore",
        trust: false,
        output: "htmlAndMathml",
      });
    } catch (_error) {
      container.classList.add("latex-render-fallback");
      container.textContent = String(raw || "");
    }
    return container;
  }

  expression(raw) {
    let value = String(raw || "").trim();

    if (value.startsWith("$$") && value.endsWith("$$")) {
      return value.slice(2, -2).trim();
    }
    if (value.startsWith("\\[") && value.endsWith("\\]")) {
      return value.slice(2, -2).trim();
    }
    if (value.startsWith("\\(") && value.endsWith("\\)")) {
      return value.slice(2, -2).trim();
    }
    if (value.startsWith("$") && value.endsWith("$") && value.length >= 2) {
      return value.slice(1, -1).trim();
    }

    const environment = value.match(
      /^\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}([\s\S]*)\\end\{\1\}$/,
    );
    if (!environment) return value;

    const name = environment[1].replace("*", "");
    const body = environment[2].trim();
    if (name === "align") return `\\begin{aligned}${body}\\end{aligned}`;
    if (name === "gather") return `\\begin{gathered}${body}\\end{gathered}`;
    if (name === "multline") return `\\begin{aligned}${body}\\end{aligned}`;
    return body;
  }
}
