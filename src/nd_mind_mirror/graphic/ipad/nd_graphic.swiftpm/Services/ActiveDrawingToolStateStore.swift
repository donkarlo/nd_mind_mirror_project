import Foundation

/// Persists the currently selected drawing tool and its appearance across app launches and upgrades.
final class ActiveDrawingToolStateStore {
    struct Value {
        let kind: GraphicTool
        let colorHex: String
        let width: Double
        let opacity: Double
        let eraserMode: EraserMode
        let selectedSavedToolID: UUID?
    }

    private struct Payload: Codable {
        let kindRawValue: String
        let colorHex: String
        let width: Double
        let opacity: Double
        let eraserModeRawValue: String
        let selectedSavedToolID: UUID?
    }

    private let defaults: UserDefaults
    private let storageKey = "graphic.active.drawing.tool.v1"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func load() -> Value {
        guard let data = defaults.data(forKey: storageKey),
              let payload = try? JSONDecoder().decode(Payload.self, from: data) else {
            return Value(
                kind: .lasso,
                colorHex: "#000000",
                width: 1.5,
                opacity: 1.0,
                eraserMode: .whole,
                selectedSavedToolID: nil
            )
        }
        return Value(
            kind: GraphicTool(rawValue: payload.kindRawValue) ?? .lasso,
            colorHex: payload.colorHex,
            width: payload.width,
            opacity: payload.opacity,
            eraserMode: EraserMode(rawValue: payload.eraserModeRawValue) ?? .whole,
            selectedSavedToolID: payload.selectedSavedToolID
        )
    }

    func save(
        kind: GraphicTool,
        colorHex: String,
        width: Double,
        opacity: Double,
        eraserMode: EraserMode,
        selectedSavedToolID: UUID?
    ) {
        let payload = Payload(
            kindRawValue: kind.rawValue,
            colorHex: colorHex,
            width: width,
            opacity: opacity,
            eraserModeRawValue: eraserMode.rawValue,
            selectedSavedToolID: selectedSavedToolID
        )
        guard let data = try? JSONEncoder().encode(payload) else { return }
        defaults.set(data, forKey: storageKey)
    }
}
