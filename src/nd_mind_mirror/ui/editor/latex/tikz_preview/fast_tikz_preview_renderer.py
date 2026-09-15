"""Low-cost Qt renderer for the conservative TikZ subset edited on iPad."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)


@dataclass(frozen=True)
class _Node:
    name: str
    label: str
    x: float
    y: float
    width: float
    height: float
    ellipse: bool
    fill: QColor
    stroke: QColor
    text: QColor
    line_width: float


@dataclass(frozen=True)
class _Edge:
    source: str
    target: str
    label: str
    path_body: str
    options: str
    stroke: QColor
    text: QColor
    line_width: float
    dashed: bool
    directed: bool
    empty_arrow: bool


class TikZFastPreviewRenderer:
    """Render iPad-generated nodes/connectors without launching LuaLaTeX."""

    _CANVAS_WIDTH = 16.0
    _CANVAS_HEIGHT = 11.0
    _IMAGE_WIDTH = 960
    _IMAGE_HEIGHT = 660

    _NODE = re.compile(
        r"\\node\s*(?:\[([^\]]*)\]\s*)?\(([^\)]+)\)\s*"
        r"at\s*\((-?[0-9.]+)\s*,\s*(-?[0-9.]+)\)\s*"
        r"\{([^{}]*)\}\s*;"
    )
    _EDGE = re.compile(
        r"\\draw\s*(?:\[((?:[^\[\]]|\[[^\]]*\])*)\])?\s*"
        r"\(([^\)]+)\)\s*(.*?)\s*\(([^\)]+)\)\s*;",
        re.DOTALL,
    )
    _CURVE = re.compile(
        r"\.\.\s*controls\s*"
        r"\(\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\)\s*"
        r"and\s*"
        r"\(\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\)\s*\.\."
    )
    _BEND = re.compile(
        r"--\s*\(\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\)"
    )
    _LABEL = re.compile(r"node(?:\[([^\]]*)\])?\s*\{([^{}]*)\}")
    _COMMAND = re.compile(r"\\([A-Za-z]+)")
    _SUPPORTED_COMMANDS = {
        "begin",
        "end",
        "usetikzlibrary",
        "node",
        "draw",
    }

    def render(self, source: str, _source_file: Path | None = None) -> QImage | None:
        """Return a fast preview, or None when the source needs real TikZ."""
        if not self._supports(source):
            return None

        nodes = self._parse_nodes(source)
        if not nodes:
            return None
        node_by_name = {node.name: node for node in nodes}
        edges = self._parse_edges(source)
        if any(edge.source not in node_by_name or edge.target not in node_by_name for edge in edges):
            return None

        image = QImage(
            self._IMAGE_WIDTH,
            self._IMAGE_HEIGHT,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            for edge in edges:
                self._draw_edge(painter, edge, node_by_name)
            for node in nodes:
                self._draw_node(painter, node)
        finally:
            painter.end()
        return image

    def _supports(self, source: str) -> bool:
        if "\\begin{tikzpicture}" not in source or "\\documentclass" in source:
            return False
        for command in self._COMMAND.findall(source):
            if command not in self._SUPPORTED_COMMANDS:
                return False
        return True

    def _parse_nodes(self, source: str) -> list[_Node]:
        result: list[_Node] = []
        for match in self._NODE.finditer(source):
            raw_options = match.group(1) or ""
            options = self._options(raw_options)
            ellipse = "ellipse" in options or "circle" in options
            result.append(
                _Node(
                    name=match.group(2).strip(),
                    label=self._plain_label(match.group(5)),
                    x=float(match.group(3)),
                    y=float(match.group(4)),
                    width=self._measurement(options.get("minimum width"), 1.8 if ellipse else 2.0),
                    height=self._measurement(options.get("minimum height"), 1.1 if ellipse else 1.0),
                    ellipse=ellipse,
                    fill=self._color(options.get("fill"), QColor("white")),
                    stroke=self._color(options.get("draw"), QColor("black")),
                    text=self._color(options.get("text"), QColor("black")),
                    line_width=self._measurement(options.get("line width"), 1.0),
                )
            )
        return result

    def _parse_edges(self, source: str) -> list[_Edge]:
        result: list[_Edge] = []
        for match in self._EDGE.finditer(source):
            raw_options = match.group(1) or ""
            path_body = match.group(3) or ""
            options = self._options(raw_options)
            label_match = self._LABEL.search(path_body)
            label = self._plain_label(label_match.group(2)) if label_match else ""
            label_options = self._options(label_match.group(1) or "") if label_match else {}
            lowered = raw_options.lower()
            result.append(
                _Edge(
                    source=match.group(2).strip(),
                    target=match.group(4).strip(),
                    label=label,
                    path_body=path_body,
                    options=raw_options,
                    stroke=self._color(options.get("draw"), QColor("black")),
                    text=self._color(label_options.get("text"), QColor("black")),
                    line_width=self._measurement(options.get("line width"), 1.0),
                    dashed="dashed" in options,
                    directed=("->" in options or "latex" in lowered),
                    empty_arrow="latex[open]" in lowered,
                )
            )
        return result

    def _draw_node(self, painter: QPainter, node: _Node) -> None:
        center = self._view_point(node.x, node.y)
        width = max(node.width / self._CANVAS_WIDTH * self._IMAGE_WIDTH, 36.0)
        height = max(node.height / self._CANVAS_HEIGHT * self._IMAGE_HEIGHT, 28.0)
        rect = QRectF(center.x() - width / 2, center.y() - height / 2, width, height)
        painter.setPen(QPen(node.stroke, max(node.line_width, 0.8)))
        painter.setBrush(node.fill)
        if node.ellipse:
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        if node.label:
            painter.setPen(node.text)
            painter.setFont(QFont("Sans Serif", 10))
            painter.drawText(rect.adjusted(4, 3, -4, -3), Qt.AlignmentFlag.AlignCenter, node.label)

    def _draw_edge(self, painter: QPainter, edge: _Edge, nodes: dict[str, _Node]) -> None:
        source = nodes[edge.source]
        target = nodes[edge.target]
        source_center = self._view_point(source.x, source.y)
        target_center = self._view_point(target.x, target.y)

        curve = self._CURVE.search(edge.path_body)
        bends = [
            self._view_point(float(x), float(y))
            for x, y in self._BEND.findall(edge.path_body)
        ]

        if curve is not None:
            first = self._view_point(float(curve.group(1)), float(curve.group(2)))
            second = self._view_point(float(curve.group(3)), float(curve.group(4)))
            start = self._boundary(source, source_center, first)
            end = self._boundary(target, target_center, second)
            path = QPainterPath(start)
            path.cubicTo(first, second, end)
        elif bends:
            start = self._boundary(source, source_center, bends[0])
            end = self._boundary(target, target_center, bends[-1])
            path = QPainterPath(start)
            for point in bends:
                path.lineTo(point)
            path.lineTo(end)
        else:
            start = self._boundary(source, source_center, target_center)
            end = self._boundary(target, target_center, source_center)
            path = QPainterPath(start)
            path.lineTo(end)

        pen = QPen(edge.stroke, max(edge.line_width, 0.8))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if edge.dashed:
            pen.setDashPattern([8.0, 5.0])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if edge.directed:
            self._draw_arrow(painter, path, edge)
        if edge.label:
            self._draw_edge_label(painter, path, edge)

    def _draw_arrow(self, painter: QPainter, path: QPainterPath, edge: _Edge) -> None:
        end = path.pointAtPercent(1.0)
        before = path.pointAtPercent(0.985)
        dx = end.x() - before.x()
        dy = end.y() - before.y()
        length = max(math.hypot(dx, dy), 1.0)
        ux = dx / length
        uy = dy / length
        size = 10.0
        base = QPointF(end.x() - ux * size, end.y() - uy * size)
        px, py = -uy, ux
        left = QPointF(base.x() + px * size * 0.45, base.y() + py * size * 0.45)
        right = QPointF(base.x() - px * size * 0.45, base.y() - py * size * 0.45)
        polygon = QPolygonF([end, left, right])
        painter.setPen(QPen(edge.stroke, max(edge.line_width, 0.8)))
        painter.setBrush(Qt.BrushStyle.NoBrush if edge.empty_arrow else edge.stroke)
        painter.drawPolygon(polygon)

    def _draw_edge_label(self, painter: QPainter, path: QPainterPath, edge: _Edge) -> None:
        center = path.pointAtPercent(0.5)
        font = QFont("Sans Serif", 9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = max(metrics.horizontalAdvance(edge.label) + 10, 28)
        height = metrics.height() + 6
        rect = QRectF(center.x() - width / 2, center.y() - height / 2, width, height)
        painter.fillRect(rect, QColor(255, 255, 255, 235))
        painter.setPen(edge.text)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, edge.label)

    def _boundary(self, node: _Node, center: QPointF, toward: QPointF) -> QPointF:
        rx = max(node.width / self._CANVAS_WIDTH * self._IMAGE_WIDTH / 2, 18.0)
        ry = max(node.height / self._CANVAS_HEIGHT * self._IMAGE_HEIGHT / 2, 14.0)
        dx = toward.x() - center.x()
        dy = toward.y() - center.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return center
        if node.ellipse:
            scale = 1.0 / max(math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2), 1e-6)
        else:
            scale = min(rx / max(abs(dx), 1e-6), ry / max(abs(dy), 1e-6))
        return QPointF(center.x() + dx * scale, center.y() + dy * scale)

    def _view_point(self, x: float, y: float) -> QPointF:
        return QPointF(
            x / self._CANVAS_WIDTH * self._IMAGE_WIDTH,
            (1.0 - y / self._CANVAS_HEIGHT) * self._IMAGE_HEIGHT,
        )

    @staticmethod
    def _measurement(raw: str | None, default: float) -> float:
        if raw is None:
            return default
        value = raw.strip().lower().replace("cm", "").replace("pt", "")
        try:
            return float(value)
        except ValueError:
            return default

    @classmethod
    def _options(cls, raw: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for field in cls._split_options(raw):
            item = field.strip()
            if not item:
                continue
            if "=" in item:
                key, value = item.split("=", 1)
                result[key.strip().lower()] = value.strip()
            else:
                result[item.lower()] = ""
        return result

    @staticmethod
    def _split_options(raw: str) -> list[str]:
        fields: list[str] = []
        start = 0
        brace_depth = 0
        bracket_depth = 0
        for index, character in enumerate(raw):
            if character == "{":
                brace_depth += 1
            elif character == "}":
                brace_depth = max(brace_depth - 1, 0)
            elif character == "[":
                bracket_depth += 1
            elif character == "]":
                bracket_depth = max(bracket_depth - 1, 0)
            elif character == "," and brace_depth == 0 and bracket_depth == 0:
                fields.append(raw[start:index])
                start = index + 1
        fields.append(raw[start:])
        return fields

    @staticmethod
    def _color(raw: str | None, default: QColor) -> QColor:
        if raw is None:
            return QColor(default)
        value = raw.strip()
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1].strip()
        named = {
            "black": QColor(0, 0, 0),
            "white": QColor(255, 255, 255),
            "red": QColor(255, 0, 0),
            "green": QColor(0, 128, 0),
            "blue": QColor(0, 0, 255),
            "gray": QColor(128, 128, 128),
            "grey": QColor(128, 128, 128),
            "orange": QColor(255, 128, 0),
            "yellow": QColor(255, 255, 0),
            "purple": QColor(128, 0, 179),
            "violet": QColor(128, 0, 179),
        }
        lowered = value.lower()
        if lowered in named:
            return named[lowered]
        if lowered.startswith("rgb,255:"):
            components: dict[str, int] = {}
            for field in value[len("rgb,255:"):].split(";"):
                if "," not in field:
                    continue
                key, number = field.split(",", 1)
                try:
                    components[key.strip().lower()] = int(float(number.strip()))
                except ValueError:
                    continue
            if {"red", "green", "blue"}.issubset(components):
                return QColor(
                    components["red"],
                    components["green"],
                    components["blue"],
                )
        return QColor(default)

    @staticmethod
    def _plain_label(raw: str) -> str:
        return raw.replace(r"\_", "_")
