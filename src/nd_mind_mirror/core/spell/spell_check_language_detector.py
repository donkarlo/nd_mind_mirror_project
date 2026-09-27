"""Document-level language detection for spell checking."""

from __future__ import annotations

from collections.abc import Iterable


class SpellCheckLanguageDetector:
    """Choose one spell-check language for an entire document."""

    _PERSIAN_MIN_RATIO = 0.20
    _MAX_SAMPLE_WORDS = 320
    _MIN_SCORE_WORD_LENGTH = 3

    def detect(
        self,
        words: Iterable[str],
        engine,
    ) -> str:
        sample = self._sample(words)
        if not sample:
            return "en"

        persian_count = sum(
            1
            for word in sample
            if self._is_persian(word)
        )
        if persian_count and (
            persian_count / len(sample) >= self._PERSIAN_MIN_RATIO
            or persian_count >= 8
        ):
            return "fa"
        latin_words = [
            word
            for word in sample
            if not self._is_persian(word)
            and len(word) >= self._MIN_SCORE_WORD_LENGTH
        ]
        if not latin_words:
            return "en"

        english = self._score(latin_words, engine, "en")
        german = self._score(latin_words, engine, "de")
        return "de" if german > english else "en"

    def _sample(self, words: Iterable[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw_word in words:
            word = str(raw_word).strip()
            key = word.casefold()
            if not word or key in seen:
                continue
            seen.add(key)
            result.append(word)
            if len(result) >= self._MAX_SAMPLE_WORDS:
                break
        return result

    @staticmethod
    def _score(words: list[str], engine, language: str) -> int:
        return sum(
            1
            for word in words
            if engine.is_correct(word, language)
        )

    @staticmethod
    def _is_persian(word: str) -> bool:
        return any("\u0600" <= char <= "\u06ff" for char in str(word))
