from __future__ import annotations

import base64

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from nd_mind_mirror.graphic.bridge.document import GraphicDocumentBackgroundResolver


def _png_base64(image: QImage) -> str:
    buffer = QBuffer()
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
    buffer.close()
    return encoded


def _solid_image(color: QColor) -> QImage:
    image = QImage(200, 200, QImage.Format.Format_ARGB32)
    image.fill(color)
    return image


def test_recovers_informative_paired_png_when_legacy_background_is_white() -> None:
    resolver = GraphicDocumentBackgroundResolver()
    white_background = _solid_image(QColor("white"))
    informative_image = _solid_image(QColor("black"))
    paired_base64 = _png_base64(informative_image)
    document = {
        "background_image_base64": _png_base64(white_background),
        "drawing_data_base64": "legacy-drawing",
        "image_objects": [{"id": "legacy-object"}],
    }

    resolved, recovered = resolver.resolve_for_open(document, paired_base64)

    assert recovered is True
    assert resolved["background_image_base64"] == paired_base64
    assert resolved["drawing_data_base64"] == ""
    assert resolved["image_objects"] == []
    assert document["drawing_data_base64"] == "legacy-drawing"


def test_keeps_informative_stored_background() -> None:
    resolver = GraphicDocumentBackgroundResolver()
    stored_base64 = _png_base64(_solid_image(QColor("black")))
    paired_base64 = _png_base64(_solid_image(QColor("red")))
    document = {
        "background_image_base64": stored_base64,
        "drawing_data_base64": "legacy-drawing",
    }

    resolved, recovered = resolver.resolve_for_open(document, paired_base64)

    assert recovered is False
    assert resolved == document


def test_recovers_when_legacy_background_is_fully_transparent() -> None:
    resolver = GraphicDocumentBackgroundResolver()
    transparent_background = _solid_image(QColor(0, 0, 0, 0))
    paired_base64 = _png_base64(_solid_image(QColor("black")))
    document = {
        "background_image_base64": _png_base64(transparent_background),
        "drawing_data_base64": "legacy-drawing",
    }

    resolved, recovered = resolver.resolve_for_open(document, paired_base64)

    assert recovered is True
    assert resolved["background_image_base64"] == paired_base64
    assert resolved["drawing_data_base64"] == ""
