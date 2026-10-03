"use strict";

/**
 * Renders the inline LaTeX constructs that the Ubuntu Visual projection treats
 * as visible text while preserving unsupported commands as readable raw tokens.
 */
class LatexInlineRenderer {
  constructor(mathRenderer) {
    this.mathRenderer = mathRenderer;
  }

  create(text) {
    const fragment = document.createDocumentFragment();
    this.append(fragment, String(text || ""));
    return fragment;
  }

  append(parent, text) {
    let index = 0;
    let plainStart = 0;

    const flushPlain = (end) => {
      if (end <= plainStart) return;
      parent.appendChild(document.createTextNode(this.decodePlain(text.slice(plainStart, end))));
    };

    while (index < text.length) {
      if (text.startsWith("\\(", index) && !this.escaped(text, index)) {
        const end = this.findToken(text, "\\)", index + 2);
        if (end >= 0) {
          flushPlain(index);
          parent.appendChild(this.mathRenderer.create(text.slice(index, end + 2), false));
          index = end + 2;
          plainStart = index;
          continue;
        }
      }

      if (text[index] === "$" && !this.escaped(text, index) && text[index + 1] !== "$") {
        const end = this.findInlineDollarEnd(text, index + 1);
        if (end >= 0) {
          flushPlain(index);
          parent.appendChild(this.mathRenderer.create(text.slice(index, end + 1), false));
          index = end + 1;
          plainStart = index;
          continue;
        }
      }

      if (text[index] === "\\") {
        const commandMatch = text.slice(index).match(/^\\([A-Za-z@]+\*?|.)/);
        if (commandMatch) {
          const command = commandMatch[1];
          const commandEnd = index + commandMatch[0].length;

          if (command === "\\") {
            flushPlain(index);
            parent.appendChild(document.createElement("br"));
            index = commandEnd;
            plainStart = index;
            continue;
          }

          if (["%", "_", "&", "#", "{", "}", "$"].includes(command)) {
            flushPlain(index);
            parent.appendChild(document.createTextNode(command));
            index = commandEnd;
            plainStart = index;
            continue;
          }

          const handled = this.appendCommand(parent, text, index, command, commandEnd);
          if (handled !== null) {
            flushPlain(index);
            index = handled;
            plainStart = index;
            continue;
          }
        }
      }

      index += 1;
    }

    flushPlain(text.length);
  }

  appendCommand(parent, text, start, command, commandEnd) {
    const normalized = command.replace("*", "");
    const formatting = {
      textbf: "strong",
      emph: "em",
      textit: "em",
      texttt: "code",
      underline: "u",
    };

    if (formatting[normalized]) {
      const group = this.groupAt(text, commandEnd);
      if (!group) return null;
      const element = document.createElement(formatting[normalized]);
      this.append(element, group.value);
      parent.appendChild(element);
      return group.end;
    }

    if (normalized === "href") {
      const first = this.groupAt(text, commandEnd);
      if (!first) return null;
      const second = this.groupAt(text, first.end);
      if (!second) return null;
      const link = document.createElement("span");
      link.className = "latex-link";
      link.title = first.value;
      this.append(link, second.value);
      parent.appendChild(link);
      return second.end;
    }

    if (normalized === "url") {
      const group = this.groupAt(text, commandEnd);
      if (!group) return null;
      const link = document.createElement("span");
      link.className = "latex-link";
      link.textContent = group.value;
      parent.appendChild(link);
      return group.end;
    }

    if (normalized === "label") {
      const group = this.groupAt(text, commandEnd);
      return group ? group.end : null;
    }

    if (["cite", "citep", "citet", "ref", "eqref", "pageref"].includes(normalized)) {
      const group = this.groupAt(text, commandEnd);
      if (!group) return null;
      const reference = document.createElement("span");
      reference.className = "latex-reference";
      reference.textContent =
        normalized.startsWith("cite") ? `[${group.value}]` : `[${group.value}]`;
      parent.appendChild(reference);
      return group.end;
    }

    if (["seeherefooter", "seehere"].includes(normalized)) {
      const group = this.groupAt(text, commandEnd);
      if (!group) return null;
      const reference = document.createElement("span");
      reference.className = "latex-source-reference";
      reference.textContent = group.value;
      parent.appendChild(reference);
      return group.end;
    }

    return null;
  }

  groupAt(text, start) {
    let cursor = start;
    while (cursor < text.length && /\s/.test(text[cursor])) cursor += 1;
    if (text[cursor] !== "{") return null;

    let depth = 0;
    for (let index = cursor; index < text.length; index += 1) {
      if (text[index] === "{" && !this.escaped(text, index)) depth += 1;
      if (text[index] === "}" && !this.escaped(text, index)) {
        depth -= 1;
        if (depth === 0) {
          return {
            value: text.slice(cursor + 1, index),
            end: index + 1,
          };
        }
      }
    }
    return null;
  }

  findInlineDollarEnd(text, start) {
    for (let index = start; index < text.length; index += 1) {
      if (text[index] === "\n") return -1;
      if (text[index] === "$" && !this.escaped(text, index) && text[index + 1] !== "$") {
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

  decodePlain(value) {
    return String(value)
      .replaceAll("~", "\u00a0")
      .replace(/\\([%_&#{}$])/g, "$1");
  }
}
