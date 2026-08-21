import SwiftUI

/// Persists the most recently used pencil colors across ND Graphic launches.
///
/// A color is remembered when a drawing is saved (that is, when it was
/// actually used for a stroke) or when the user taps one of the recent-color
/// swatches. Duplicate colors are moved to the front and only the ten most
/// recent entries are retained.
@MainActor
final class RecentPencilColors: ObservableObject {
    @Published private(set) var hexColors: [String]

    private let defaultsKey = "graphic.pencil.recentColors"
    private let maximumCount = 10

    init() {
        let stored = UserDefaults.standard.stringArray(forKey: defaultsKey) ?? []
        var seen = Set<String>()
        hexColors = stored.compactMap { raw in
            let normalized = Self.normalize(raw)
            guard !normalized.isEmpty, seen.insert(normalized).inserted else { return nil }
            return normalized
        }
        if hexColors.count > maximumCount {
            hexColors = Array(hexColors.prefix(maximumCount))
        }
    }

    func remember(_ color: Color) {
        remember(hex: color.hexRGB())
    }

    func remember(hex: String) {
        let normalized = Self.normalize(hex)
        guard !normalized.isEmpty else { return }
        hexColors.removeAll { $0.caseInsensitiveCompare(normalized) == .orderedSame }
        hexColors.insert(normalized, at: 0)
        if hexColors.count > maximumCount {
            hexColors.removeLast(hexColors.count - maximumCount)
        }
        UserDefaults.standard.set(hexColors, forKey: defaultsKey)
    }

    private static func normalize(_ raw: String) -> String {
        let cleaned = raw.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        guard cleaned.count == 6, UInt64(cleaned, radix: 16) != nil else { return "" }
        return "#" + cleaned.uppercased()
    }
}
