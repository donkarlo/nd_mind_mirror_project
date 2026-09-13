// Deterministic layered layout for editable named-node TikZ graphs.

import CoreGraphics
import Foundation

final class TikZAutoLayoutService {
    func positions(for graph: TikZGraph) -> [String: CGPoint] {
        guard !graph.nodes.isEmpty else { return [:] }
        let names = graph.nodes.map(\.name).sorted()
        var outgoing: [String: [String]] = [:]
        var indegree = Dictionary(uniqueKeysWithValues: names.map { ($0, 0) })
        for edge in graph.edges where indegree[edge.source] != nil && indegree[edge.target] != nil {
            outgoing[edge.source, default: []].append(edge.target)
            indegree[edge.target, default: 0] += 1
        }

        var queue = names.filter { indegree[$0] == 0 }
        var layer: [String: Int] = Dictionary(uniqueKeysWithValues: queue.map { ($0, 0) })
        var visited: [String] = []
        while !queue.isEmpty {
            let current = queue.removeFirst()
            visited.append(current)
            for target in (outgoing[current] ?? []).sorted() {
                layer[target] = max(layer[target] ?? 0, (layer[current] ?? 0) + 1)
                indegree[target, default: 0] -= 1
                if indegree[target] == 0 { queue.append(target) }
            }
        }

        if visited.count != names.count {
            return circularPositions(names)
        }

        let maximumLayer = max(layer.values.max() ?? 0, 0)
        var grouped: [Int: [String]] = [:]
        for name in names { grouped[layer[name] ?? 0, default: []].append(name) }
        var result: [String: CGPoint] = [:]
        for level in 0...maximumLayer {
            let members = (grouped[level] ?? []).sorted()
            let y = maximumLayer == 0 ? 5.5 : 9.5 - (Double(level) / Double(maximumLayer)) * 8.0
            for (index, name) in members.enumerated() {
                let x = members.count == 1 ? 8.0 : 2.0 + Double(index) * (12.0 / Double(members.count - 1))
                result[name] = CGPoint(x: x, y: y)
            }
        }
        return result
    }

    private func circularPositions(_ names: [String]) -> [String: CGPoint] {
        guard names.count > 1 else { return [names[0]: CGPoint(x: 8, y: 5.5)] }
        var result: [String: CGPoint] = [:]
        for (index, name) in names.enumerated() {
            let angle = (Double(index) / Double(names.count)) * 2 * Double.pi - Double.pi / 2
            result[name] = CGPoint(x: 8 + 5.5 * cos(angle), y: 5.5 + 4.0 * sin(angle))
        }
        return result
    }
}
