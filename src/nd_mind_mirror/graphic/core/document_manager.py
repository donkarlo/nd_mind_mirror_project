from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
from pathlib import Path
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

    The editable PencilKit state is stored in a neighboring ``.ndgraphic``
    sidecar. The raster remains the file seen by LaTeX, Source, Visual, and
    Preview, while the sidecar is the authoritative editable iPad document.
    """

    _INCLUDE_GRAPHICS = re.compile(
        r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{(?P<path>[^}]+)\}",
        re.MULTILINE,
    )
    _LATEX_EDITABLE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
    _FIGURE_BEGIN = re.compile(r"\\begin\s*\{figure\*?\}(?:\s*\[[^\]]*\])?")
    _FIGURE_END = re.compile(r"\\end\s*\{figure\*?\}")
    _SIDECAR_VERSION = 2

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
        self._write_blank_png(image_path, self.canvas_width, self.canvas_height)
        sidecar_path = self.ensure_for_image(image_path, source)
        relative = image_path.relative_to(source.parent).as_posix()
        return GraphicDocument(image_path, sidecar_path, relative)

    def ensure_for_image(
        self,
        image_path: str | Path,
        source_path: str | Path | None = None,
    ) -> Path:
        """Return a self-contained editable sidecar for one existing raster image."""
        image = Path(image_path).expanduser().resolve()
        sidecar = image.with_suffix(".ndgraphic")
        if not sidecar.exists():
            self._write_sidecar(sidecar, image, source_path)
            return sidecar

        if source_path is not None:
            self._ensure_source_name(
                sidecar,
                Path(source_path).expanduser().resolve(),
            )
        self._ensure_image_canvas_size(sidecar, image)
        self._ensure_background_snapshot(sidecar, image)
        return sidecar

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
                figure_range = self._containing_figure_range(source, match)
                if figure_range is None:
                    continue
                figure_start, figure_end = figure_range
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
        if image.suffix.lower() not in self._LATEX_EDITABLE_IMAGE_SUFFIXES:
            return None
        sidecar = self.ensure_for_image(image, source_file)
        return GraphicReference(
            image_path=image,
            sidecar_path=sidecar,
            tex_reference=chosen.group(0),
            start=chosen.start(),
            end=chosen.end(),
        )

    @classmethod
    def _containing_figure_range(
        cls,
        source: str,
        graphic_match: re.Match[str],
    ) -> tuple[int, int] | None:
        """Return the enclosing figure/figure* range for one includegraphics."""
        prior_begin = None
        for candidate in cls._FIGURE_BEGIN.finditer(source, 0, graphic_match.start()):
            prior_begin = candidate
        if prior_begin is None:
            return None

        prior_end = None
        for candidate in cls._FIGURE_END.finditer(source, 0, graphic_match.start()):
            prior_end = candidate
        if prior_end is not None and prior_end.start() > prior_begin.start():
            return None

        following_end = cls._FIGURE_END.search(source, graphic_match.end())
        if following_end is None:
            return None
        nested_begin = cls._FIGURE_BEGIN.search(
            source,
            prior_begin.end(),
            graphic_match.start(),
        )
        if nested_begin is not None:
            return None
        return prior_begin.start(), following_end.end()

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
        native_width, native_height = self._image_dimensions(image_path)
        canvas_width = native_width if native_width > 0 else self.canvas_width
        canvas_height = native_height if native_height > 0 else self.canvas_height
        background = self._encoded_image_snapshot(image_path)
        payload = {
            "version": self._SIDECAR_VERSION,
            "image_name": image_path.name,
            "source_name": source_name,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "drawing_data_base64": "",
            "background_image_base64": background,
            "background_is_authoritative": bool(background),
            "web_strokes": [],
            "pencil": {
                "width": 6.0,
                "color": "#202020",
            },
        }
        self._write_sidecar_payload(sidecar, payload)

    @staticmethod
    def _encoded_image_snapshot(image_path: Path) -> str:
        """Return the exact paired raster bytes as base64 for editable background use."""
        try:
            raw = Path(image_path).read_bytes()
        except OSError:
            return ""
        if not raw:
            return ""
        return base64.b64encode(raw).decode("ascii")

    @classmethod
    def _ensure_background_snapshot(cls, sidecar: Path, image_path: Path) -> None:
        """Migrate only untouched legacy sidecars to an authoritative background."""
        payload = cls._read_sidecar_payload(sidecar)
        if payload is None:
            return
        if str(payload.get("background_image_base64", "") or "").strip():
            return
        if str(payload.get("drawing_data_base64", "") or "").strip():
            return
        image_objects = payload.get("image_objects")
        if isinstance(image_objects, list) and image_objects:
            return
        if payload.get("web_strokes"):
            return

        background = cls._encoded_image_snapshot(image_path)
        if not background:
            return
        payload["version"] = max(
            int(payload.get("version", 1) or 1),
            cls._SIDECAR_VERSION,
        )
        payload["background_image_base64"] = background
        payload["background_is_authoritative"] = True
        cls._write_sidecar_payload(sidecar, payload)

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
        """Use native raster size until editable drawing/background data exists."""
        payload = cls._read_sidecar_payload(sidecar)
        if payload is None:
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
        cls._write_sidecar_payload(sidecar, payload)

    @classmethod
    def _ensure_source_name(cls, sidecar: Path, source_path: Path) -> None:
        """Backfill the owning LaTeX filename into older editable sidecars."""
        payload = cls._read_sidecar_payload(sidecar)
        if payload is None:
            return
        source_name = source_path.name
        if str(payload.get("source_name", "")).strip() == source_name:
            return
        payload["source_name"] = source_name
        cls._write_sidecar_payload(sidecar, payload)

    @staticmethod
    def _read_sidecar_payload(sidecar: Path) -> dict[str, object] | None:
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _write_sidecar_payload(sidecar: Path, payload: dict[str, object]) -> None:
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(sidecar)

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
