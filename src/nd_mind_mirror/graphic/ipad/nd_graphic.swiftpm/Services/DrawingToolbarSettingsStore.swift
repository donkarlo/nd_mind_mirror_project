import Foundation
import SwiftUI

/// Persists drawing-toolbar visibility and one shared item order for both iPad tool palettes.
@MainActor
final class DrawingToolbarSettingsStore: ObservableObject {
    @Published private(set) var isToolbarVisible: Bool
    @Published private(set) var orderedItemIDs: [String]

    private enum Keys {
        static let visible = "graphic.drawing.toolbar.visible"
        static let order = "graphic.drawing.toolbar.order.v1"
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if defaults.object(forKey: Keys.visible) == nil {
            isToolbarVisible = true
        } else {
            isToolbarVisible = defaults.bool(forKey: Keys.visible)
        }

        if let data = defaults.data(forKey: Keys.order),
           let decoded = try? JSONDecoder().decode([String].self, from: data) {
            orderedItemIDs = decoded
        } else {
            orderedItemIDs = []
        }
    }

    func setToolbarVisible(_ visible: Bool) {
        guard visible != isToolbarVisible else { return }
        isToolbarVisible = visible
        defaults.set(visible, forKey: Keys.visible)
    }

    func reconcile(with savedTools: [SavedDrawingTool]) {
        let validIDs = Self.defaultIDs(for: savedTools)
        let validSet = Set(validIDs)
        var next = orderedItemIDs.filter { validSet.contains($0) }

        if next.isEmpty {
            next = validIDs
        } else {
            for id in validIDs where !next.contains(id) {
                if id == DrawingToolbarItem.lasso.id || id == DrawingToolbarItem.addImage.id {
                    next.append(id)
                } else {
                    let specialIndex = next.firstIndex {
                        $0 == DrawingToolbarItem.lasso.id
                            || $0 == DrawingToolbarItem.addImage.id
                    } ?? next.endIndex
                    next.insert(id, at: specialIndex)
                }
            }
        }

        setOrder(next)
    }

    func items(for savedTools: [SavedDrawingTool]) -> [DrawingToolbarItem] {
        let availableSavedIDs = Set(savedTools.map(\.id))
        let current = orderedItemIDs.isEmpty
            ? Self.defaultIDs(for: savedTools)
            : orderedItemIDs

        return current.compactMap { storageID in
            guard let item = DrawingToolbarItem.from(storageID: storageID) else {
                return nil
            }
            if case .savedTool(let id) = item, !availableSavedIDs.contains(id) {
                return nil
            }
            return item
        }
    }

    func move(
        fromOffsets: IndexSet,
        toOffset: Int,
        savedTools: [SavedDrawingTool]
    ) {
        var ids = items(for: savedTools).map(\.id)
        ids.move(fromOffsets: fromOffsets, toOffset: toOffset)
        setOrder(ids)
    }

    func insertSavedTool(_ id: UUID, after existingID: UUID?) {
        let newID = DrawingToolbarItem.savedTool(id).id
        guard !orderedItemIDs.contains(newID) else { return }

        var next = orderedItemIDs
        if let existingID {
            let anchorID = DrawingToolbarItem.savedTool(existingID).id
            if let index = next.firstIndex(of: anchorID) {
                next.insert(newID, at: index + 1)
                setOrder(next)
                return
            }
        }

        let specialIndex = next.firstIndex {
            $0 == DrawingToolbarItem.lasso.id
                || $0 == DrawingToolbarItem.addImage.id
        } ?? next.endIndex
        next.insert(newID, at: specialIndex)
        setOrder(next)
    }

    func removeSavedTool(_ id: UUID) {
        let target = DrawingToolbarItem.savedTool(id).id
        setOrder(orderedItemIDs.filter { $0 != target })
    }

    private func setOrder(_ ids: [String]) {
        guard ids != orderedItemIDs else { return }
        orderedItemIDs = ids
        if let data = try? JSONEncoder().encode(ids) {
            defaults.set(data, forKey: Keys.order)
        }
    }

    private static func defaultIDs(for savedTools: [SavedDrawingTool]) -> [String] {
        savedTools.map { DrawingToolbarItem.savedTool($0.id).id }
            + [DrawingToolbarItem.lasso.id, DrawingToolbarItem.addImage.id]
    }
}
