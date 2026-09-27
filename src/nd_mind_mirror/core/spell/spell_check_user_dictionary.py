"""Persistent user-added spell-check words."""

from __future__ import annotations

from pathlib import Path
import unicodedata


class SpellCheckUserDictionary:
    """Store custom accepted words in one UTF-8 text file per language."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser()
        self._words: dict[str, set[str]] = {}

    @staticmethod
    def _normalized(word: str) -> str:
        return unicodedata.normalize("NFC", str(word).strip()).casefold()

    def _path(self, language: str) -> Path:
        return self._root / f"{language}.txt"

    def _load(self, language: str) -> set[str]:
        key = str(language)
        cached = self._words.get(key)
        if cached is not None:
            return cached
        path = self._path(key)
        words: set[str] = set()
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    value = self._normalized(line)
                    if value:
                        words.add(value)
            except OSError:
                pass
        self._words[key] = words
        return words

    def contains(self, language: str, word: str) -> bool:
        value = self._normalized(word)
        return bool(value) and value in self._load(language)

    def add(self, language: str, word: str) -> bool:
        key = str(language)
        value = self._normalized(word)
        if not value:
            return False
        words = self._load(key)
        if value in words:
            return False
        words.add(value)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(sorted(words, key=str.casefold)) + "\n",
            encoding="utf-8",
        )
        return True
