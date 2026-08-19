from difflib import SequenceMatcher
from pathlib import Path
import re

from PySide6.QtCore import QThread, Signal


class FileSearchThread(QThread):
    results_ready = Signal(int, object, bool)

    def __init__(
        self,
        generation: int,
        entries: list[
            tuple[str, str, str, str, str, bool]
        ],
        query: str,
        max_results: int,
        fuzzy_threshold: float,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._generation = generation
        self._entries = entries
        self._query = self._normalize(query)
        self._tokens = [
            token
            for token in re.split(r"\s+", self._query)
            if token
        ]
        self._max_results = max(int(max_results), 1)
        self._fuzzy_threshold = max(
            0.75,
            min(float(fuzzy_threshold), 0.98),
        )
        self._strict_filename_query = (
            "." in self._query
        )

    def run(self) -> None:
        if not self._tokens:
            self.results_ready.emit(
                self._generation,
                [],
                False,
            )
            return

        scored_results: list[tuple[float, int, str]] = []

        for (
            path_text,
            name_text,
            stem_text,
            normalized_name,
            normalized_stem,
            is_directory,
        ) in self._entries:
            if self.isInterruptionRequested():
                return

            score = self._score_name(
                name_text=name_text,
                stem_text=stem_text,
                name=normalized_name,
                stem=normalized_stem,
            )
            if score is None:
                continue

            scored_results.append(
                (
                    score,
                    0 if is_directory else 1,
                    path_text,
                )
            )

        if self.isInterruptionRequested():
            return

        scored_results.sort(
            key=lambda item: (
                -item[0],
                item[1],
                len(Path(item[2]).name),
                item[2].casefold(),
            )
        )

        truncated = len(scored_results) > self._max_results
        results = [
            path
            for _, _, path in scored_results[:self._max_results]
        ]

        self.results_ready.emit(
            self._generation,
            results,
            truncated,
        )

    def _score_name(
        self,
        name_text: str,
        stem_text: str,
        name: str,
        stem: str,
    ) -> float | None:
        if not name:
            return None

        if self._query == name or self._query == stem:
            return 5.0

        if name.startswith(self._query) or stem.startswith(self._query):
            return 4.5

        if self._query in name or self._query in stem:
            return 4.0

        compact_query = self._compact(self._query)
        compact_name = self._compact(name)
        compact_stem = self._compact(stem)

        if compact_query:
            if compact_query == compact_name or compact_query == compact_stem:
                return 3.8

            if (
                compact_query in compact_name
                or compact_query in compact_stem
            ):
                return 3.5

        if self._strict_filename_query:
            return None

        token_scores: list[float] = []

        for token in self._tokens:
            token_score = self._score_token(
                token=token,
                name=name,
                stem=stem,
                name_text=name_text,
                stem_text=stem_text,
            )
            if token_score is None:
                return None
            token_scores.append(token_score)

        if not token_scores:
            return None

        return sum(token_scores) / len(token_scores)

    def _score_token(
        self,
        token: str,
        name: str,
        stem: str,
        name_text: str,
        stem_text: str,
    ) -> float | None:
        if token == name or token == stem:
            return 3.3

        if name.startswith(token) or stem.startswith(token):
            return 3.0

        if token in name or token in stem:
            return 2.8

        compact_token = self._compact(token)
        if len(compact_token) < 4:
            return None

        candidate_parts = self._candidate_parts(
            name_text,
            stem_text,
        )
        best = 0.0

        for candidate in candidate_parts:
            compact_candidate = self._compact(candidate)
            if not compact_candidate:
                continue

            length_gap = abs(
                len(compact_candidate) - len(compact_token)
            )
            allowed_gap = max(
                2,
                len(compact_token) // 4,
            )
            if length_gap > allowed_gap:
                continue

            matcher = SequenceMatcher(
                None,
                compact_token,
                compact_candidate,
            )

            if matcher.real_quick_ratio() < self._fuzzy_threshold:
                continue
            if matcher.quick_ratio() < self._fuzzy_threshold:
                continue

            best = max(
                best,
                matcher.ratio(),
            )

        if best < self._fuzzy_threshold:
            return None

        return 1.5 + best

    def _candidate_parts(
        self,
        name: str,
        stem: str,
    ) -> list[str]:
        parts = [name, stem]
        parts.extend(
            part
            for part in re.split(r"[_\-.\s]+", stem)
            if part
        )
        return parts

    def _normalize(self, value: str) -> str:
        return str(value).casefold().strip()

    def _compact(self, value: str) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            "",
            value.casefold(),
        )
