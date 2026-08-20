from dataclasses import dataclass
import re

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


@dataclass(frozen=True)
class YamlStructureNode:
    kind: str
    title: str
    line_number: int
    level: int


class YamlStructureParser:
    """Extract a navigable YAML hierarchy with source line numbers."""

    def __init__(self, tab_size: int = 4) -> None:
        self._tab_size = max(1, min(int(tab_size), 16))

    def set_tab_size(self, tab_size: int) -> None:
        self._tab_size = max(1, min(int(tab_size), 16))

    def parse(self, source: str) -> list[YamlStructureNode]:
        if not source.strip():
            return []
        try:
            root = yaml.compose(source)
        except yaml.YAMLError:
            return self._fallback_parse(source)
        if root is None:
            return []

        output: list[YamlStructureNode] = []
        self._walk(root, 0, output)
        return output

    def _walk(self, node, level: int, output: list[YamlStructureNode]) -> None:
        if isinstance(node, MappingNode):
            for key_node, value_node in node.value:
                title = self._node_title(key_node)
                output.append(
                    YamlStructureNode(
                        kind="key",
                        title=title,
                        line_number=key_node.start_mark.line + 1,
                        level=level,
                    )
                )
                if isinstance(value_node, (MappingNode, SequenceNode)):
                    self._walk(value_node, level + 1, output)
            return

        if isinstance(node, SequenceNode):
            for index, value_node in enumerate(node.value, start=1):
                if isinstance(value_node, ScalarNode):
                    title = self._node_title(value_node)
                    output.append(
                        YamlStructureNode(
                            kind="item",
                            title=f"[{index}] {title}",
                            line_number=value_node.start_mark.line + 1,
                            level=level,
                        )
                    )
                else:
                    output.append(
                        YamlStructureNode(
                            kind="item",
                            title=f"[{index}]",
                            line_number=value_node.start_mark.line + 1,
                            level=level,
                        )
                    )
                    self._walk(value_node, level + 1, output)

    def _node_title(self, node) -> str:
        if isinstance(node, ScalarNode):
            value = str(node.value).strip()
            return value if value else "(empty)"
        return "(node)"

    def _fallback_parse(self, source: str) -> list[YamlStructureNode]:
        """Keep Structure useful while the user is typing invalid YAML."""
        output: list[YamlStructureNode] = []
        indents: list[int] = []

        for line_number, raw_line in enumerate(source.splitlines(), start=1):
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue

            expanded = raw_line.expandtabs(self._tab_size)
            stripped = expanded.lstrip(" ")
            indent = len(expanded) - len(stripped)

            while indents and indent < indents[-1]:
                indents.pop()
            if not indents or indent > indents[-1]:
                indents.append(indent)
            level = max(len(indents) - 1, 0)

            candidate = stripped
            if candidate.startswith("- "):
                candidate = candidate[2:].lstrip()
                kind = "item"
            else:
                kind = "key"

            match = re.match(r"([^:#][^:]*?):(?:\s|$)", candidate)
            if match:
                title = match.group(1).strip().strip("'\"")
            elif kind == "item":
                title = candidate.split(" #", 1)[0].strip()
            else:
                continue

            if title:
                output.append(
                    YamlStructureNode(
                        kind=kind,
                        title=title,
                        line_number=line_number,
                        level=level,
                    )
                )

        return output
