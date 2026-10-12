// Compact graph layouts based on actual node dimensions, never canvas width.

import CoreGraphics
import Foundation

final class TikZAutoLayoutService {
    private let horizontalGap: Double = 0.75
    private let verticalGap: Double = 0.65

    func positions(
        for graph: TikZGraph,
        direction: TikZAutoLayoutDirection = .topToBottom
    ) -> [String: CGPoint] {
        guard !graph.nodes.isEmpty else { return [:] }
        let names = graph.nodes.map(\.name).sorted()
        let groups = layerGroups(graph: graph, names: names)
        guard let groups else {
            return circularPositions(for: graph.nodes)
        }

        let horizontalDirections: Set<TikZAutoLayoutDirection> = [
            .leftToRight, .rightToLeft, .rightTree, .leftTree
        ]
        let horizontal = horizontalDirections.contains(direction)
        let forward = direction == .leftToRight
            || direction == .rightTree
            || direction == .bottomToTop
        let byName = Dictionary(uniqueKeysWithValues: graph.nodes.map { ($0.name, $0) })
        let levels = groups.keys.sorted()
        let primarySizes: [Double] = levels.map { level in
            (groups[level] ?? []).compactMap { byName[$0] }
                .map { horizontal ? max($0.width, 0.2) : max($0.height, 0.2) }
                .max() ?? 1
        }
        let primaryGap = horizontal ? horizontalGap : verticalGap
        let totalPrimary = primarySizes.reduce(0, +)
            + Double(max(levels.count - 1, 0)) * primaryGap
        let mainCenter = horizontal ? 8.0 : 5.5
        let crossCenter = horizontal ? 5.5 : 8.0
        var primaryCursor = -totalPrimary / 2
        var result: [String: CGPoint] = [:]

        for (index, level) in levels.enumerated() {
            let primarySize = primarySizes[index]
            let primary = mainCenter
                + (forward ? 1.0 : -1.0)
                * (primaryCursor + primarySize / 2)

            let members = (groups[level] ?? []).sorted()
            let crossSizes: [Double] = members.map { name in
                guard let node = byName[name] else { return 1 }
                return horizontal ? max(node.height, 0.2) : max(node.width, 0.2)
            }
            let crossGap = horizontal ? verticalGap : horizontalGap
            let crossTotal = crossSizes.reduce(0, +)
                + Double(max(members.count - 1, 0)) * crossGap
            var crossCursor = -crossTotal / 2

            for (memberIndex, name) in members.enumerated() {
                let cross = crossCenter + crossCursor + crossSizes[memberIndex] / 2
                // Vertical layers are ordered in view coordinates, hence inverted
                // on TikZ's upward-positive Y axis.
                result[name] = horizontal
                    ? CGPoint(x: primary, y: crossCenter * 2 - cross)
                    : CGPoint(x: cross, y: primary)
                crossCursor += crossSizes[memberIndex] + crossGap
            }
            primaryCursor += primarySize + primaryGap
        }
        return result
    }

    private func layerGroups(
        graph: TikZGraph,
        names: [String]
    ) -> [Int: [String]]? {
        var indegree = Dictionary(uniqueKeysWithValues: names.map { ($0, 0) })
        var adjacency: [String: [String]] = [:]
        for edge in graph.edges
        where indegree[edge.source] != nil && indegree[edge.target] != nil {
            indegree[edge.target, default: 0] += 1
            adjacency[edge.source, default: []].append(edge.target)
        }

        var queue = names.filter { indegree[$0] == 0 }
        var layers = Dictionary(uniqueKeysWithValues: queue.map { ($0, 0) })
        var visited = 0
        while !queue.isEmpty {
            let name = queue.removeFirst()
            visited += 1
            for target in (adjacency[name] ?? []).sorted() {
                layers[target] = max(layers[target] ?? 0, (layers[name] ?? 0) + 1)
                indegree[target, default: 0] -= 1
                if indegree[target] == 0 { queue.append(target) }
            }
        }

        guard visited == names.count else { return nil }
        var groups: [Int: [String]] = [:]
        for name in names {
            groups[layers[name] ?? 0, default: []].append(name)
        }
        return groups
    }

    private func circularPositions(for nodes: [TikZNode]) -> [String: CGPoint] {
        let ordered = nodes.sorted { $0.name < $1.name }
        guard ordered.count > 1 else {
            return [ordered[0].name: CGPoint(x: 8, y: 5.5)]
        }
        let largest = ordered.map { max($0.width, $0.height) }.max() ?? 1
        let circumference = Double(ordered.count) * (largest + horizontalGap)
        let radius = circumference / (2 * Double.pi)
        var result: [String: CGPoint] = [:]
        for (index, node) in ordered.enumerated() {
            let angle = Double(index) * 2 * Double.pi / Double(ordered.count)
                - Double.pi / 2
            result[node.name] = CGPoint(
                x: 8 + radius * cos(angle),
                y: 5.5 + radius * sin(angle)
            )
        }
        return result
    }
}
