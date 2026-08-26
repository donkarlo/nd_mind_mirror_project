import Foundation
import SwiftUI
import UIKit

/// One editable bitmap object positioned in logical canvas coordinates.
struct CanvasImageObject: Codable, Equatable, Identifiable {
    let id: UUID
    var imageDataBase64: String
    var x: Double
    var y: Double
    var width: Double
    var height: Double

    var frame: CGRect {
        get {
            CGRect(x: x, y: y, width: width, height: height)
        }
        set {
            let normalized = newValue.standardized
            x = normalized.origin.x
            y = normalized.origin.y
            width = normalized.size.width
            height = normalized.size.height
        }
    }

    var image: UIImage? {
        guard let data = Data(base64Encoded: imageDataBase64) else { return nil }
        return UIImage(data: data)
    }
}

/// Persists editable image objects separately from the Ubuntu/base background image.
enum CanvasImageObjectStore {
    private static let folderName = "NDGraphicImageObjects"

    static func load(documentIdentifier: String) -> [CanvasImageObject] {
        guard !documentIdentifier.isEmpty,
              let url = storageURL(documentIdentifier: documentIdentifier),
              let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode([CanvasImageObject].self, from: data) else {
            return []
        }
        return decoded.filter { object in
            object.width > 0 && object.height > 0 && object.image != nil
        }
    }

    static func save(_ objects: [CanvasImageObject], documentIdentifier: String) {
        guard !documentIdentifier.isEmpty,
              let url = storageURL(documentIdentifier: documentIdentifier) else { return }
        if objects.isEmpty {
            try? FileManager.default.removeItem(at: url)
            return
        }
        guard let data = try? JSONEncoder().encode(objects) else { return }
        try? data.write(to: url, options: .atomic)
    }

    static func clear(documentIdentifier: String) {
        guard !documentIdentifier.isEmpty,
              let url = storageURL(documentIdentifier: documentIdentifier) else { return }
        try? FileManager.default.removeItem(at: url)
    }

    private static func storageURL(documentIdentifier: String) -> URL? {
        guard let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            return nil
        }
        let folder = base.appendingPathComponent(folderName, isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        return folder.appendingPathComponent(stableHash(documentIdentifier) + ".json")
    }

    /// Deterministic FNV-1a hash so the same Ubuntu path maps to the same local object file across launches.
    private static func stableHash(_ value: String) -> String {
        var hash: UInt64 = 1469598103934665603
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash = hash &* 1099511628211
        }
        return String(format: "%016llx", hash)
    }
}

/// Owns image-object selection, persistence, and Undo/Redo on the same UndoManager as PencilKit.
@MainActor
final class CanvasImageObjectManager: ObservableObject {
    @Published private(set) var objects: [CanvasImageObject] = []
    @Published private(set) var selectedID: UUID?
    @Published private(set) var editRevision = 0

    weak var undoManager: UndoManager?
    private var documentIdentifier = ""

    func load(documentIdentifier: String, remoteObjects: [CanvasImageObject]? = nil) {
        self.documentIdentifier = documentIdentifier
        if let remoteObjects {
            objects = remoteObjects.filter { $0.width > 0 && $0.height > 0 && $0.image != nil }
            CanvasImageObjectStore.save(objects, documentIdentifier: documentIdentifier)
        } else {
            objects = CanvasImageObjectStore.load(documentIdentifier: documentIdentifier)
        }
        selectedID = nil
    }

    func beginNewDocument(documentIdentifier: String) {
        self.documentIdentifier = documentIdentifier
        CanvasImageObjectStore.clear(documentIdentifier: documentIdentifier)
        objects = []
        selectedID = nil
    }

    func setSelected(_ id: UUID?) {
        selectedID = id.flatMap { candidate in
            objects.contains(where: { $0.id == candidate }) ? candidate : nil
        }
    }

    @discardableResult
    func insert(image: UIImage, canvasSize: CGSize) -> UUID? {
        guard let data = image.pngData(), image.size.width > 0, image.size.height > 0 else { return nil }
        let maxDimension = max(
            48.0,
            min(600.0, canvasSize.width * 0.45, canvasSize.height * 0.45)
        )
        let naturalMax = max(image.size.width, image.size.height)
        let scale = min(1.0, maxDimension / max(naturalMax, 1.0))
        let size = CGSize(
            width: max(24.0, image.size.width * scale),
            height: max(24.0, image.size.height * scale)
        )
        let origin = CGPoint(
            x: min(20.0, max(canvasSize.width - size.width, 0)),
            y: min(20.0, max(canvasSize.height - size.height, 0))
        )
        let object = CanvasImageObject(
            id: UUID(),
            imageDataBase64: data.base64EncodedString(),
            x: origin.x,
            y: origin.y,
            width: min(size.width, max(canvasSize.width, 24.0)),
            height: min(size.height, max(canvasSize.height, 24.0))
        )
        var updated = objects
        updated.append(object)
        replaceObjects(updated, selectedID: object.id, actionName: "Insert Image", registerUndo: true)
        return object.id
    }

    func deleteSelected() {
        guard let selectedID,
              objects.contains(where: { $0.id == selectedID }) else { return }
        let updated = objects.filter { $0.id != selectedID }
        replaceObjects(updated, selectedID: nil, actionName: "Delete Image", registerUndo: true)
    }

    func commitFromCanvas(_ updated: [CanvasImageObject], selectedID: UUID?, actionName: String) {
        guard updated != objects || selectedID != self.selectedID else { return }
        replaceObjects(updated, selectedID: selectedID, actionName: actionName, registerUndo: true)
    }

    private func replaceObjects(
        _ updated: [CanvasImageObject],
        selectedID: UUID?,
        actionName: String,
        registerUndo: Bool
    ) {
        let previousObjects = objects
        let previousSelection = self.selectedID
        if registerUndo {
            undoManager?.registerUndo(withTarget: self) { target in
                target.restore(
                    objects: previousObjects,
                    selectedID: previousSelection,
                    actionName: actionName
                )
            }
            undoManager?.setActionName(actionName)
        }
        objects = updated
        self.selectedID = selectedID.flatMap { id in updated.contains(where: { $0.id == id }) ? id : nil }
        CanvasImageObjectStore.save(objects, documentIdentifier: documentIdentifier)
        editRevision &+= 1
    }

    private func restore(objects targetObjects: [CanvasImageObject], selectedID targetSelection: UUID?, actionName: String) {
        let currentObjects = objects
        let currentSelection = selectedID
        undoManager?.registerUndo(withTarget: self) { target in
            target.restore(
                objects: currentObjects,
                selectedID: currentSelection,
                actionName: actionName
            )
        }
        undoManager?.setActionName(actionName)
        objects = targetObjects
        selectedID = targetSelection.flatMap { id in targetObjects.contains(where: { $0.id == id }) ? id : nil }
        CanvasImageObjectStore.save(objects, documentIdentifier: documentIdentifier)
        editRevision &+= 1
    }
}
