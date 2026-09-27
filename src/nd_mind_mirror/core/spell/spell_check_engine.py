"""Cached multilingual spell checking using local Hunspell dictionaries."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from nd_mind_mirror.core.spell.hunspell_dictionary import HunspellDictionary
from nd_mind_mirror.core.spell.spell_check_user_dictionary import (
    SpellCheckUserDictionary,
)


class SpellCheckEngine:
    """Check words against one explicitly selected document language."""

    _DICTIONARY_NAMES = {
        "en": ("en_US", "en_GB"),
        "de": ("de_AT_frami", "de_DE_frami", "de_DE"),
        "fa": ("fa_IR",),
    }
    _CACHE_LIMIT = 20000
    _SHARED_DICTIONARIES: dict[
        tuple[str, str],
        HunspellDictionary | None,
    ] = {}
    _SHARED_USER_DICTIONARIES: dict[str, SpellCheckUserDictionary] = {}

    def __init__(
        self,
        user_dictionary_root: str | Path,
        hunspell_root: str | Path = "/usr/share/hunspell",
    ) -> None:
        self._hunspell_root = Path(hunspell_root)
        user_root = Path(user_dictionary_root).expanduser().resolve()
        user_key = str(user_root)
        if user_key not in self._SHARED_USER_DICTIONARIES:
            self._SHARED_USER_DICTIONARIES[user_key] = SpellCheckUserDictionary(
                user_root
            )
        self._user_dictionary = self._SHARED_USER_DICTIONARIES[user_key]
        self._dictionaries: dict[str, HunspellDictionary | None] = {}
        self._correct_cache: dict[str, bool] = {}

    def is_correct(self, word: str, language: str) -> bool:
        value = str(word).strip()
        lang = str(language).strip().casefold()
        if not value:
            return True
        cache_key = f"{lang}:{value.casefold()}"
        if self._user_dictionary.contains(lang, value):
            self._remember(cache_key, True)
            return True
        cached = self._correct_cache.get(cache_key)
        if cached is not None:
            return cached

        dictionary = self._dictionary_for(lang)
        result = True if dictionary is None else dictionary.spell(value)
        self._remember(cache_key, result)
        return result

    def suggestions(
        self,
        word: str,
        language: str,
        limit: int = 5,
    ) -> list[str]:
        value = str(word).strip()
        lang = str(language).strip().casefold()
        if not value:
            return []
        dictionary = self._dictionary_for(lang)
        if dictionary is None:
            return []
        candidates = dictionary.suggest(
            value,
            limit=max(limit * 2, 8),
        )

        source = value.casefold()
        candidates.sort(
            key=lambda candidate: (
                -SequenceMatcher(None, source, candidate.casefold()).ratio(),
                abs(len(candidate) - len(value)),
                candidate.casefold(),
            )
        )
        return candidates[: max(int(limit), 1)]

    def add_to_dictionary(self, language: str, word: str) -> bool:
        changed = self._user_dictionary.add(language, word)
        if not changed:
            return False
        dictionary = self._dictionaries.get(language)
        if dictionary is not None:
            dictionary.add(word)
        prefix = f"{str(language).strip().casefold()}:"
        self._correct_cache.pop(
            prefix + str(word).casefold(),
            None,
        )
        return True

    def _dictionary_for(self, language: str) -> HunspellDictionary | None:
        if language in self._dictionaries:
            return self._dictionaries[language]
        shared_key = (str(self._hunspell_root.resolve()), str(language))
        if shared_key in self._SHARED_DICTIONARIES:
            dictionary = self._SHARED_DICTIONARIES[shared_key]
            self._dictionaries[language] = dictionary
            return dictionary

        dictionary: HunspellDictionary | None = None
        for stem in self._DICTIONARY_NAMES.get(language, ()):
            aff_path = self._hunspell_root / f"{stem}.aff"
            dic_path = self._hunspell_root / f"{stem}.dic"
            if not aff_path.exists() or not dic_path.exists():
                continue
            try:
                dictionary = HunspellDictionary(aff_path, dic_path)
            except (OSError, RuntimeError):
                dictionary = None
            if dictionary is not None:
                break
        self._SHARED_DICTIONARIES[shared_key] = dictionary
        self._dictionaries[language] = dictionary
        return dictionary

    def _remember(self, key: str, value: bool) -> None:
        if len(self._correct_cache) >= self._CACHE_LIMIT:
            self._correct_cache.clear()
        self._correct_cache[key] = bool(value)
