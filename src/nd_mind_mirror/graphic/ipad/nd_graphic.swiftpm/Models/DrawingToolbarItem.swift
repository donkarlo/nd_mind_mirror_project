import Foundation

/// One shared item shown by both the persistent drawing toolbar and the Pencil quick palette.
enum DrawingToolbarItem: Hashable, Identifiable {
    case savedTool(UUID)
    case lasso
    case addImage

    var id: String {
        switch self {
        case .savedTool(let id):
            return "saved:\(id.uuidString.lowercased())"
        case .lasso:
            return "lasso"
        case .addImage:
            return "add-image"
        }
    }

    static func from(storageID: String) -> DrawingToolbarItem? {
        if storageID == "lasso" {
            return .lasso
        }
        if storageID == "add-image" {
            return .addImage
        }
        let prefix = "saved:"
        guard storageID.hasPrefix(prefix) else { return nil }
        let uuidText = String(storageID.dropFirst(prefix.count))
        guard let id = UUID(uuidString: uuidText) else { return nil }
        return .savedTool(id)
    }
}
