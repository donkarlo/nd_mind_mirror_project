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
            tuple[str, str, str, str, str, bool, str]
        ],
        query: str,
        max_results: int,
        fuzzy_threshold: float,
        hierarchical_path_matching: bool = True,
        parent=None,
        root_path: str | Path | None = None,
        workspace_root_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)

        self._generation = generation
        self._entries = entries
        raw_query = str(query).strip()
        self._raw_query = raw_query
        self._root_path = (
            Path(root_path).expanduser() if root_path is not None else None
        )
        self._workspace_root_path = (
            Path(workspace_root_path).expanduser()
            if workspace_root_path is not None
            else self._root_path
        )
        hierarchy_chain = [
            part.strip().casefold()
            for part in raw_query.split(">")
            if part.strip()
        ]
        self._hierarchy_chain = (
            hierarchy_chain if len(hierarchy_chain) >= 2 else []
        )
        effective_query = (
            hierarchy_chain[-1]
            if self._hierarchy_chain
            else raw_query
        )
        self._query = self._normalize(effective_query)
        self._tokens = [
            token
            for token in re.split(r"\s+", self._query)
            if token
        ]
        self._query_pairs = (
            tuple(self._query[index:index + 2] for index in range(len(self._query) - 1))
            if len(self._query) >= 8 else ()
        )
        self._max_results = max(int(max_results), 1)
        self._fuzzy_threshold = max(
            0.75,
            min(float(fuzzy_threshold), 0.98),
        )
        self._strict_filename_query = (
            "." in self._query
        )
        self._hierarchical_path_matching = bool(
            hierarchical_path_matching
        )

    def run(self) -> None:
        """Find literal matches first and use costly fuzzy matching only as fallback."""
        direct_path = self._find_direct_path()
        if direct_path is not None:
            self.results_ready.emit(
                self._generation,
                [{"path": str(direct_path), "is_directory": direct_path.is_dir()}],
                False,
            )
            return
        if self._is_absolute_query() or not self._tokens:
            self.results_ready.emit(self._generation, [], False)
            return

        scored_results: list[tuple[float, int, str]] = []
        for allow_fuzzy in (False, True):
            for index, entry in enumerate(self._entries, start=1):
                if self.isInterruptionRequested():
                    return
                score = self._score_entry(entry, allow_fuzzy)
                if score is not None:
                    scored_results.append((score, 0 if entry[5] else 1, entry[0]))
                self._yield_during_search(index)
            if scored_results:
                break

        if self.isInterruptionRequested():
            return
        scored_results.sort(
            key=lambda item: (-item[0], item[1], len(Path(item[2]).name), item[2].casefold())
        )
        truncated = len(scored_results) > self._max_results
        self.results_ready.emit(
            self._generation,
            [path for _, _, path in scored_results[:self._max_results]],
            truncated,
        )

    def _find_direct_path(self) -> Path | None:
        """Resolve explicit OS, workspace-rooted, and relative paths in the worker."""
        query = self._raw_query
        if not query or ("/" not in query and not query.startswith("~")):
            return None
        expanded = Path(query).expanduser()
        candidates: list[Path] = []
        if query.startswith("/") and self._workspace_root_path is not None:
            candidates.append(self._workspace_root_path / query.lstrip("/"))
        if self._root_path is not None:
            candidates.append(self._root_path / query.lstrip("/"))
        if expanded.is_absolute():
            candidates.append(expanded)
        for path in candidates:
            try:
                if path.is_file() or path.is_dir():
                    return path.resolve()
            except OSError:
                continue
        return None

    def _is_absolute_query(self) -> bool:
        """Avoid expensive fuzzy scans for incomplete absolute paths."""
        return self._raw_query.startswith("/") or self._raw_query.startswith("~/")

    def _score_entry(
        self,
        entry: tuple[str, str, str, str, str, bool, str],
        allow_fuzzy: bool,
    ) -> float | None:
        """Score one indexed path without filesystem access."""
        _, name_text, stem_text, normalized_name, normalized_stem, _, relative_path = entry
        if "/" in self._raw_query:
            path_query = self._raw_query.casefold().strip("/")
            if relative_path == path_query:
                return 5.5
            if relative_path.endswith("/" + path_query):
                return 5.2
            if path_query in relative_path:
                return 4.2
            return None
        if self._hierarchy_chain:
            return self._score_explicit_hierarchy(
                relative_path, name_text, stem_text, allow_fuzzy=allow_fuzzy,
            )
        score = self._score_name(
            name_text, stem_text, normalized_name, normalized_stem,
            allow_fuzzy=allow_fuzzy,
        )
        if (
            score is None
            and self._hierarchical_path_matching
            and not self._strict_filename_query
            and len(self._tokens) >= 2
        ):
            score = self._score_hierarchical_path(
                relative_path, allow_fuzzy=allow_fuzzy,
            )
        return score

    def _yield_during_search(self, index: int) -> None:
        """Hook for cooperative workers without slowing the base scoring loop."""
        del index

    def _score_name(
        self,
        name_text: str,
        stem_text: str,
        name: str,
        stem: str,
        allow_fuzzy: bool = True,
    ) -> float | None:
        if not name:
            return None

        if self._query == name or self._query == stem:
            return 5.0

        if name.startswith(self._query) or stem.startswith(self._query):
            return 4.5

        if self._query in name or self._query in stem:
            return 4.0

        if not allow_fuzzy:
            literal_scores = [
                self._score_token(token, name, stem, name_text, stem_text, allow_fuzzy=False)
                for token in self._tokens
            ]
            if all(score is not None for score in literal_scores):
                return sum(literal_scores) / len(literal_scores)
            return None

        if self._strict_filename_query:
            return None
        if self._query_pairs and not any(pair in name for pair in self._query_pairs):
            return None

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

    def _score_explicit_hierarchy(
        self,
        relative_path: str,
        name_text: str,
        stem_text: str,
        allow_fuzzy: bool = True,
    ) -> float | None:
        """Score an ordered ``parent > child`` chain without runtime patching."""
        components = [
            component
            for component in Path(relative_path).parts
            if component
        ]
        if not components:
            return None

        leaf = self._hierarchy_chain[-1]
        leaf_score = self._score_token(
            token=leaf,
            name=name_text.casefold(),
            stem=stem_text.casefold(),
            name_text=name_text,
            stem_text=stem_text,
            allow_fuzzy=allow_fuzzy,
        )
        if leaf_score is None:
            return None

        ancestors = components[:-1]
        search_from = 0
        parent_score = 0.0
        for token in self._hierarchy_chain[:-1]:
            matched: tuple[int, float] | None = None
            for index in range(search_from, len(ancestors)):
                component = ancestors[index]
                stem = Path(component).stem
                score = self._score_token(
                    token=token,
                    name=component.casefold(),
                    stem=stem.casefold(),
                    name_text=component,
                    stem_text=stem,
                    allow_fuzzy=allow_fuzzy,
                )
                if score is None and allow_fuzzy:
                    score = self._family_prefix_score(
                        token,
                        stem.casefold(),
                    )
                if score is not None:
                    matched = (index, score)
                    break
            if matched is None:
                return None
            search_from = matched[0] + 1
            parent_score += matched[1]

        return min(
            5.0,
            3.6 + leaf_score * 0.25 + parent_score * 0.08,
        )

    def _score_hierarchical_path(
        self, relative_path: str, allow_fuzzy: bool = True,
    ) -> float | None:
        if not allow_fuzzy and not all(token in relative_path for token in self._tokens):
            return None
        components = [
            component
            for component in Path(relative_path).parts
            if component
        ]
        if not components:
            return None

        component_candidates: list[tuple[str, str, str, int]] = []
        for index, component in enumerate(components):
            stem = Path(component).stem
            component_candidates.append(
                (component, stem, component.casefold(), index)
            )

        token_matches: list[tuple[float, int]] = []
        for token in self._tokens:
            best_score: float | None = None
            best_index = -1
            for name_text, stem_text, normalized, index in component_candidates:
                score = self._score_token(
                    token=token,
                    name=normalized,
                    stem=stem_text.casefold(),
                    name_text=name_text,
                    stem_text=stem_text,
                    allow_fuzzy=allow_fuzzy,
                )
                if score is None and allow_fuzzy:
                    score = self._family_prefix_score(token, stem_text.casefold())
                if score is not None and (best_score is None or score > best_score):
                    best_score = score
                    best_index = index
            if best_score is None:
                return None
            token_matches.append((best_score, best_index))

        base = sum(score for score, _ in token_matches) / len(token_matches)
        indices = [index for _, index in token_matches]
        distinct_bonus = 0.35 if len(set(indices)) > 1 else 0.0
        ordered_bonus = 0.20 if indices == sorted(indices) else 0.0
        return min(3.45, base + distinct_bonus + ordered_bonus)

    def _family_prefix_score(self, token: str, candidate: str) -> float | None:
        compact_token = self._compact(token)
        compact_candidate = self._compact(candidate)
        if len(compact_token) < 5 or len(compact_candidate) < 5:
            return None
        common = 0
        for left, right in zip(compact_token, compact_candidate):
            if left != right:
                break
            common += 1
        minimum = max(4, int(min(len(compact_token), len(compact_candidate)) * 0.65))
        if common < minimum:
            return None
        return 2.05 + common / max(len(compact_token), len(compact_candidate))

    def _score_token(
        self,
        token: str,
        name: str,
        stem: str,
        name_text: str,
        stem_text: str,
        allow_fuzzy: bool = True,
    ) -> float | None:
        if token == name or token == stem:
            return 3.3

        if name.startswith(token) or stem.startswith(token):
            return 3.0

        if token in name or token in stem:
            return 2.8

        if not allow_fuzzy:
            return None

        # A close match of eight or more characters must share a short
        # adjacent pair. Reject unrelated names before Python fuzzy scoring.
        if len(token) >= 8 and not any(
            token[index:index + 2] in name
            for index in range(len(token) - 1)
        ):
            return None

        compact_token = self._compact(token)
        compact_stem = self._compact(stem)
        if self._is_single_adjacent_transposition(compact_token, compact_stem):
            return 2.75
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

    def _is_single_adjacent_transposition(self, left: str, right: str) -> bool:
        if len(left) != len(right) or left == right or len(left) < 2:
            return False
        differences = [
            index
            for index, (a, b) in enumerate(zip(left, right))
            if a != b
        ]
        if len(differences) != 2:
            return False
        first, second = differences
        return (
            second == first + 1
            and left[first] == right[second]
            and left[second] == right[first]
        )

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
