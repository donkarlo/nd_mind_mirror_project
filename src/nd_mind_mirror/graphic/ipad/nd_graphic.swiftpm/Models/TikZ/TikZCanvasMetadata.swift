// Source-backed logical canvas metadata for the iPad TikZ editor.

import CoreGraphics
import Foundation

struct TikZCanvasMetadata {
    static let defaultSize = CGSize(width: 760, height: 980)
    private static let pattern = #"(?m)^%\s*nd_mind_mirror_canvas\s*:\s*(\d+)\s*x\s*(\d+)\s*$"#

    static func size(in source: String) -> CGSize {
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(
                in: source,
                range: NSRange(source.startIndex..., in: source)
              ),
              let widthRange = Range(match.range(at: 1), in: source),
              let heightRange = Range(match.range(at: 2), in: source),
              let width = Double(source[widthRange]),
              let height = Double(source[heightRange]) else {
            return defaultSize
        }
        return CGSize(width: max(width, 64), height: max(height, 64))
    }

    static func updating(source: String, size: CGSize) -> String {
        let width = max(Int(size.width.rounded()), 64)
        let height = max(Int(size.height.rounded()), 64)
        let marker = "% nd_mind_mirror_canvas: \(width)x\(height)"
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return marker + "\n" + source
        }
        let range = NSRange(source.startIndex..., in: source)
        if regex.firstMatch(in: source, range: range) != nil {
            return regex.stringByReplacingMatches(
                in: source,
                range: range,
                withTemplate: marker
            )
        }
        return marker + "\n" + source
    }
}
