"""PencilCanvas, bridge payload, and image-object source patch."""
from __future__ import annotations
from pathlib import Path

class IpadDynamicCanvasPatch:
    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = self._patch_pencil_canvas()
        changed |= self._patch_graphic_message()
        changed |= self._patch_bridge_rendering()
        changed |= self._patch_pencil_settings()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    def _patch_pencil_canvas(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        if "let opacity: Double" not in text:
            text = text.replace(
                "    let color: Color\n    let width: Double\n    let logicalCanvasSize: CGSize\n",
                "    let color: Color\n    let width: Double\n    let opacity: Double\n    let imageObjects: [CanvasImageObject]\n    let selectedImageObjectID: UUID?\n    let logicalCanvasSize: CGSize\n",
                1,
            )
        if "let onImageObjectSelectionChanged" not in text:
            text = text.replace(
                "    let onZoomChanged: (CGFloat) -> Void\n",
                "    let onZoomChanged: (CGFloat) -> Void\n    let onImageObjectSelectionChanged: (UUID?) -> Void\n    let onImageObjectsCommitted: ([CanvasImageObject], UUID?, String) -> Void\n",
                1,
            )

        if "ND_CANVAS_IMAGE_LAYER_V1" not in text:
            anchor = "        content.addSubview(background)\n\n"
            insertion = '''        // ND_CANVAS_IMAGE_LAYER_V1
        let imageObjectLayer = CanvasImageObjectLayerView(frame: content.bounds)
        imageObjectLayer.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        imageObjectLayer.setObjects(imageObjects)
        content.addSubview(imageObjectLayer)

'''
            text = text.replace(anchor, anchor + insertion, 1)

        if "ND_CANVAS_IMAGE_INTERACTION_V1" not in text:
            anchor = "        let selectionOverlay = SelectionResizeOverlay(frame: content.bounds)\n"
            insertion = '''        // ND_CANVAS_IMAGE_INTERACTION_V1
        let imageObjectInteraction = CanvasImageObjectInteractionView(frame: content.bounds)
        imageObjectInteraction.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        imageObjectInteraction.onSelectionChanged = { id in
            context.coordinator.clearSelection()
            context.coordinator.onImageObjectSelectionChanged(id)
        }
        imageObjectInteraction.onPreviewObjectsChanged = { objects in
            imageObjectLayer.setObjects(objects)
        }
        imageObjectInteraction.onCommit = { objects, selectedID, actionName in
            context.coordinator.onImageObjectsCommitted(objects, selectedID, actionName)
        }
        imageObjectInteraction.setState(
            objects: imageObjects,
            selectedID: selectedImageObjectID,
            selectionEnabled: tool == .lasso,
            zoomScale: 1.0
        )
        content.addSubview(imageObjectInteraction)

'''
            text = text.replace(anchor, insertion + anchor, 1)

        if "context.coordinator.imageObjectLayer" not in text:
            anchor = "        context.coordinator.backgroundView = background\n"
            text = text.replace(
                anchor,
                anchor
                + "        context.coordinator.imageObjectLayer = imageObjectLayer\n"
                + "        context.coordinator.imageObjectInteractionView = imageObjectInteraction\n"
                + "        context.coordinator.onImageObjectSelectionChanged = onImageObjectSelectionChanged\n"
                + "        context.coordinator.onImageObjectsCommitted = onImageObjectsCommitted\n",
                1,
            )

        if "coordinator.imageObjectLayer?.setObjects(imageObjects)" not in text:
            anchor = "        coordinator.onZoomChanged = onZoomChanged\n"
            insertion = '''        coordinator.onImageObjectSelectionChanged = onImageObjectSelectionChanged
        coordinator.onImageObjectsCommitted = onImageObjectsCommitted
        coordinator.imageObjectLayer?.setObjects(imageObjects)
        coordinator.imageObjectInteractionView?.setState(
            objects: imageObjects,
            selectedID: selectedImageObjectID,
            selectionEnabled: tool == .lasso,
            zoomScale: scroll.zoomScale
        )
'''
            text = text.replace(anchor, anchor + insertion, 1)

        text = text.replace(
            "            coordinator.backgroundView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n",
            "            coordinator.backgroundView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n            coordinator.imageObjectLayer?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n            coordinator.imageObjectInteractionView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n",
            1,
        )

        text = text.replace(
            '''            if tool != .lasso {
                coordinator.clearSelection()
            }
''',
            '''            if tool != .lasso {
                coordinator.clearSelection()
                coordinator.imageObjectInteractionView?.clearSelection(notify: true)
            }
''',
            1,
        )

        pencil_block = '''        case .pencil:
            canvas.tool = PKInkingTool(.pencil, color: UIColor(color), width: CGFloat(max(1.0, width)))
        case .highlighter:
            canvas.tool = PKInkingTool(
                .marker,
                color: UIColor(color).withAlphaComponent(0.34),
                width: CGFloat(max(10.0, width * 2.6))
            )
'''
        dynamic_ink = '''        case .pencil:
            canvas.tool = PKInkingTool(
                .pencil,
                color: UIColor(color).withAlphaComponent(CGFloat(min(max(opacity, 0.05), 1.0))),
                width: CGFloat(max(0.5, width))
            )
        case .highlighter:
            canvas.tool = PKInkingTool(
                .marker,
                color: UIColor(color).withAlphaComponent(CGFloat(min(max(opacity, 0.05), 1.0))),
                width: CGFloat(max(0.5, width))
            )
'''
        text = text.replace(pencil_block, dynamic_ink, 1)

        if "weak var imageObjectLayer" not in text:
            anchor = "        weak var backgroundView: UIImageView?\n"
            insertion = '''        weak var imageObjectLayer: CanvasImageObjectLayerView?
        weak var imageObjectInteractionView: CanvasImageObjectInteractionView?
'''
            text = text.replace(anchor, anchor + insertion, 1)
        if "var onImageObjectSelectionChanged" not in text:
            anchor = "        var onZoomChanged: (CGFloat) -> Void\n"
            insertion = '''        var onImageObjectSelectionChanged: (UUID?) -> Void = { _ in }
        var onImageObjectsCommitted: ([CanvasImageObject], UUID?, String) -> Void = { _, _, _ in }
'''
            text = text.replace(anchor, anchor + insertion, 1)

        text = text.replace(
            '''            case .began:
                lassoPoints = [recognizer.location(in: canvas)]
''',
            '''            case .began:
                imageObjectInteractionView?.clearSelection(notify: true)
                lassoPoints = [recognizer.location(in: canvas)]
''',
            1,
        )
        text = text.replace(
            '''            selectedStrokeIndices = selected
            refreshSelectionBounds()
''',
            '''            selectedStrokeIndices = selected
            refreshSelectionBounds()
            if selected.isEmpty {
                imageObjectInteractionView?.selectObject(inLasso: polygon)
            }
''',
            1,
        )
        text = text.replace(
            '''        func scrollViewDidZoom(_ scrollView: UIScrollView) {
            centerCanvas()
            selectionOverlay?.updateZoom(scrollView.zoomScale)
            reportZoom()
        }
''',
            '''        func scrollViewDidZoom(_ scrollView: UIScrollView) {
            centerCanvas()
            selectionOverlay?.updateZoom(scrollView.zoomScale)
            imageObjectInteractionView?.updateZoom(scrollView.zoomScale)
            reportZoom()
        }
''',
            1,
        )
        return self._write_if_changed(path, original, text)

    def _patch_graphic_message(self) -> bool:
        path = self.source_root / "Models" / "GraphicMessage.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original
        if "var imageObjects: [CanvasImageObject]?" not in text:
            text = text.replace(
                "    var backgroundImageBase64: String?\n    var pencil: PencilPayload?\n",
                "    var backgroundImageBase64: String?\n    var imageObjects: [CanvasImageObject]?\n    var pencil: PencilPayload?\n",
                1,
            )
            text = text.replace(
                "        case backgroundImageBase64 = \"background_image_base64\"\n        case pencil\n",
                "        case backgroundImageBase64 = \"background_image_base64\"\n        case imageObjects = \"image_objects\"\n        case pencil\n",
                1,
            )
        return self._write_if_changed(path, original, text)

    def _patch_bridge_rendering(self) -> bool:
        path = self.source_root / "Services" / "GraphicBridgeClient.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original
        if "let imageObjects = CanvasImageObjectStore.load(documentIdentifier: path)" not in text:
            text = text.replace(
                '''        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize
        ) else {
''',
                '''        let imageObjects = CanvasImageObjectStore.load(documentIdentifier: path)
        guard let png = GraphicImageRenderer.pngData(
            drawing: drawing,
            backgroundImage: backgroundImage,
            imageObjects: imageObjects,
            logicalCanvasSize: logicalCanvasSize
        ) else {
''',
                1,
            )
        if 'payload["image_objects"]' not in text:
            anchor = '''        if persistBackground {
            payload["background_image_base64"] = backgroundImage?.pngData()?.base64EncodedString() ?? ""
        }
'''
            insertion = '''        if let objectData = try? JSONEncoder().encode(imageObjects),
           let objectJSON = try? JSONSerialization.jsonObject(with: objectData) {
            payload["image_objects"] = objectJSON
        }

'''
            text = text.replace(anchor, insertion + anchor, 1)
        return self._write_if_changed(path, original, text)

    def _patch_pencil_settings(self) -> bool:
        path = self.source_root / "Services" / "PencilSettings.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original.replace(
            "self.width = min(max(resolvedWidth, 1.0), 24.0)",
            "self.width = min(max(resolvedWidth, 0.5), 60.0)",
        )
        return self._write_if_changed(path, original, text)
