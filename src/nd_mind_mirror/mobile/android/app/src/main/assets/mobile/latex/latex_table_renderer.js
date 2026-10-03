"use strict";

/**
 * Safe rectangular tabular parser/renderer modeled after the Ubuntu
 * LatexTableParser. Complex multicolumn/multirow tables remain readable raw
 * LaTeX instead of being guessed incorrectly.
 */
class LatexTableRenderer {
  constructor(inlineRenderer) {
    this.inlineRenderer = inlineRenderer;
  }

  create(raw) {
    const model = this.parse(raw);
    if (!model) {
      const fallback = document.createElement("pre");
      fallback.className = "latex-raw latex-table-fallback";
      fallback.textContent = String(raw || "");
      return fallback;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "latex-table-wrapper";

    const table = document.createElement("table");
    table.className = "latex-table";
    const body = document.createElement("tbody");

    model.rows.forEach((row, rowIndex) => {
      const tr = document.createElement("tr");
      if (model.rowPrefixes[rowIndex]) {
        tr.classList.add("latex-table-rule-before");
      }

      row.forEach((cell, columnIndex) => {
        const td = document.createElement("td");
        td.className = `latex-table-align-${model.alignments[columnIndex] || "left"}`;
        td.appendChild(this.inlineRenderer.create(cell));
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });

    table.appendChild(body);
    wrapper.appendChild(table);
    return wrapper;
  }

  parse(raw) {
    const source = String(raw || "");
    const beginToken = "\\begin{tabular}";
    const begin = source.indexOf(beginToken);
    if (begin < 0) return null;
    if (source.indexOf(beginToken, begin + beginToken.length) >= 0) return null;
    if (source.includes("\\multicolumn") || source.includes("\\multirow")) return null;

    let cursor = begin + beginToken.length;
    cursor = this.skipWhitespace(source, cursor);

    if (source[cursor] === "[") {
      const optionalEnd = this.balancedEnd(source, cursor, "[", "]");
      if (optionalEnd === null) return null;
      cursor = this.skipWhitespace(source, optionalEnd);
    }

    if (source[cursor] !== "{") return null;
    const specEnd = this.balancedEnd(source, cursor, "{", "}");
    if (specEnd === null) return null;

    const columnSpec = source.slice(cursor + 1, specEnd - 1);
    if (columnSpec.includes("*{")) return null;

    const endToken = "\\end{tabular}";
    const endStart = source.indexOf(endToken, specEnd);
    if (endStart < 0) return null;

    const body = source.slice(specEnd, endStart);
    const chunks = this.splitRows(body);
    const rows = [];
    const rowPrefixes = [];
    let pendingRules = [];

    chunks.forEach((rawChunk) => {
      let chunk = rawChunk.trim();
      if (!chunk) return;

      const rules = [];
      while (true) {
        const match = chunk.match(
          /^\s*(\\(?:hline|toprule|midrule|bottomrule|cline\{[^}]+\}))\s*/,
        );
        if (!match) break;
        rules.push(match[1]);
        chunk = chunk.slice(match[0].length);
      }

      if (!chunk.trim()) {
        pendingRules.push(...rules);
        return;
      }

      rowPrefixes.push([...pendingRules, ...rules].join("\n"));
      pendingRules = [];
      rows.push(this.splitCells(chunk).map((cell) => cell.trim()));
    });

    if (!rows.length) return null;
    const width = Math.max(...rows.map((row) => row.length));
    if (!rows.every((row) => row.length === width)) return null;

    return {
      columnSpec,
      alignments: this.alignments(columnSpec, width),
      rows,
      rowPrefixes,
    };
  }

  alignments(spec, width) {
    const result = [];
    for (const char of String(spec || "")) {
      if (char === "l") result.push("left");
      if (char === "c") result.push("center");
      if (char === "r") result.push("right");
    }
    while (result.length < width) result.push("left");
    return result.slice(0, width);
  }

  splitRows(body) {
    const chunks = [];
    let start = 0;
    let depth = 0;
    let index = 0;

    while (index < body.length) {
      const char = body[index];
      if (char === "{" && !this.escaped(body, index)) depth += 1;
      if (char === "}" && !this.escaped(body, index)) depth = Math.max(depth - 1, 0);

      if (depth === 0 && body.startsWith("\\\\", index)) {
        chunks.push(body.slice(start, index));
        index += 2;
        if (body[index] === "*") index += 1;
        if (body[index] === "[") {
          const optionalEnd = this.balancedEnd(body, index, "[", "]");
          if (optionalEnd !== null) index = optionalEnd;
        }
        start = index;
        continue;
      }
      index += 1;
    }

    chunks.push(body.slice(start));
    return chunks;
  }

  splitCells(row) {
    const cells = [];
    let start = 0;
    let depth = 0;

    for (let index = 0; index < row.length; index += 1) {
      const char = row[index];
      if (char === "{" && !this.escaped(row, index)) depth += 1;
      if (char === "}" && !this.escaped(row, index)) depth = Math.max(depth - 1, 0);
      if (char === "&" && depth === 0 && !this.escaped(row, index)) {
        cells.push(row.slice(start, index));
        start = index + 1;
      }
    }

    cells.push(row.slice(start));
    return cells;
  }

  balancedEnd(text, start, opening, closing) {
    if (text[start] !== opening) return null;
    let depth = 0;

    for (let index = start; index < text.length; index += 1) {
      if (text[index] === opening && !this.escaped(text, index)) depth += 1;
      if (text[index] === closing && !this.escaped(text, index)) {
        depth -= 1;
        if (depth === 0) return index + 1;
      }
    }
    return null;
  }

  skipWhitespace(text, start) {
    let cursor = start;
    while (cursor < text.length && /\s/.test(text[cursor])) cursor += 1;
    return cursor;
  }

  escaped(text, index) {
    let count = 0;
    for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
      count += 1;
    }
    return count % 2 === 1;
  }
}
