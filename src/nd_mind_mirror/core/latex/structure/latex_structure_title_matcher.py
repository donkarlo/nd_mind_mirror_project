"""Typo-tolerant title matching for LaTeX and YAML Structure trees."""

from difflib import SequenceMatcher
import re
import unicodedata


class LatexStructureTitleMatcher:
    """Match title tokens without parsing or changing canonical documents."""

    _SEPARATORS = re.compile(r"[^\w]+", flags=re.UNICODE)

    @classmethod
    def normalize(cls, text: str) -> str:
        value = unicodedata.normalize("NFKC", str(text)).casefold()
        value = "".join(
            character for character in value
            if unicodedata.category(character) != "Mn"
        )
        value = value.replace("\u200c", " ").replace("_", " ")
        return " ".join(cls._SEPARATORS.sub(" ", value).split())

    @classmethod
    def matches(cls, title: str, query: str) -> bool:
        phrase = cls.normalize(query)
        if not phrase:
            return True
        normalized_title = cls.normalize(title)
        if phrase in normalized_title:
            return True

        words = normalized_title.split()
        terms = phrase.split()
        for term in terms:
            if term in normalized_title:
                continue
            # Three-letter terms need supporting words to avoid unrelated
            # one-word matches; longer terms tolerate small spelling errors.
            if len(term) < 3 or (len(term) == 3 and len(terms) == 1):
                return False
            threshold = 0.70 if len(term) <= 4 else 0.76 if len(term) < 7 else 0.73
            allowed_difference = max(1, len(term) // 3)
            if not any(
                abs(len(term) - len(word)) <= allowed_difference
                and SequenceMatcher(None, term, word).ratio() >= threshold
                for word in words
            ):
                return False
        return True
