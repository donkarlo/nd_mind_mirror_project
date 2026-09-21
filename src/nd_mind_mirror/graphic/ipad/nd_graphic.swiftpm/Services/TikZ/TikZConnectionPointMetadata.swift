// Persist per-node connection-point counts as compile-safe TikZ comments.

import Foundation

enum TikZConnectionPointMetadata {
    private static let prefix = "% nd-connection-points "
    static let defaultCount = 4

    static func counts(
        in source: String,
        nodeNames: [String]
    ) -> [String: Int] {
        Dictionary(
            uniqueKeysWithValues: nodeNames.map {
                ($0, count(for: $0, in: source))
            }
        )
    }

    static func count(
        for nodeName: String,
        in source: String
    ) -> Int {
        let escaped = NSRegularExpression.escapedPattern(for: nodeName)
        let pattern = #"(?m)^[ \t]*% nd-connection-points\s+"#
            + escaped
            + #"\s*=\s*([0-9]+)\s*$"#
        guard
            let regex = try? NSRegularExpression(pattern: pattern),
            let match = regex.firstMatch(
                in: source,
                range: NSRange(
                    location: 0,
                    length: (source as NSString).length
                )
            ),
            match.numberOfRanges == 2,
            let value = Int(
                (source as NSString).substring(with: match.range(at: 1))
            )
        else {
            return defaultCount
        }
        return max(value, defaultCount)
    }

    static func updating(
        nodeName: String,
        count: Int,
        in source: String
    ) -> String {
        let normalized = max(count, defaultCount)
        let line = "\(prefix)\(nodeName)=\(normalized)"
        let escaped = NSRegularExpression.escapedPattern(for: nodeName)
        let pattern = #"(?m)^[ \t]*% nd-connection-points\s+"#
            + escaped
            + #"\s*=\s*[0-9]+\s*$"#

        if
            let regex = try? NSRegularExpression(pattern: pattern),
            regex.firstMatch(
                in: source,
                range: NSRange(location: 0, length: (source as NSString).length)
            ) != nil
        {
            return regex.stringByReplacingMatches(
                in: source,
                range: NSRange(location: 0, length: (source as NSString).length),
                withTemplate: line
            )
        }

        let end = "\\end{tikzpicture}"
        guard let range = source.range(of: end, options: .backwards) else {
            return source + (source.hasSuffix("\n") ? "" : "\n") + line + "\n"
        }
        var result = source
        result.insert(contentsOf: "    \(line)\n", at: range.lowerBound)
        return result
    }

    static func removing(
        nodeName: String,
        from source: String
    ) -> String {
        let escaped = NSRegularExpression.escapedPattern(for: nodeName)
        let pattern = #"(?m)^[ \t]*% nd-connection-points\s+"#
            + escaped
            + #"\s*=\s*[0-9]+\s*\n?"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return source
        }
        return regex.stringByReplacingMatches(
            in: source,
            range: NSRange(location: 0, length: (source as NSString).length),
            withTemplate: ""
        )
    }
}
