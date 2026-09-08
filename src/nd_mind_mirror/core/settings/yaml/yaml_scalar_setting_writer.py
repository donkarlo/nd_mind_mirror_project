from pathlib import Path
import re


class YamlScalarSettingWriter:
    """Update one simple nested YAML scalar without reformatting the file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()

    def set_section_value(
        self,
        section: str,
        key: str,
        value: str,
    ) -> None:
        text = self._path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        section_pattern = re.compile(
            rf"^(?P<indent>[ ]*){re.escape(section)}\s*:\s*(?:#.*)?$"
        )

        section_index = None
        section_indent = 0
        for index, raw_line in enumerate(lines):
            line = raw_line.rstrip("\r\n")
            match = section_pattern.match(line)
            if match is not None:
                section_index = index
                section_indent = len(match.group("indent"))
                break

        if section_index is None:
            suffix = "" if text.endswith("\n") or not text else "\n"
            addition = f"{suffix}{section}:\n  {key}: {value}\n"
            self._path.write_text(text + addition, encoding="utf-8")
            return

        child_indent = section_indent + 2
        key_pattern = re.compile(
            rf"^[ ]{{{child_indent}}}{re.escape(key)}\s*:"
        )
        insert_index = len(lines)
        for index in range(section_index + 1, len(lines)):
            line = lines[index].rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= section_indent:
                insert_index = index
                break
            if key_pattern.match(line):
                newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
                lines[index] = " " * child_indent + f"{key}: {value}" + newline
                self._path.write_text("".join(lines), encoding="utf-8")
                return

        lines.insert(
            insert_index,
            " " * child_indent + f"{key}: {value}\n",
        )
        self._path.write_text("".join(lines), encoding="utf-8")
