"use strict";

/**
 * Extracts Source-mode image, math and table previews without changing the
 * canonical LaTeX source. The supported spans mirror the Ubuntu extractor.
 */
class SourceLatexPreviewExtractor {
  extract(source) {
    const original = String(source || "");
    const masked = this.maskComments(original);
    const previews = [];
    const occupied = [];

    this.collectFigures(masked, original, previews, occupied);
    this.collectTables(masked, original, previews, occupied);
    this.collectDisplayMath(masked, original, previews, occupied);
    this.collectStandaloneGraphics(masked, original, previews, occupied);
    this.collectInlineMath(masked, original, previews, occupied);

    return previews.sort((first, second) => {
      if (first.anchorLine !== second.anchorLine) {
        return first.anchorLine - second.anchorLine;
      }
      return first.start - second.start;
    });
  }

  collectFigures(masked, original, previews, occupied) {
    const pattern =
      /\\begin\s*\{figure\}(?:\s*\[[^\]]*\])?[\s\S]*?\\end\s*\{figure\}/gi;
    let match;

    while ((match = pattern.exec(masked)) !== null) {
      const raw = original.slice(match.index, match.index + match[0].length);
      const graphics = this.graphicsInside(raw);
      if (!graphics.length) continue;

      const captionMatch = raw.match(/\\caption(?:\s*\[[^\]]*\])?\s*\{([^{}]*)\}/i);
      const endOffset = match.index + match[0].lastIndexOf("\\end");
      previews.push({
        kind: "graphic",
        start: match.index,
        end: match.index + match[0].length,
        anchorLine: this.lineOf(original, endOffset),
        graphics,
        caption: captionMatch ? captionMatch[1].trim() : "",
        raw,
      });
      occupied.push([match.index, match.index + match[0].length]);
    }
  }

  collectTables(masked, original, previews, occupied) {
    const pattern =
      /\\begin\{tabular\}(?:\[[^\]]*\])?\s*\{.*?\}[\s\S]*?\\end\{tabular\}/g;
    let match;

    while ((match = pattern.exec(masked)) !== null) {
      const start = match.index;
      const end = match.index + match[0].length;
      if (this.overlaps(start, end, occupied)) continue;

      previews.push({
        kind: "table",
        start,
        end,
        anchorLine: this.lineOf(original, end - 1),
        raw: original.slice(start, end),
      });
      occupied.push([start, end]);
    }
  }

  collectDisplayMath(masked, original, previews, occupied) {
    const patterns = [
      /\\\[[\s\S]*?\\\]/g,
      /\$\$[\s\S]*?\$\$/g,
      /\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}[\s\S]*?\\end\{\1\}/g,
    ];

    patterns.forEach((pattern) => {
      let match;
      while ((match = pattern.exec(masked)) !== null) {
        const start = match.index;
        const end = match.index + match[0].length;
        if (this.overlaps(start, end, occupied)) continue;

        previews.push({
          kind: "math",
          display: true,
          start,
          end,
          anchorLine: this.lineOf(original, end - 1),
          raw: original.slice(start, end),
        });
        occupied.push([start, end]);
      }
    });
  }

  collectStandaloneGraphics(masked, original, previews, occupied) {
    const pattern =
      /\\includegraphics\s*(?:\[(?<options>[^\]]*)\]\s*)?\{(?<path>[^{}]+)\}/gi;
    let match;

    while ((match = pattern.exec(masked)) !== null) {
      const start = match.index;
      const end = match.index + match[0].length;
      if (this.overlaps(start, end, occupied)) continue;

      previews.push({
        kind: "graphic",
        start,
        end,
        anchorLine: this.lineOf(original, end - 1),
        graphics: [{
          path: match.groups?.path?.trim() || "",
          options: match.groups?.options || "",
        }],
        caption: "",
        raw: original.slice(start, end),
      });
      occupied.push([start, end]);
    }
  }

  collectInlineMath(masked, original, previews, occupied) {
    const lines = masked.split("\n");
    let absoluteStart = 0;

    lines.forEach((line, lineIndex) => {
      const formulas = [];
      let index = 0;

      while (index < line.length) {
        const absolute = absoluteStart + index;
        if (this.inside(absolute, occupied)) {
          index += 1;
          continue;
        }

        if (line.startsWith("\\(", index) && !this.escaped(line, index)) {
          const close = this.findToken(line, "\\)", index + 2);
          if (close >= 0) {
            const end = close + 2;
            formulas.push(original.slice(absoluteStart + index, absoluteStart + end));
            index = end;
            continue;
          }
        }

        if (
          line[index] === "$" &&
          line[index + 1] !== "$" &&
          !this.escaped(line, index)
        ) {
          const close = this.inlineDollarEnd(line, index + 1);
          if (close >= 0) {
            formulas.push(
              original.slice(absoluteStart + index, absoluteStart + close + 1),
            );
            index = close + 1;
            continue;
          }
        }

        index += 1;
      }

      if (formulas.length) {
        previews.push({
          kind: "inline-math",
          start: absoluteStart,
          end: absoluteStart + line.length,
          anchorLine: lineIndex,
          formulas,
        });
      }
      absoluteStart += line.length + 1;
    });
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

  lineOf(source, position) {
    let line = 0;
    const end = Math.max(0, Math.min(Number(position) || 0, source.length));
    for (let index = 0; index < end; index += 1) {
      if (source[index] === "\n") line += 1;
    }
    return line;
  }

  overlaps(start, end, ranges) {
    return ranges.some(([left, right]) => start < right && end > left);
  }

  inside(position, ranges) {
    return ranges.some(([left, right]) => left <= position && position < right);
  }

  inlineDollarEnd(text, start) {
    for (let index = start; index < text.length; index += 1) {
      if (
        text[index] === "$" &&
        text[index + 1] !== "$" &&
        !this.escaped(text, index)
      ) {
        return index;
      }
    }
    return -1;
  }

  findToken(text, token, start) {
    let index = text.indexOf(token, start);
    while (index >= 0) {
      if (!this.escaped(text, index)) return index;
      index = text.indexOf(token, index + token.length);
    }
    return -1;
  }

  escaped(text, index) {
    let count = 0;
    for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
      count += 1;
    }
    return count % 2 === 1;
  }

  maskComments(source) {
    const characters = [...source];
    let lineStart = 0;

    while (lineStart < source.length) {
      let lineEnd = source.indexOf("\n", lineStart);
      if (lineEnd < 0) lineEnd = source.length;

      for (let index = lineStart; index < lineEnd; index += 1) {
        if (source[index] === "%" && !this.escaped(source, index)) {
          for (let maskedIndex = index; maskedIndex < lineEnd; maskedIndex += 1) {
            characters[maskedIndex] = " ";
          }
          break;
        }
      }
      lineStart = lineEnd + 1;
    }

    return characters.join("");
  }
}
