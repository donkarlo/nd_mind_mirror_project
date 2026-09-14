// Preserve unknown TikZ options while editing the visual editor's supported style subset.

import Foundation

struct TikZOptionList {
    private(set) var items: [String]

    init(_ raw: String) {
        items = Self.splitTopLevel(raw)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    func containsFlag(_ flag: String) -> Bool {
        let wanted = Self.normalized(flag)
        return items.contains { Self.normalized($0) == wanted }
    }

    func value(for key: String) -> String? {
        let wanted = Self.normalized(key)
        for item in items {
            guard let equal = item.firstIndex(of: "=") else { continue }
            let itemKey = Self.normalized(String(item[..<equal]))
            guard itemKey == wanted else { continue }
            return String(item[item.index(after: equal)...])
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return nil
    }

    mutating func setValue(_ value: String, for key: String) {
        removeKey(key)
        items.append("\(key)=\(value)")
    }

    mutating func setFlag(_ flag: String, enabled: Bool) {
        let wanted = Self.normalized(flag)
        items.removeAll { Self.normalized($0) == wanted }
        if enabled {
            items.append(flag)
        }
    }

    mutating func removeKey(_ key: String) {
        let wanted = Self.normalized(key)
        items.removeAll { item in
            if Self.normalized(item) == wanted { return true }
            guard let equal = item.firstIndex(of: "=") else { return false }
            return Self.normalized(String(item[..<equal])) == wanted
        }
    }

    var serialized: String {
        items.joined(separator: ", ")
    }

    private static func normalized(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    private static func splitTopLevel(_ raw: String) -> [String] {
        var result: [String] = []
        var current = ""
        var braceDepth = 0
        var bracketDepth = 0

        for character in raw {
            switch character {
            case "{": braceDepth += 1
            case "}": braceDepth = max(0, braceDepth - 1)
            case "[": bracketDepth += 1
            case "]": bracketDepth = max(0, bracketDepth - 1)
            case "," where braceDepth == 0 && bracketDepth == 0:
                result.append(current)
                current = ""
                continue
            default:
                break
            }
            current.append(character)
        }
        result.append(current)
        return result
    }
}
