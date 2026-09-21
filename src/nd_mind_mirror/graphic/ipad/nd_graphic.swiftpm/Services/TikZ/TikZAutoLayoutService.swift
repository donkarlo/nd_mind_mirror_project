// Deterministic layered and tree layouts for editable named-node TikZ graphs.

import CoreGraphics
import Foundation

final class TikZAutoLayoutService {
    func positions(
        for graph: TikZGraph,
        direction: TikZAutoLayoutDirection = .topToBottom
    ) -> [String: CGPoint] {
        guard !graph.nodes.isEmpty else { return [:] }
        let names = graph.nodes.map(\.name).sorted()
        let topology = layeredTopology(graph: graph, names: names)
        guard topology.acyclic else {
            return circularPositions(names)
        }

        switch direction {
        case .rightTree, .leftTree:
            return treePositions(
                graph: graph,
                topology: topology,
                direction: direction
            )
        default:
            return layeredPositions(
                topology: topology,
                direction: direction
            )
        }
    }

    private func layeredTopology(
        graph: TikZGraph,
        names: [String]
    ) -> (layers: [String: Int], grouped: [Int: [String]], maximum: Int, roots: [String], acyclic: Bool) {
        var outgoing: [String: [String]] = [:]
        var indegree = Dictionary(uniqueKeysWithValues: names.map { ($0, 0) })
        for edge in graph.edges where indegree[edge.source] != nil && indegree[edge.target] != nil {
            outgoing[edge.source, default: []].append(edge.target)
            indegree[edge.target, default: 0] += 1
        }

        let roots = names.filter { indegree[$0] == 0 }
        var queue = roots
        var layer = Dictionary(uniqueKeysWithValues: roots.map { ($0, 0) })
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

        let maximum = max(layer.values.max() ?? 0, 0)
        var grouped: [Int: [String]] = [:]
        for name in names {
            grouped[layer[name] ?? 0, default: []].append(name)
        }
        return (layer, grouped, maximum, roots, visited.count == names.count)
    }

    private func layeredPositions(
        topology: (layers: [String: Int], grouped: [Int: [String]], maximum: Int, roots: [String], acyclic: Bool),
        direction: TikZAutoLayoutDirection
    ) -> [String: CGPoint] {
        var result: [String: CGPoint] = [:]
        for level in 0...topology.maximum {
            let members = (topology.grouped[level] ?? []).sorted()
            for (index, name) in members.enumerated() {
                let memberFraction = members.count <= 1
                    ? 0.5
                    : Double(index) / Double(members.count - 1)
                let layerFraction = topology.maximum == 0
                    ? 0.5
                    : Double(level) / Double(topology.maximum)

                switch direction {
                case .topToBottom:
                    result[name] = CGPoint(
                        x: 2 + 12 * memberFraction,
                        y: 9.5 - 8 * layerFraction
                    )
                case .bottomToTop:
                    result[name] = CGPoint(
                        x: 2 + 12 * memberFraction,
                        y: 1.5 + 8 * layerFraction
                    )
                case .leftToRight:
                    result[name] = CGPoint(
                        x: 2 + 12 * layerFraction,
                        y: 9.5 - 8 * memberFraction
                    )
                case .rightToLeft:
                    result[name] = CGPoint(
                        x: 14 - 12 * layerFraction,
                        y: 9.5 - 8 * memberFraction
                    )
                case .rightTree, .leftTree:
                    break
                }
            }
        }
        return result
    }

    private func treePositions(
        graph: TikZGraph,
        topology: (layers: [String: Int], grouped: [Int: [String]], maximum: Int, roots: [String], acyclic: Bool),
        direction: TikZAutoLayoutDirection
    ) -> [String: CGPoint] {
        var outgoing: [String: [String]] = [:]
        for edge in graph.edges {
            outgoing[edge.source, default: []].append(edge.target)
        }
        var order: [String] = []
        var seen: Set<String> = []
        func visit(_ name: String) {
            guard seen.insert(name).inserted else { return }
            order.append(name)
            for child in (outgoing[name] ?? []).sorted() { visit(child) }
        }
        for root in topology.roots.sorted() { visit(root) }
        for name in topology.layers.keys.sorted() { visit(name) }
        let rank = Dictionary(uniqueKeysWithValues: order.enumerated().map { ($1, $0) })

        var result: [String: CGPoint] = [:]
        for level in 0...topology.maximum {
            let members = (topology.grouped[level] ?? []).sorted {
                (rank[$0] ?? 0) < (rank[$1] ?? 0)
            }
            for (index, name) in members.enumerated() {
                let vertical = members.count <= 1
                    ? 5.5
                    : 9.5 - 8 * Double(index) / Double(members.count - 1)
                let horizontal = topology.maximum == 0
                    ? 8.0
                    : 2 + 12 * Double(level) / Double(topology.maximum)
                result[name] = CGPoint(
                    x: direction == .rightTree ? horizontal : 16 - horizontal,
                    y: vertical
                )
            }
        }
        return result
    }

    private func circularPositions(_ names: [String]) -> [String: CGPoint] {
        guard names.count > 1 else {
            return [names[0]: CGPoint(x: 8, y: 5.5)]
        }
        var result: [String: CGPoint] = [:]
        for (index, name) in names.enumerated() {
            let angle = (Double(index) / Double(names.count)) * 2 * Double.pi - Double.pi / 2
            result[name] = CGPoint(
                x: 8 + 5.5 * cos(angle),
                y: 5.5 + 4.0 * sin(angle)
            )
        }
        return result
    }
}
