from nd_mind_mirror.core.yaml.structure.yaml_structure_parser import (
    YamlStructureParser,
)


def test_yaml_structure_parser_extracts_nested_mapping_hierarchy() -> None:
    source = (
        "editor:\n"
        "  font_size: 16\n"
        "  colors:\n"
        "    background: white\n"
        "search:\n"
        "  max_results: 100\n"
    )

    items = YamlStructureParser().parse(source)
    assert [(item.title, item.level, item.line_number) for item in items] == [
        ("editor", 0, 1),
        ("font_size", 1, 2),
        ("colors", 1, 3),
        ("background", 2, 4),
        ("search", 0, 5),
        ("max_results", 1, 6),
    ]


def test_yaml_structure_fallback_survives_incomplete_yaml() -> None:
    source = "editor:\n  font_size: 16\n  broken: [\n"
    items = YamlStructureParser().parse(source)
    assert [item.title for item in items] == ["editor", "font_size", "broken"]
