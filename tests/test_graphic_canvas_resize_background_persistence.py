import asyncio
import base64
import json
from pathlib import Path

from nd_mind_mirror.graphic.bridge.server_compat import PreservingGraphicBridgeServer


ROOT = Path(__file__).resolve().parents[1]
IPAD_BRIDGE_CLIENT = (
    ROOT
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClient.swift"
)


def _write_legacy_editable_graphic(tmp_path: Path) -> tuple[Path, Path]:
    image_path = tmp_path / "graphic.png"
    image_path.write_bytes(b"rendered-legacy-composite")

    sidecar = tmp_path / "graphic.ndgraphic"
    sidecar.write_text(
        json.dumps(
            {
                "version": 2,
                "image_name": image_path.name,
                "canvas_width": 760,
                "canvas_height": 600,
                "drawing_data_base64": "legacy-pencilkit-drawing",
                "image_objects": [
                    {"id": "shape-1", "kind": "image"},
                    {"id": "shape-2", "kind": "text"},
                ],
                "background_image_base64": "legacy-blank-background",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return sidecar, image_path


def test_canvas_resize_does_not_commit_inferred_composite_over_editable_layers(
    tmp_path: Path,
) -> None:
    sidecar, _image_path = _write_legacy_editable_graphic(tmp_path)
    server = PreservingGraphicBridgeServer(tmp_path)
    resolved = sidecar.resolve()
    server._inferred_background_sidecars.add(resolved)

    original = json.loads(sidecar.read_text(encoding="utf-8"))
    original_ids = [item["id"] for item in original["image_objects"]]
    original_drawing = original["drawing_data_base64"]
    original_background = original["background_image_base64"]

    sizes = [(760, 980), (760, 640), (760, 1040), (760, 600)]
    serialized_sizes: list[int] = []
    for revision, (width, height) in enumerate(sizes, start=1):
        asyncio.run(
            server._update_graphic(
                sidecar,
                {
                    "type": "update_graphic",
                    "path": sidecar.name,
                    "canvas_width": width,
                    "canvas_height": height,
                    "client_revision": revision,
                },
            )
        )
        saved = json.loads(sidecar.read_text(encoding="utf-8"))

        assert saved["drawing_data_base64"] == original_drawing
        assert saved["background_image_base64"] == original_background
        assert [item["id"] for item in saved["image_objects"]] == original_ids
        assert len(saved["image_objects"]) == len(original_ids)
        assert saved["canvas_width"] == width
        assert saved["canvas_height"] == height
        assert resolved in server._inferred_background_sidecars
        serialized_sizes.append(sidecar.stat().st_size)

    # Repeated metadata-only resizes must not accumulate another copy of the
    # editable content into the serialized document.
    assert max(serialized_sizes) - min(serialized_sizes) < 32


def test_full_save_can_commit_recovered_background_when_editable_layers_are_replaced(
    tmp_path: Path,
) -> None:
    sidecar, image_path = _write_legacy_editable_graphic(tmp_path)
    server = PreservingGraphicBridgeServer(tmp_path)
    resolved = sidecar.resolve()
    server._inferred_background_sidecars.add(resolved)

    replacement_objects = [{"id": "new-object", "kind": "text"}]
    asyncio.run(
        server._update_graphic(
            sidecar,
            {
                "type": "update_graphic",
                "path": sidecar.name,
                "drawing_data_base64": "replacement-pencilkit-drawing",
                "image_objects": replacement_objects,
                "canvas_width": 760,
                "canvas_height": 980,
                "client_revision": 1,
            },
        )
    )

    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    expected_background = base64.b64encode(image_path.read_bytes()).decode("ascii")

    assert saved["background_image_base64"] == expected_background
    assert saved["drawing_data_base64"] == "replacement-pencilkit-drawing"
    assert saved["image_objects"] == replacement_objects
    assert resolved not in server._inferred_background_sidecars


def test_ipad_canvas_size_save_remains_metadata_only() -> None:
    source = IPAD_BRIDGE_CLIENT.read_text(encoding="utf-8")
    start = source.index("func saveCanvasSize(logicalCanvasSize: CGSize)")
    end = source.index("\n    private func resolvedBackgroundImage", start)
    method = source[start:end]

    assert '"canvas_width": width' in method
    assert '"canvas_height": height' in method
    assert '"drawing_data_base64"' not in method
    assert '"png_base64"' not in method
    assert '"background_image_base64"' not in method
    assert '"image_objects"' not in method
