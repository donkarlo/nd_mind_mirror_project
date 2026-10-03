"use strict";

/**
 * Canonical LaTeX-to-Visual block parser modeled after the Ubuntu Visual
 * editor: headings, lists, graphics, tables, display math, paragraphs and raw
 * blocks retain their source line anchors.
 */
class LatexDocumentParser {
  parse(source) {
    const extracted = this.documentBody(String(source || ""));
    const lines = extracted.body.split("\n");
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
      const rawLine = lines[index];
      const lineNumber = extracted.baseLine + index;
      const stripped = this.stripComment(rawLine).trim();

      if (!stripped) {
        index += 1;
        continue;
      }

      const heading = stripped.match(
        /^\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\s*\{([^{}]*)\}/,
      );
      if (heading) {
        blocks.push({
          kind: "heading",
          command: heading[1],
          text: heading[2],
          sourceLine: lineNumber,
        });
        index += 1;
        continue;
      }

      if (/^\\begin\{figure\}(?:\s*\[[^\]]*\])?/.test(stripped)) {
        const collected = this.collectEnvironment(lines, index, "figure");
        const graphics = this.graphicsInside(collected.raw);
        const caption = this.captionInside(collected.raw);
        blocks.push(
          graphics.length
            ? {
                kind: "graphic",
                graphics,
                caption,
                raw: collected.raw,
                sourceLine: lineNumber,
              }
            : { kind: "raw", raw: collected.raw, sourceLine: lineNumber },
        );
        index = collected.nextIndex;
        continue;
      }

      if (/^\\begin\{table\}(?:\s*\[[^\]]*\])?/.test(stripped)) {
        const collected = this.collectEnvironment(lines, index, "table");
        const tabular = this.firstEnvironment(collected.raw, "tabular");
        const caption = this.captionInside(collected.raw);
        blocks.push(
          tabular
            ? {
                kind: "table",
                raw: tabular,
                caption,
                sourceLine: lineNumber,
              }
            : { kind: "raw", raw: collected.raw, sourceLine: lineNumber },
        );
        index = collected.nextIndex;
        continue;
      }

      if (/^\\begin\{tabular\}/.test(stripped)) {
        const collected = this.collectEnvironment(lines, index, "tabular");
        blocks.push({
          kind: "table",
          raw: collected.raw,
          caption: "",
          sourceLine: lineNumber,
        });
        index = collected.nextIndex;
        continue;
      }

      const listMatch = stripped.match(/^\\begin\{(itemize|enumerate)\}/);
      if (listMatch) {
        const collected = this.collectEnvironment(lines, index, listMatch[1]);
        blocks.push({
          kind: "list",
          ordered: listMatch[1] === "enumerate",
          items: this.listItems(collected.raw, listMatch[1]),
          raw: collected.raw,
          sourceLine: lineNumber,
        });
        index = collected.nextIndex;
        continue;
      }

      const mathEnvironment = stripped.match(
        /^\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}/,
      );
      if (mathEnvironment) {
        const collected = this.collectEnvironment(lines, index, mathEnvironment[1]);
        blocks.push({
          kind: "math",
          raw: collected.raw,
          sourceLine: lineNumber,
        });
        index = collected.nextIndex;
        continue;
      }

      if (stripped.startsWith("\\[")) {
        const collected = this.collectDelimited(lines, index, "\\[", "\\]");
        blocks.push({
          kind: "math",
          raw: collected.raw,
          sourceLine: lineNumber,
        });
        index = collected.nextIndex;
        continue;
      }

      if (stripped.startsWith("$$")) {
        const collected = this.collectDelimited(lines, index, "$$", "$$");
        blocks.push({
          kind: "math",
          raw: collected.raw,
          sourceLine: lineNumber,
        });
        index = collected.nextIndex;
        continue;
      }

      const graphic = stripped.match(
        /^\\includegraphics\s*(?:\[(?<options>[^\]]*)\]\s*)?\{(?<path>[^{}]+)\}\s*$/,
      );
      if (graphic) {
        blocks.push({
          kind: "graphic",
          graphics: [{
            path: graphic.groups?.path?.trim() || "",
            options: graphic.groups?.options || "",
          }],
          caption: "",
          raw: rawLine,
          sourceLine: lineNumber,
        });
        index += 1;
        continue;
      }

      const input = stripped.match(/^\\(?:input|include)\s*\{([^{}]+)\}\s*$/);
      if (input) {
        blocks.push({
          kind: "input",
          path: input[1].trim(),
          raw: rawLine,
          sourceLine: lineNumber,
        });
        index += 1;
        continue;
      }

      if (/^\\(?:label|centering|maketitle|tightlist)\b/.test(stripped)) {
        index += 1;
        continue;
      }

      if (stripped.startsWith("%")) {
        index += 1;
        continue;
      }

      if (
        stripped.startsWith("\\begin{") ||
        stripped.startsWith("\\end{") ||
        (stripped.startsWith("\\") && !this.startsInlineConstruct(stripped))
      ) {
        blocks.push({ kind: "raw", raw: rawLine, sourceLine: lineNumber });
        index += 1;
        continue;
      }

      const paragraphLines = [];
      const startLine = lineNumber;
      while (index < lines.length) {
        const candidateRaw = lines[index];
        const candidate = this.stripComment(candidateRaw).trim();
        if (!candidate) break;
        if (paragraphLines.length && this.startsStructuralBlock(candidate)) break;
        paragraphLines.push(candidate);
        index += 1;
      }

      if (!paragraphLines.length) {
        paragraphLines.push(stripped);
        index += 1;
      }

      blocks.push({
        kind: "paragraph",
        text: paragraphLines.join(" "),
        sourceLine: startLine,
      });
    }

    return blocks;
  }

  documentBody(source) {
    const beginToken = "\\begin{document}";
    const endToken = "\\end{document}";
    const begin = source.indexOf(beginToken);
    const end = source.lastIndexOf(endToken);
    if (begin < 0 || end < 0 || end <= begin) {
      return { body: source, baseLine: 1 };
    }

    const bodyStart = begin + beginToken.length;
    const baseLine = 1 + (source.slice(0, bodyStart).match(/\n/g) || []).length;
    return {
      body: source.slice(bodyStart, end),
      baseLine,
    };
  }

  startsStructuralBlock(text) {
    return (
      /^\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\s*\{/.test(text) ||
      /^\\begin\{/.test(text) ||
      /^\\includegraphics\b/.test(text) ||
      /^\\(?:input|include)\b/.test(text) ||
      text.startsWith("\\[") ||
      text.startsWith("$$")
    );
  }

  startsInlineConstruct(text) {
    return /^\\(?:textbf|textit|emph|texttt|underline|href|url|cite|citep|citet|ref|eqref|pageref|seeherefooter|seehere)\b/.test(
      text,
    );
  }

  collectEnvironment(lines, startIndex, environment) {
    const rawLines = [];
    let depth = 0;
    let index = startIndex;
    const escapedEnvironment = this.escapeRegex(environment);

    while (index < lines.length) {
      const line = lines[index];
      const beginPattern = new RegExp("\\\\begin\\{" + escapedEnvironment + "\\}", "g");
      const endPattern = new RegExp("\\\\end\\{" + escapedEnvironment + "\\}", "g");
      depth += (line.match(beginPattern) || []).length;
      depth -= (line.match(endPattern) || []).length;
      rawLines.push(line);
      index += 1;
      if (depth <= 0) break;
    }

    return {
      raw: rawLines.join("\n"),
      nextIndex: index,
    };
  }

  collectDelimited(lines, startIndex, opening, closing) {
    const rawLines = [];
    let index = startIndex;
    let openingSeen = false;

    while (index < lines.length) {
      const line = lines[index];
      rawLines.push(line);

      const searchStart = openingSeen ? 0 : Math.max(line.indexOf(opening), 0) + opening.length;
      openingSeen = true;
      if (line.indexOf(closing, searchStart) >= 0) {
        index += 1;
        break;
      }
      index += 1;
    }

    return {
      raw: rawLines.join("\n"),
      nextIndex: index,
    };
  }

  graphicsInside(raw) {
    const graphics = [];
    const pattern =
      /\\includegraphics\s*(?:\[(?<options>[^\]]*)\]\s*)?\{(?<path>[^{}]+)\}/gi;
    let match;

    while ((match = pattern.exec(raw)) !== null) {
      graphics.push({
        path: match.groups?.path?.trim() || "",
        options: match.groups?.options || "",
      });
    }
    return graphics;
  }

  captionInside(raw) {
    const match = String(raw || "").match(
      /\\caption(?:\s*\[[^\]]*\])?\s*\{([^{}]*)\}/i,
    );
    return match ? match[1].trim() : "";
  }

  firstEnvironment(raw, environment) {
    const beginToken = "\\begin{" + environment + "}";
    const start = raw.indexOf(beginToken);
    if (start < 0) return null;

    const lines = raw.slice(start).split("\n");
    return this.collectEnvironment(lines, 0, environment).raw;
  }

  listItems(raw, environment) {
    const beginToken = "\\begin{" + environment + "}";
    const endToken = "\\end{" + environment + "}";
    let body = String(raw || "");
    const beginIndex = body.indexOf(beginToken);
    const endIndex = body.lastIndexOf(endToken);
    if (beginIndex >= 0 && endIndex > beginIndex) {
      body = body.slice(beginIndex + beginToken.length, endIndex);
    }

    const items = [];
    let current = "";
    let depth = 0;

    body.split("\n").forEach((line) => {
      const stripped = this.stripComment(line).trim();
      if (!stripped || stripped === "\\tightlist") return;

      if (/^\\begin\{(itemize|enumerate)\}/.test(stripped)) {
        depth += 1;
        current += (current ? " " : "") + stripped;
        return;
      }
      if (/^\\end\{(itemize|enumerate)\}/.test(stripped)) {
        depth = Math.max(depth - 1, 0);
        current += (current ? " " : "") + stripped;
        return;
      }

      const item = stripped.match(/^\\item(?:\s+|$)(.*)$/);
      if (item && depth === 0) {
        if (current) items.push(current.trim());
        current = item[1].trim();
      } else {
        current += (current ? " " : "") + stripped;
      }
    });

    if (current) items.push(current.trim());
    return items;
  }

  stripComment(line) {
    const value = String(line || "");
    for (let index = 0; index < value.length; index += 1) {
      if (value[index] === "%" && !this.escaped(value, index)) {
        return value.slice(0, index);
      }
    }
    return value;
  }

  escaped(text, index) {
    let count = 0;
    for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
      count += 1;
    }
    return count % 2 === 1;
  }

  escapeRegex(value) {
    return String(value).replace(/[.*+?^$(){}|[\]\\]/g, "\\$&");
  }
}
