// Single owner for iPad TikZ tap, context-menu, shape, and Pencil connector gestures.

import UIKit

final class TikZCanvasInteractionCoordinator:
    NSObject,
    UIGestureRecognizerDelegate,
    UIContextMenuInteractionDelegate
{
    private var graph = TikZGraph.empty
    private var canvasSize = CGSize(width: 1, height: 1)
    private var activeTool: TikZCanvasTool = .select
    private var preferredConnectorTool: TikZCanvasTool = .straightConnector
    private var connectionPointCounts: [String: Int] = [:]

    private let hitTester = TikZCanvasHitTester()
    private let connectionGeometry = TikZConnectionPointGeometry()

    private weak var hostView: UIView?
    private var singleTap: UITapGestureRecognizer?
    private var doubleTap: UITapGestureRecognizer?
    private var connectorPan: UIPanGestureRecognizer?
    private var shapePan: UIPanGestureRecognizer?

    private var connectorSourceName: String?
    private var shapeStartPoint: CGPoint?

    private var onNodeSingleTap: ((String) -> Void)?
    private var onNodeDoubleTap: ((String) -> Void)?
    private var onEdgeSingleTap: ((String) -> Void)?
    private var onEdgeDoubleTap: ((String) -> Void)?
    private var onClearSelection: (() -> Void)?

    private var onConnectorAutoActivated: (() -> Void)?
    private var onConnectorDragChanged: ((String, CGPoint) -> Void)?
    private var onConnectorDragEnded: ((String, String?, CGPoint) -> Void)?
    private var onShapeDragChanged: ((CGPoint, CGPoint) -> Void)?
    private var onShapeDragEnded: ((TikZNodeShape, CGPoint, CGPoint) -> Void)?

    private var onNodeEditLabel: ((String) -> Void)?
    private var onNodeDuplicate: ((String) -> Void)?
    private var onNodeBringToFront: ((String) -> Void)?
    private var onNodeSendToBack: ((String) -> Void)?
    private var onNodeAddConnectionPoint: ((String) -> Void)?
    private var onNodeDelete: ((String) -> Void)?

    private var onEdgeEditLabel: ((String) -> Void)?
    private var onEdgeAddBendPoint: ((String, CGPoint) -> Void)?
    private var onEdgeBringToFront: ((String) -> Void)?
    private var onEdgeSendToBack: ((String) -> Void)?
    private var onEdgeDelete: ((String) -> Void)?

    func attach(to view: UIView) {
        hostView = view

        let doubleTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleDoubleTap(_:))
        )
        doubleTap.numberOfTapsRequired = 2
        doubleTap.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.direct.rawValue),
            NSNumber(value: UITouch.TouchType.pencil.rawValue),
        ]
        doubleTap.delegate = self
        view.addGestureRecognizer(doubleTap)
        self.doubleTap = doubleTap

        let singleTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleSingleTap(_:))
        )
        singleTap.numberOfTapsRequired = 1
        singleTap.allowedTouchTypes = doubleTap.allowedTouchTypes
        singleTap.require(toFail: doubleTap)
        singleTap.delegate = self
        view.addGestureRecognizer(singleTap)
        self.singleTap = singleTap

        let connectorPan = UIPanGestureRecognizer(
            target: self,
            action: #selector(handleConnectorPan(_:))
        )
        connectorPan.minimumNumberOfTouches = 1
        connectorPan.maximumNumberOfTouches = 1
        connectorPan.allowedTouchTypes = [
            NSNumber(value: UITouch.TouchType.pencil.rawValue)
        ]
        connectorPan.delegate = self
        view.addGestureRecognizer(connectorPan)
        self.connectorPan = connectorPan

        let shapePan = UIPanGestureRecognizer(
            target: self,
            action: #selector(handleShapePan(_:))
        )
        shapePan.minimumNumberOfTouches = 1
        shapePan.maximumNumberOfTouches = 1
        shapePan.allowedTouchTypes = doubleTap.allowedTouchTypes
        shapePan.delegate = self
        view.addGestureRecognizer(shapePan)
        self.shapePan = shapePan

        view.addInteraction(UIContextMenuInteraction(delegate: self))
        updateGestureAvailability()
    }

    func update(
        graph: TikZGraph,
        canvasSize: CGSize,
        activeTool: TikZCanvasTool,
        preferredConnectorTool: TikZCanvasTool,
        connectionPointCounts: [String: Int],
        onNodeSingleTap: @escaping (String) -> Void,
        onNodeDoubleTap: @escaping (String) -> Void,
        onEdgeSingleTap: @escaping (String) -> Void,
        onEdgeDoubleTap: @escaping (String) -> Void,
        onClearSelection: @escaping () -> Void,
        onConnectorAutoActivated: @escaping () -> Void,
        onConnectorDragChanged: @escaping (String, CGPoint) -> Void,
        onConnectorDragEnded: @escaping (String, String?, CGPoint) -> Void,
        onShapeDragChanged: @escaping (CGPoint, CGPoint) -> Void,
        onShapeDragEnded: @escaping (TikZNodeShape, CGPoint, CGPoint) -> Void,
        onNodeEditLabel: @escaping (String) -> Void,
        onNodeDuplicate: @escaping (String) -> Void,
        onNodeBringToFront: @escaping (String) -> Void,
        onNodeSendToBack: @escaping (String) -> Void,
        onNodeAddConnectionPoint: @escaping (String) -> Void,
        onNodeDelete: @escaping (String) -> Void,
        onEdgeEditLabel: @escaping (String) -> Void,
        onEdgeAddBendPoint: @escaping (String, CGPoint) -> Void,
        onEdgeBringToFront: @escaping (String) -> Void,
        onEdgeSendToBack: @escaping (String) -> Void,
        onEdgeDelete: @escaping (String) -> Void
    ) {
        self.graph = graph
        self.canvasSize = canvasSize
        self.activeTool = activeTool
        self.preferredConnectorTool = preferredConnectorTool.connectorKind == nil
            ? .straightConnector
            : preferredConnectorTool
        self.connectionPointCounts = connectionPointCounts
        self.onNodeSingleTap = onNodeSingleTap
        self.onNodeDoubleTap = onNodeDoubleTap
        self.onEdgeSingleTap = onEdgeSingleTap
        self.onEdgeDoubleTap = onEdgeDoubleTap
        self.onClearSelection = onClearSelection
        self.onConnectorAutoActivated = onConnectorAutoActivated
        self.onConnectorDragChanged = onConnectorDragChanged
        self.onConnectorDragEnded = onConnectorDragEnded
        self.onShapeDragChanged = onShapeDragChanged
        self.onShapeDragEnded = onShapeDragEnded
        self.onNodeEditLabel = onNodeEditLabel
        self.onNodeDuplicate = onNodeDuplicate
        self.onNodeBringToFront = onNodeBringToFront
        self.onNodeSendToBack = onNodeSendToBack
        self.onNodeAddConnectionPoint = onNodeAddConnectionPoint
        self.onNodeDelete = onNodeDelete
        self.onEdgeEditLabel = onEdgeEditLabel
        self.onEdgeAddBendPoint = onEdgeAddBendPoint
        self.onEdgeBringToFront = onEdgeBringToFront
        self.onEdgeSendToBack = onEdgeSendToBack
        self.onEdgeDelete = onEdgeDelete
        updateGestureAvailability()
    }

    @objc private func handleSingleTap(_ recognizer: UITapGestureRecognizer) {
        guard let view = hostView else { return }
        let point = recognizer.location(in: view)
        switch hitTester.target(at: point, in: graph, canvasSize: canvasSize) {
        case .node(let name): onNodeSingleTap?(name)
        case .edge(let id): onEdgeSingleTap?(id)
        case .none: onClearSelection?()
        }
    }

    @objc private func handleDoubleTap(_ recognizer: UITapGestureRecognizer) {
        guard let view = hostView else { return }
        let point = recognizer.location(in: view)
        switch hitTester.target(at: point, in: graph, canvasSize: canvasSize) {
        case .node(let name): onNodeDoubleTap?(name)
        case .edge(let id): onEdgeDoubleTap?(id)
        case .none: break
        }
    }

    @objc private func handleConnectorPan(_ recognizer: UIPanGestureRecognizer) {
        guard let view = hostView else { return }
        let point = recognizer.location(in: view)

        switch recognizer.state {
        case .began:
            guard
                activeTool.connectorKind != nil || activeTool == .select,
                let hit = connectionGeometry.nearest(
                    to: point,
                    in: graph,
                    counts: connectionPointCounts,
                    canvasSize: canvasSize,
                    tolerance: 28
                )
            else {
                connectorSourceName = nil
                return
            }
            connectorSourceName = hit.node.name
            if activeTool.connectorKind == nil {
                onConnectorAutoActivated?()
            }
            onConnectorDragChanged?(hit.node.name, point)

        case .changed:
            guard let sourceName = connectorSourceName else { return }
            onConnectorDragChanged?(sourceName, point)

        case .ended:
            guard let sourceName = connectorSourceName else { return }
            let target = connectionGeometry.nearest(
                to: point,
                in: graph,
                counts: connectionPointCounts,
                canvasSize: canvasSize,
                excluding: sourceName,
                tolerance: 32
            )
            connectorSourceName = nil
            onConnectorDragEnded?(sourceName, target?.node.name, point)

        case .cancelled, .failed:
            if let sourceName = connectorSourceName {
                onConnectorDragEnded?(sourceName, nil, point)
            }
            connectorSourceName = nil

        default:
            break
        }
    }

    @objc private func handleShapePan(_ recognizer: UIPanGestureRecognizer) {
        guard let shape = activeTool.nodeShape, let view = hostView else { return }
        let point = recognizer.location(in: view)
        switch recognizer.state {
        case .began:
            shapeStartPoint = point
            onShapeDragChanged?(point, point)
        case .changed:
            guard let start = shapeStartPoint else { return }
            onShapeDragChanged?(start, point)
        case .ended:
            guard let start = shapeStartPoint else { return }
            shapeStartPoint = nil
            onShapeDragEnded?(shape, start, point)
        case .cancelled, .failed:
            shapeStartPoint = nil
        default:
            break
        }
    }

    private func updateGestureAvailability() {
        connectorPan?.isEnabled = activeTool.connectorKind != nil || activeTool == .select
        shapePan?.isEnabled = activeTool.nodeShape != nil
        singleTap?.isEnabled = true
        doubleTap?.isEnabled = true
    }

    func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        guard let view = hostView else { return false }
        if gestureRecognizer === connectorPan {
            guard activeTool.connectorKind != nil || activeTool == .select else { return false }
            let point = gestureRecognizer.location(in: view)
            return connectionGeometry.nearest(
                to: point,
                in: graph,
                counts: connectionPointCounts,
                canvasSize: canvasSize,
                tolerance: 28
            ) != nil
        }
        if gestureRecognizer === shapePan {
            return activeTool.nodeShape != nil
        }
        return true
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        false
    }

    func contextMenuInteraction(
        _ interaction: UIContextMenuInteraction,
        configurationForMenuAtLocation location: CGPoint
    ) -> UIContextMenuConfiguration? {
        guard let target = hitTester.target(
            at: location,
            in: graph,
            canvasSize: canvasSize
        ) else {
            return nil
        }

        switch target {
        case .node(let name):
            onNodeSingleTap?(name)
            return UIContextMenuConfiguration(
                identifier: nil,
                previewProvider: nil
            ) { [weak self] _ in
                guard let self else { return UIMenu() }
                return UIMenu(children: [
                    UIAction(
                        title: "Edit label",
                        image: UIImage(systemName: "pencil")
                    ) { [weak self] _ in self?.onNodeEditLabel?(name) },
                    UIAction(
                        title: "Duplicate",
                        image: UIImage(systemName: "plus.square.on.square")
                    ) { [weak self] _ in self?.onNodeDuplicate?(name) },
                    UIAction(
                        title: "Add connection point",
                        image: UIImage(systemName: "plus.circle")
                    ) { [weak self] _ in self?.onNodeAddConnectionPoint?(name) },
                    UIAction(
                        title: "Bring to Front",
                        image: UIImage(systemName: "square.3.layers.3d.top.filled")
                    ) { [weak self] _ in self?.onNodeBringToFront?(name) },
                    UIAction(
                        title: "Send to Back",
                        image: UIImage(systemName: "square.3.layers.3d.bottom.filled")
                    ) { [weak self] _ in self?.onNodeSendToBack?(name) },
                    UIAction(
                        title: "Delete",
                        image: UIImage(systemName: "trash"),
                        attributes: .destructive
                    ) { [weak self] _ in self?.onNodeDelete?(name) },
                ])
            }

        case .edge(let id):
            onEdgeSingleTap?(id)
            let edge = graph.edges.first { $0.id == id }
            return UIContextMenuConfiguration(
                identifier: nil,
                previewProvider: nil
            ) { [weak self] _ in
                guard let self else { return UIMenu() }
                var actions: [UIMenuElement] = [
                    UIAction(
                        title: "Edit label",
                        image: UIImage(systemName: "pencil")
                    ) { [weak self] _ in self?.onEdgeEditLabel?(id) }
                ]
                if edge?.geometry.kind == .polyline {
                    actions.append(
                        UIAction(
                            title: "Add bend point here",
                            image: UIImage(systemName: "plus.circle")
                        ) { [weak self] _ in
                            self?.onEdgeAddBendPoint?(id, location)
                        }
                    )
                }
                actions.append(
                    UIAction(
                        title: "Bring to Front",
                        image: UIImage(systemName: "square.3.layers.3d.top.filled")
                    ) { [weak self] _ in self?.onEdgeBringToFront?(id) }
                )
                actions.append(
                    UIAction(
                        title: "Send to Back",
                        image: UIImage(systemName: "square.3.layers.3d.bottom.filled")
                    ) { [weak self] _ in self?.onEdgeSendToBack?(id) }
                )
                actions.append(
                    UIAction(
                        title: "Delete",
                        image: UIImage(systemName: "trash"),
                        attributes: .destructive
                    ) { [weak self] _ in self?.onEdgeDelete?(id) }
                )
                return UIMenu(children: actions)
            }
        }
    }
}
