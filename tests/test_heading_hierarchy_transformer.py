from nd_mind_mirror.core.latex.hierarchy.transformer.heading_hierarchy_transformer import (
    HeadingHierarchyTransformer,
)


def test_beamer_clamps_deep_recursive_headings_at_subsubsection() -> None:
    transformer = HeadingHierarchyTransformer("beamer")

    mapping = transformer.build_mapping(
        "\\section{Nervous system}\n\\subsection{}\n",
        "subsubsection",
    )
    rendered = transformer.transform(
        "\\section{Nervous system}\n\\subsection{}\n",
        mapping,
    )

    assert transformer.allowed_headings == (
        "part",
        "section",
        "subsection",
        "subsubsection",
    )
    assert mapping["section"] == "subsubsection"
    assert mapping["subsection"] == "subsubsection"
    assert "\\paragraph" not in rendered
    assert "\\subparagraph" not in rendered
    assert rendered.count("\\subsubsection") == 2


def test_article_keeps_paragraph_headings_available() -> None:
    transformer = HeadingHierarchyTransformer("article")

    assert "paragraph" in transformer.allowed_headings
    assert "subparagraph" in transformer.allowed_headings
