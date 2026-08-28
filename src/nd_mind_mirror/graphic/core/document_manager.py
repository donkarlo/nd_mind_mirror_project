from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import binascii
import json
import re
import struct
import zlib

from PySide6.QtGui import QImageReader


@dataclass(frozen=True)
class GraphicDocument:
    image_path: Path
    sidecar_path: Path
    tex_reference: str


@dataclass(frozen=True)
class GraphicReference:
    image_path: Path
    sidecar_path: Path
    tex_reference: str
    start: int
    end: int


class GraphicDocumentManager:
    """Create and locate source-backed raster graphics used by LaTeX.

    The editable PencilKit state is stored in a small ``.ndgraphic`` JSON
    sidecar. LaTeX only sees the neighboring PNG, so the generated document
    remains ordinary portable LaTeX and the iPad editor can preserve strokes
    for later editing.
    """

    _INCLUDE_GRAPHICS = re.compile(
        r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{(?P<path>[^}]+)\}",
        re.MULTILINE,
    )

    def __init__(
        self,
        *,
        directory_name: str = ".",
        width_ratio: float = 0.90,
        canvas_width: int = 1240,
        canvas_height: int = 1754,
    ) -> None:
        cleaned = str(directory_name).strip().strip("/\\") or "."
        self.directory_name = cleaned
        self.width_ratio = max(0.10, min(float(width_ratio), 1.0))
        self.canvas_width = max(int(canvas_width), 64)
        self.canvas_height = max(int(canvas_height), 64)

    def create_for_source(self, source_path: str | Path) -> GraphicDocument:
        source = Path(source_path).expanduser().resolve()
        directory = source.parent
        directory.mkdir(parents=True, exist_ok=True)

        image_path = self._next_image_path(directory)
        sidecar_path = image_path.with_suffix(".ndgraphic")
        self._write_blank_png(image_path, self.canvas_width, self.canvas_height)
        self._write_sidecar(sidecar_path, image_path, source)
        relative = image_path.relative_to(source.parent).as_posix()
        return GraphicDocument(image_path, sidecar_path, relative)

    def find_reference(
        self,
        source: str,
        source_path: str | Path,
        position: int,
    ) -> GraphicReference | None:
        source_file = Path(source_path).expanduser().resolve()
        position = max(0, min(int(position), len(source)))
        matches = list(self._INCLUDE_GRAPHICS.finditer(source))
        if not matches:
            return None

        chosen = None
        for match in matches:
            if match.start() <= position <= match.end():
                chosen = match
                break
        if chosen is None:
            for match in matches:
                figure_start = source.rfind("\\begin{figure}", 0, match.start())
                figure_end = source.find("\\end{figure}", match.end())
                if figure_start < 0 or figure_end < 0:
                    continue
                figure_end += len("\\end{figure}")
                nested_end = source.find("\\end{figure}", figure_start, match.start())
                if nested_end >= 0:
                    continue
                if figure_start <= position <= figure_end:
                    chosen = match
                    break
        if chosen is None:
            line_start = source.rfind("\n", 0, position) + 1
            line_end = source.find("\n", position)
            if line_end < 0:
                line_end = len(source)
            for match in matches:
                if match.start() >= line_start and match.end() <= line_end:
                    chosen = match
                    break
        if chosen is None:
            return None

        raw = chosen.group("path").strip()
        if not raw or raw.startswith("\\"):
            return None
        image = Path(raw).expanduser()
        if not image.is_absolute():
            image = source_file.parent / image
        image = image.resolve()
        if image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            return None
        sidecar = image.with_suffix(".ndgraphic")
        if not sidecar.exists():
            self._write_sidecar(sidecar, image, source_file)
        else:
            self._ensure_source_name(sidecar, source_file)
            self._ensure_image_canvas_size(sidecar, image)
        return GraphicReference(
            image_path=image,
            sidecar_path=sidecar,
            tex_reference=chosen.group(0),
            start=chosen.start(),
            end=chosen.end(),
        )

    def _next_image_path(self, directory: Path) -> Path:
        candidate = directory / "graphic.png"
        if not candidate.exists():
            return candidate
        counter = 2
        while True:
            candidate = directory / f"graphic_{counter}.png"
            if not candidate.exists():
                return candidate
            counter += 1

    def _write_sidecar(
        self,
        sidecar: Path,
        image_path: Path,
        source_path: str | Path | None = None,
    ) -> None:
        source_name = ""
        if source_path is not None:
            source_name = Path(source_path).expanduser().name
        # ND_MIGRATION4_NATIVE_IMAGE_CANVAS
        native_width, native_height = self._image_dimensions(image_path)
        canvas_width = native_width if native_width > 0 else self.canvas_width
        canvas_height = native_height if native_height > 0 else self.canvas_height
        payload = {
            "version": 1,
            "image_name": image_path.name,
            "source_name": source_name,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "drawing_data_base64": "",
            "background_image_base64": "",
            "web_strokes": [],
            "pencil": {
                "width": 6.0,
                "color": "#202020",
            },
        }
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        temp = sidecar.with_suffix(sidecar.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(sidecar)

    @staticmethod
    def _image_dimensions(image_path: Path) -> tuple[int, int]:
        try:
            size = QImageReader(str(image_path)).size()
        except Exception:
            return 0, 0
        if not size.isValid():
            return 0, 0
        return max(int(size.width()), 0), max(int(size.height()), 0)

    @classmethod
    def _ensure_image_canvas_size(cls, sidecar: Path, image_path: Path) -> None:
        """Use native JPG/PNG size until editable drawing/background data exists."""
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(payload, dict):
            return
        if str(payload.get("drawing_data_base64", "") or "").strip():
            return
        if str(payload.get("background_image_base64", "") or "").strip():
            return
        if payload.get("image_objects"):
            return
        width, height = cls._image_dimensions(image_path)
        if width <= 0 or height <= 0:
            return
        if (
            int(payload.get("canvas_width", 0) or 0) == width
            and int(payload.get("canvas_height", 0) or 0) == height
        ):
            return
        payload["canvas_width"] = width
        payload["canvas_height"] = height
        try:
            temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(sidecar)
        except OSError:
            return

    @staticmethod
    def _ensure_source_name(sidecar: Path, source_path: Path) -> None:
        """Backfill the owning LaTeX filename into older editable sidecars."""
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        source_name = source_path.name
        if str(payload.get("source_name", "")).strip() == source_name:
            return
        payload["source_name"] = source_name
        try:
            temp = sidecar.with_suffix(sidecar.suffix + ".tmp")
            temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp.replace(sidecar)
        except OSError:
            return

    @staticmethod
    def _png_chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    @classmethod
    def _write_blank_png(cls, path: Path, width: int, height: int) -> None:
        """Write a white RGB PNG using only the Python standard library."""
        path.parent.mkdir(parents=True, exist_ok=True)
        row = b"\x00" + (b"\xff\xff\xff" * width)
        raw = row * height
        png = b"\x89PNG\r\n\x1a\n"
        png += cls._png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
        png += cls._png_chunk(b"IDAT", zlib.compress(raw, level=9))
        png += cls._png_chunk(b"IEND", b"")
        path.write_bytes(png)
