"""Regression checks for the raster/ND Graphic companion document contract."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from nd_mind_mirror.core.workspace.operation.filesystem_operation_service import (
    WorkspaceFilesystemOperationService,
)


PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402

from nd_mind_mirror.graphic.bridge.document import (  # noqa: E402
    GraphicDocumentBackgroundResolver,
)
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager  # noqa: E402


def _png_bytes(color: QColor) -> bytes:
    image = QImage(80, 60, QImage.Format.Format_ARGB32)
    image.fill(color)
    buffer = QBuffer()
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    raw = bytes(buffer.data())
    buffer.close()
    return raw


def _png_base64(color: QColor) -> str:
    return base64.b64encode(_png_bytes(color)).decode("ascii")


def test_first_ipad_association_snapshots_original_raster(tmp_path: Path) -> None:
    image_path = tmp_path / "figure.png"
    original = _png_bytes(QColor("white"))
    image_path.write_bytes(original)

    sidecar = GraphicDocumentManager().ensure_for_image(image_path)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))

    assert payload["version"] >= 2
    assert payload["image_name"] == "figure.png"
    assert payload["background_is_authoritative"] is True
    assert base64.b64decode(payload["background_image_base64"]) == original
    assert payload["drawing_data_base64"] == ""


def test_authoritative_white_background_keeps_editable_strokes() -> None:
    resolver = GraphicDocumentBackgroundResolver()
    document = {
        "version": 2,
        "background_image_base64": _png_base64(QColor("white")),
        "background_is_authoritative": True,
        "drawing_data_base64": "pencilkit-vector-data",
        "image_objects": [{"id": "object"}],
    }

    resolved, recovered = resolver.resolve_for_open(
        document,
        _png_base64(QColor("black")),
    )

    assert recovered is False
    assert resolved["drawing_data_base64"] == "pencilkit-vector-data"
    assert resolved["image_objects"] == [{"id": "object"}]
    assert resolved["background_image_base64"] == document["background_image_base64"]


def test_move_rebinds_companion_to_new_raster_name(tmp_path: Path) -> None:
    source_image = tmp_path / "before.png"
    source_sidecar = tmp_path / "before.ndgraphic"
    destination_image = tmp_path / "after.png"
    destination_sidecar = tmp_path / "after.ndgraphic"

    source_image.write_bytes(b"image")
    source_sidecar.write_text(
        json.dumps(
            {
                "version": 2,
                "image_name": "before.png",
                "background_is_authoritative": True,
            }
        ),
        encoding="utf-8",
    )

    result = WorkspaceFilesystemOperationService().execute(
        {
            "moves": [
                {"source": str(source_image), "destination": str(destination_image)},
                {"source": str(source_sidecar), "destination": str(destination_sidecar)},
            ],
            "deletes": [],
        }
    )

    assert [entry["success"] for entry in result["moves"]] == [True, True]
    assert destination_image.is_file()
    assert destination_sidecar.is_file()
    payload = json.loads(destination_sidecar.read_text(encoding="utf-8"))
    assert payload["image_name"] == "after.png"
