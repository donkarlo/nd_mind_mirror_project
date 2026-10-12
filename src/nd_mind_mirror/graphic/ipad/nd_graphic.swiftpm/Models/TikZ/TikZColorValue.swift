// Arbitrary RGB color used by the TikZ canvas and native SwiftUI ColorPicker.

import SwiftUI
import UIKit

struct TikZColorValue: Hashable, Codable {
    var red: Double
    var green: Double
    var blue: Double
    var alpha: Double = 1.0

    static let black = TikZColorValue(red: 0, green: 0, blue: 0)
    static let white = TikZColorValue(red: 1, green: 1, blue: 1)

    var color: Color {
        Color(.sRGB, red: red, green: green, blue: blue, opacity: alpha)
    }

    var tikzValue: String {
        let r = Int((clamped(red) * 255).rounded())
        let g = Int((clamped(green) * 255).rounded())
        let b = Int((clamped(blue) * 255).rounded())
        return "{rgb,255:red,\(r);green,\(g);blue,\(b)}"
    }

    init(red: Double, green: Double, blue: Double, alpha: Double = 1.0) {
        self.red = Self.clamped(red)
        self.green = Self.clamped(green)
        self.blue = Self.clamped(blue)
        self.alpha = Self.clamped(alpha)
    }

    init(color: Color) {
        let uiColor = UIColor(color)
        var r: CGFloat = 0
        var g: CGFloat = 0
        var b: CGFloat = 0
        var a: CGFloat = 1
        if uiColor.getRed(&r, green: &g, blue: &b, alpha: &a) {
            self.init(red: Double(r), green: Double(g), blue: Double(b), alpha: Double(a))
            return
        }
        var white: CGFloat = 0
        if uiColor.getWhite(&white, alpha: &a) {
            self.init(red: Double(white), green: Double(white), blue: Double(white), alpha: Double(a))
            return
        }
        self = .black
    }

    static func fromTikZ(_ raw: String?) -> TikZColorValue? {
        guard var value = raw?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else { return nil }
        if value.hasPrefix("{") && value.hasSuffix("}") {
            value.removeFirst()
            value.removeLast()
        }
        switch value.lowercased() {
        case "black": return .black
        case "white": return .white
        case "red": return TikZColorValue(red: 1, green: 0, blue: 0)
        case "green": return TikZColorValue(red: 0, green: 0.5, blue: 0)
        case "blue": return TikZColorValue(red: 0, green: 0, blue: 1)
        case "gray", "grey": return TikZColorValue(red: 0.5, green: 0.5, blue: 0.5)
        case "orange": return TikZColorValue(red: 1, green: 0.5, blue: 0)
        case "yellow": return TikZColorValue(red: 1, green: 1, blue: 0)
        case "purple", "violet": return TikZColorValue(red: 0.5, green: 0, blue: 0.7)
        default: break
        }

        let lower = value.lowercased()
        guard lower.hasPrefix("rgb,255:") else { return nil }
        let body = String(value.dropFirst("rgb,255:".count))
        var components: [String: Double] = [:]
        for field in body.split(separator: ";") {
            let pieces = field.split(separator: ",", maxSplits: 1)
            guard pieces.count == 2, let number = Double(pieces[1]) else { continue }
            components[String(pieces[0]).lowercased()] = number / 255.0
        }
        guard let r = components["red"],
              let g = components["green"],
              let b = components["blue"] else { return nil }
        return TikZColorValue(red: r, green: g, blue: b)
    }

    private static func clamped(_ value: Double) -> Double {
        min(max(value, 0), 1)
    }

    private func clamped(_ value: Double) -> Double {
        Self.clamped(value)
    }
}
