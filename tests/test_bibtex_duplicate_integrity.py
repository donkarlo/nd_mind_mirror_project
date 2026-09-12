"""Regression checks for BibTeX duplicate-key validation and paste protection."""

from nd_mind_mirror.core.bibliography.bibtex_duplicate_key_validator import (
    BibtexDuplicateKeyValidator,
)
from nd_mind_mirror.core.bibliography.bibtex_entry_key_parser import (
    BibtexEntryKeyParser,
)
from nd_mind_mirror.core.bibliography.bibtex_paste_guard import BibtexPasteGuard


def test_parser_extracts_top_level_entry_keys_and_ignores_special_entries() -> None:
    source = """% @article{commented-out,\n@string{journal = \"Journal\"}\n@comment{\n@article{nested-in-comment,\n}\n}\n@article{alpha-key,\n  title = {A}\n}\n@book(beta-key,\n  title = {B}\n)\n"""

    assert BibtexEntryKeyParser().parse(source) == [
        ("alpha-key", 7),
        ("beta-key", 10),
    ]


def test_validator_reports_every_line_for_duplicate_key() -> None:
    source = """@article{same-key,\n}\n\n@book{unique-key,\n}\n\n@misc{same-key,\n}\n"""

    assert BibtexDuplicateKeyValidator().duplicates(source) == {
        "same-key": (1, 7),
    }


def test_paste_guard_blocks_key_that_already_exists() -> None:
    document = """@article{existing-key,\n  title = {Original}\n}\n"""
    pasted = """@book{existing-key,\n  title = {Duplicate}\n}\n"""

    assert BibtexPasteGuard().conflicts(
        document,
        len(document),
        len(document),
        pasted,
    ) == ("existing-key",)


def test_paste_guard_blocks_duplicate_keys_inside_one_paste() -> None:
    pasted = """@article{same-key,\n}\n@book{same-key,\n}\n"""

    assert BibtexPasteGuard().conflicts("", 0, 0, pasted) == ("same-key",)


def test_paste_guard_allows_replacing_selected_entry_with_same_key() -> None:
    document = """@article{replace-me,\n  title = {Old}\n}\n@book{other-key,\n}\n"""
    selected_end = document.index("@book")
    replacement = """@article{replace-me,\n  title = {New}\n}\n"""

    assert BibtexPasteGuard().conflicts(
        document,
        0,
        selected_end,
        replacement,
    ) == ()


def test_unrelated_plain_text_paste_is_never_blocked() -> None:
    document = """@article{existing-key,\n}\n"""

    assert BibtexPasteGuard().conflicts(
        document,
        len(document),
        len(document),
        "ordinary notes",
    ) == ()
