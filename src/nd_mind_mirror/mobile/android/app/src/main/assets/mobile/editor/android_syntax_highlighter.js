"use strict";

/**
 * Filename-aware browser syntax highlighter for the standalone Android editor.
 * Unknown formats intentionally remain plain text.
 */
class AndroidSyntaxHighlighter {
  constructor() {
    this.language = "plain";
  }

  setPath(path) {
    this.language = this.languageForPath(path);
  }

  render(source) {
    const lines = String(source ?? "").split("\n");
    return lines.map((line, index) => {
      const highlighted = this.highlightLine(line);
      return `<span class="source-line" data-source-line="${index + 1}">${highlighted || "&#8203;"}</span>`;
    }).join("");
  }

  languageForPath(path) {
    const name = String(path || "").split("/").pop().toLowerCase();
    const suffix = name.includes(".") ? name.split(".").pop() : "";

    if (["tex", "ltx", "tikz", "sty", "cls"].includes(suffix)) return "latex";
    if (suffix === "bib") return "bibtex";
    if (["py", "pyw", "pyi"].includes(suffix)) return "python";
    if (["yaml", "yml"].includes(suffix)) return "yaml";
    if (["json", "jsonc"].includes(suffix)) return "json";
    if (["js", "jsx", "mjs", "cjs", "ts", "tsx"].includes(suffix)) return "javascript";
    if (["java", "kt", "kts", "c", "h", "cc", "cpp", "cxx", "hpp", "cs", "go", "rs", "swift", "dart", "scala"].includes(suffix)) return "c-like";
    if (["sh", "bash", "zsh", "fish"].includes(suffix) || name === ".bashrc" || name === ".zshrc") return "shell";
    if (["html", "htm", "xhtml", "xml", "svg"].includes(suffix)) return "markup";
    if (["css", "scss", "sass", "less"].includes(suffix)) return "css";
    if (["md", "markdown", "rst"].includes(suffix)) return "markdown";
    if (["toml", "ini", "cfg", "conf", "properties", "env"].includes(suffix) || name.startsWith(".env")) return "config";
    if (suffix === "sql") return "sql";
    if (["lua", "r", "m"].includes(suffix)) return "script";
    if (name === "dockerfile" || name.startsWith("dockerfile.")) return "shell";
    if (name === "makefile" || name.endsWith(".mk")) return "make";
    return "plain";
  }

  highlightLine(line) {
    const rules = this.rulesForLanguage(this.language);
    if (!rules.length) return this.escape(line);
    return this.tokenize(line, rules);
  }

  rulesForLanguage(language) {
    const stringRules = [
      { type: "string", regex: /"(?:\\.|[^"\\])*"/g },
      { type: "string", regex: /'(?:\\.|[^'\\])*'/g },
    ];
    const number = { type: "number", regex: /\b(?:0x[\da-fA-F]+|\d+(?:\.\d+)?)\b/g };

    if (language === "latex") {
      return [
        { type: "comment", regex: /(^|[^\\])%.*/g },
        { type: "keyword", regex: /\\[A-Za-z@]+\*?/g },
        { type: "string", regex: /\$[^$]*\$/g },
        number,
        { type: "punctuation", regex: /[{}\[\]&]/g },
      ];
    }

    if (language === "bibtex") {
      return [
        { type: "comment", regex: /(^|\s)%.*$/g },
        { type: "keyword", regex: /@[A-Za-z]+/g },
        { type: "attribute", regex: /\b[A-Za-z][\w-]*(?=\s*=)/g },
        ...stringRules,
        number,
        { type: "punctuation", regex: /[{}(),=]/g },
      ];
    }

    if (language === "python") {
      return [
        { type: "comment", regex: /#.*/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:and|as|assert|async|await|break|case|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|match|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b/g },
        { type: "builtin", regex: /\b(?:abs|all|any|bool|dict|enumerate|filter|float|int|len|list|map|max|min|open|print|range|set|str|sum|super|tuple|type|zip)\b/g },
        { type: "function", regex: /\b[A-Za-z_]\w*(?=\s*\()/g },
        number,
        { type: "operator", regex: /(?:==|!=|<=|>=|:=|\*\*|\/\/|[-+*/%=<>])/g },
      ];
    }

    if (language === "yaml") {
      return [
        { type: "comment", regex: /#.*/g },
        { type: "attribute", regex: /^\s*[-?]?\s*[A-Za-z0-9_.-]+(?=\s*:)/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:true|false|null|yes|no|on|off)\b/gi },
        number,
        { type: "punctuation", regex: /[:\[\]{},|>&*!-]/g },
      ];
    }

    if (language === "json") {
      return [
        { type: "comment", regex: /\/\/.*$/g },
        { type: "attribute", regex: /"(?:\\.|[^"\\])*"(?=\s*:)/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:true|false|null)\b/g },
        number,
        { type: "punctuation", regex: /[{}\[\],:]/g },
      ];
    }

    if (language === "javascript") {
      return [
        { type: "comment", regex: /\/\/.*$/g },
        { type: "comment", regex: /\/\*.*?\*\//g },
        { type: "string", regex: /\x60(?:\\.|[^\x60\\])*\x60/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|false|finally|for|from|function|get|if|import|in|instanceof|let|new|null|of|return|set|static|super|switch|this|throw|true|try|typeof|undefined|var|void|while|with|yield|interface|type|enum|implements|private|protected|public|readonly)\b/g },
        { type: "function", regex: /\b[A-Za-z_$][\w$]*(?=\s*\()/g },
        number,
        { type: "operator", regex: /(?:===|!==|=>|==|!=|<=|>=|&&|\|\||\?\?|\+\+|--|[-+*/%=<>!&|?:])/g },
      ];
    }

    if (language === "c-like") {
      return [
        { type: "comment", regex: /\/\/.*$/g },
        { type: "comment", regex: /\/\*.*?\*\//g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:abstract|as|async|await|auto|bool|break|byte|case|catch|char|class|companion|const|constexpr|continue|data|default|delete|do|double|else|enum|explicit|export|extends|extern|false|final|finally|float|for|fun|func|go|goto|if|implements|import|in|inline|int|interface|internal|is|let|long|match|mutable|namespace|new|null|nullptr|object|open|operator|override|package|private|protected|public|record|return|sealed|short|signed|sizeof|static|string|struct|super|switch|template|this|throw|throws|trait|true|try|type|typedef|typename|uint|union|unsigned|using|val|var|virtual|void|volatile|when|where|while)\b/g },
        { type: "function", regex: /\b[A-Za-z_]\w*(?=\s*\()/g },
        number,
        { type: "operator", regex: /(?:==|!=|<=|>=|&&|\|\||::|->|=>|\+\+|--|[-+*/%=<>!&|?:])/g },
        { type: "punctuation", regex: /[{}\[\]();,.]/g },
      ];
    }

    if (language === "shell" || language === "make") {
      return [
        { type: "comment", regex: /#.*/g },
        ...stringRules,
        { type: "variable", regex: /\$(?:\{[^}]+\}|[A-Za-z_][\w]*|\d+)/g },
        { type: "keyword", regex: /\b(?:case|do|done|elif|else|esac|fi|for|function|if|in|select|then|time|until|while|export|local|readonly|return|set|source)\b/g },
        { type: "builtin", regex: /\b(?:cd|echo|printf|read|test|pwd|command|exec|trap|unset|shift)\b/g },
        number,
        { type: "operator", regex: /(?:&&|\|\||>>|<<|[|&;<>])/g },
      ];
    }

    if (language === "markup") {
      return [
        { type: "comment", regex: /<!--.*?-->/g },
        { type: "tag", regex: /<\/?[A-Za-z][\w:.-]*/g },
        { type: "attribute", regex: /\b[A-Za-z_:][\w:.-]*(?=\s*=)/g },
        ...stringRules,
        { type: "punctuation", regex: /\/?\s*>/g },
      ];
    }

    if (language === "css") {
      return [
        { type: "comment", regex: /\/\*.*?\*\//g },
        ...stringRules,
        { type: "attribute", regex: /[-A-Za-z]+(?=\s*:)/g },
        { type: "keyword", regex: /(?:#[\da-fA-F]{3,8}\b|\b(?:none|auto|inherit|initial|unset|block|inline|flex|grid|absolute|relative|fixed|sticky)\b)/g },
        number,
        { type: "punctuation", regex: /[{}:;,()[\]]/g },
      ];
    }

    if (language === "markdown") {
      return [
        { type: "heading", regex: /^#{1,6}\s+.*$/g },
        { type: "string", regex: /\x60[^\x60]+\x60/g },
        { type: "strong", regex: /\*\*[^*]+\*\*/g },
        { type: "emphasis", regex: /\*[^*]+\*/g },
        { type: "tag", regex: /\[[^\]]+\]\([^)]+\)/g },
        { type: "punctuation", regex: /^\s*(?:[-*+] |\d+\. )/g },
      ];
    }

    if (language === "config") {
      return [
        { type: "comment", regex: /(?:#|;).*$/g },
        { type: "heading", regex: /^\s*\[[^\]]+\]/g },
        { type: "attribute", regex: /^\s*[A-Za-z0-9_.-]+(?=\s*=)/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:true|false|null|yes|no|on|off)\b/gi },
        number,
      ];
    }

    if (language === "sql") {
      return [
        { type: "comment", regex: /--.*$/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:ALTER|AND|AS|ASC|BEGIN|BETWEEN|BY|CASE|CREATE|DELETE|DESC|DISTINCT|DROP|ELSE|END|EXISTS|FROM|GROUP|HAVING|IN|INDEX|INNER|INSERT|INTO|IS|JOIN|LEFT|LIKE|LIMIT|NOT|NULL|ON|OR|ORDER|OUTER|PRIMARY|REFERENCES|RIGHT|SELECT|SET|TABLE|THEN|UNION|UNIQUE|UPDATE|VALUES|WHEN|WHERE)\b/gi },
        number,
        { type: "operator", regex: /(?:<>|!=|<=|>=|[-+*/%=<>])/g },
      ];
    }

    if (language === "script") {
      return [
        { type: "comment", regex: /(?:--|#|%).*$/g },
        ...stringRules,
        { type: "keyword", regex: /\b(?:break|do|else|elseif|end|false|for|function|if|in|local|nil|not|or|repeat|return|then|true|until|while|library|require)\b/g },
        { type: "function", regex: /\b[A-Za-z_]\w*(?=\s*\()/g },
        number,
      ];
    }

    return [];
  }

  tokenize(line, rules) {
    let cursor = 0;
    let output = "";

    while (cursor < line.length) {
      let chosen = null;
      let chosenMatch = null;

      rules.forEach((rule, priority) => {
        rule.regex.lastIndex = cursor;
        const match = rule.regex.exec(line);
        if (!match) return;

        if (
          chosenMatch === null ||
          match.index < chosenMatch.index ||
          (match.index === chosenMatch.index && priority < chosen.priority)
        ) {
          chosen = { ...rule, priority };
          chosenMatch = match;
        }
      });

      if (!chosen || !chosenMatch) {
        output += this.escape(line.slice(cursor));
        break;
      }

      if (chosenMatch.index > cursor) {
        output += this.escape(line.slice(cursor, chosenMatch.index));
      }

      const value = chosenMatch[0];
      if (!value) {
        output += this.escape(line[cursor]);
        cursor += 1;
        continue;
      }

      output += `<span class="tok-${chosen.type}">${this.escape(value)}</span>`;
      cursor = chosenMatch.index + value.length;
    }

    return output;
  }

  escape(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }
}
