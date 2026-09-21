// Allocate the same conservative ndNodeN names used by TikZSourceEditor.

import Foundation

struct TikZNodeNameAllocator {
    func nextName(in source: String) -> String {
        let pattern = #"\(ndNode([0-9]+)\)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return "ndNode1"
        }
        let nsSource = source as NSString
        let maximum = regex.matches(
            in: source,
            range: NSRange(location: 0, length: nsSource.length)
        ).compactMap { match -> Int? in
            guard match.numberOfRanges > 1 else { return nil }
            return Int(nsSource.substring(with: match.range(at: 1)))
        }.max() ?? 0
        return "ndNode\(maximum + 1)"
    }
}
