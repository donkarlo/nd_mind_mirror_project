// Persists the last selected stroke color and width for the iPad drawing toolbar.

import Foundation
import SwiftUI

/// Stores the current stroke appearance and writes every user change to UserDefaults.
struct PencilSettings: Equatable {
    private static let widthKey = "graphic.stroke.lastWidth"
    private static let colorKey = "graphic.stroke.lastColor"

    var width: Double {
        didSet {
            UserDefaults.standard.set(width, forKey: Self.widthKey)
        }
    }

    var color: Color {
        didSet {
            UserDefaults.standard.set(color.hexRGB(), forKey: Self.colorKey)
        }
    }

    /// Loads the last persisted stroke settings while preserving optional explicit values from callers.
    init(width: Double? = nil, color: Color? = nil) {
        let storedWidth = UserDefaults.standard.double(forKey: Self.widthKey)
        let resolvedWidth = width ?? (storedWidth > 0 ? storedWidth : 6.0)
        self.width = min(max(resolvedWidth, 1.0), 24.0)

        if let color {
            self.color = color
        } else if let storedHex = UserDefaults.standard.string(forKey: Self.colorKey), !storedHex.isEmpty {
            self.color = Color(hex: storedHex)
        } else {
            self.color = Color(red: 0.12, green: 0.12, blue: 0.12)
        }
    }
}
