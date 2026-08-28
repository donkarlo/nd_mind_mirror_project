from nd_mind_mirror.core.yaml.formatting.yaml_formatter import YamlFormatter


def test_formats_nested_mapping_and_sequence_with_configured_indent() -> None:
    source = (
        "root:\n"
        "  child:\n"
        "    - first\n"
        "    - second\n"
        "  next: value\n"
    )

    formatted = YamlFormatter(indent_size=4).format(source)

    assert formatted == (
        "root:\n"
        "    child:\n"
        "        - first\n"
        "        - second\n"
        "    next: value\n"
    )


def test_preserves_comments_quotes_and_key_order() -> None:
    source = (
        "first: \"a # value\"\n"
        "second:\n"
        "  # keep this comment\n"
        "  child: 'quoted value'\n"
        "third: 3\n"
    )

    formatted = YamlFormatter(indent_size=4).format(source)

    assert formatted == (
        "first: \"a # value\"\n"
        "second:\n"
        "    # keep this comment\n"
        "    child: 'quoted value'\n"
        "third: 3\n"
    )


def test_preserves_block_scalar_text_while_rebasing_indentation() -> None:
    source = (
        "root:\n"
        "  text: |\n"
        "    first line\n"
        "      intentionally indented\n"
        "  folded: >-\n"
        "    second line\n"
    )

    formatted = YamlFormatter(indent_size=4).format(source)

    assert formatted == (
        "root:\n"
        "    text: |\n"
        "        first line\n"
        "          intentionally indented\n"
        "    folded: >-\n"
        "        second line\n"
    )


def test_expands_leading_tabs_without_touching_content_tabs() -> None:
    source = "root:\n\tchild: \"a\\tb\"\n"

    formatted = YamlFormatter(indent_size=4).format(source)

    assert formatted == "root:\n    child: \"a\\tb\"\n"
