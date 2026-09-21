// Direct-manipulation TikZ editor opened automatically by Ubuntu.

import SwiftUI

struct TikZWorkspaceView: View {
    @ObservedObject var router: GraphicEditorSessionRouter

    @State private var activeTool: TikZCanvasTool = .select
    @State private var lastConnectorTool: TikZCanvasTool = .straightConnector
    @State private var pendingConnectorDrop: TikZPendingConnectorDrop?

    @State private var selectedNodeName: String?
    @State private var selectedEdgeID: String?
    @State private var editingNodeName: String?
    @State private var editingEdgeID: String?

    @State private var labelDraft = ""
    @State private var sourceDraft = ""

    @State private var showSource = false
    @State private var showCanvasEditor = false
    @State private var canvasWidthText = "760"
    @State private var canvasHeightText = "980"
    @State private var logicalCanvasSize = TikZCanvasMetadata.defaultSize

    @State private var nodeStyle = TikZNodeStyle()
    @State private var edgeStyle = TikZEdgeStyle()
    @State private var lastStyleMode: TikZStyleToolbarView.Mode = .node

    private let layoutService = TikZAutoLayoutService()
    private let nodeNameAllocator = TikZNodeNameAllocator()

    private var graph: TikZGraph {
        TikZGraphParser.parse(router.tikzSource)
    }

    private var connectionPointCounts: [String: Int] {
        TikZConnectionPointMetadata.counts(
            in: router.tikzSource,
            nodeNames: graph.nodes.map(\.name)
        )
    }

    private var selectedNode: TikZNode? {
        guard let selectedNodeName else { return nil }
        return graph.nodes.first { $0.name == selectedNodeName }
    }

    private var selectedEdge: TikZEdge? {
        guard let selectedEdgeID else { return nil }
        return graph.edges.first { $0.id == selectedEdgeID }
    }

    private var compactPath: String {
        guard let path = router.tikzPath, !path.isEmpty else {
            return "TikZ"
        }
        return path.split(separator: "/").suffix(2).joined(separator: "/")
    }

    private var styleMode: TikZStyleToolbarView.Mode {
        if selectedNode != nil { return .node }
        if selectedEdge != nil { return .edge }
        if activeTool == .rectangle || activeTool == .ellipse { return .node }
        if activeTool.connectorKind != nil { return .edge }
        return lastStyleMode
    }

    private var nodeStyleBinding: Binding<TikZNodeStyle> {
        Binding(
            get: { nodeStyle },
            set: { style in
                nodeStyle = style
                guard let node = selectedNode else { return }
                router.updateTikZSource(
                    TikZSourceEditor.updateNodeStyle(
                        named: node.name,
                        style: style,
                        in: router.tikzSource
                    )
                )
            }
        )
    }

    private var edgeStyleBinding: Binding<TikZEdgeStyle> {
        Binding(
            get: { edgeStyle },
            set: { style in
                edgeStyle = style
                guard let edge = selectedEdge else { return }
                router.updateTikZSource(
                    TikZSourceEditor.updateEdgeStyle(
                        edgeID: edge.id,
                        style: style,
                        in: router.tikzSource
                    )
                )
            }
        )
    }

    private var pendingConnectorDialogPresented: Binding<Bool> {
        Binding(
            get: { pendingConnectorDrop != nil },
            set: { presented in
                if !presented {
                    pendingConnectorDrop = nil
                }
            }
        )
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            drawingToolbar

            TikZStyleToolbarView(
                mode: styleMode,
                nodeStyle: nodeStyleBinding,
                edgeStyle: edgeStyleBinding
            )

            TikZCanvasView(
                graph: graph,
                previewImage: router.tikzPreviewImage,
                logicalCanvasSize: logicalCanvasSize,
                activeTool: activeTool,
                preferredConnectorTool: lastConnectorTool,
                connectionPointCounts: connectionPointCounts,
                draftNodeStyle: nodeStyle,
                draftEdgeStyle: edgeStyle,
                selectedNodeName: selectedNodeName,
                selectedEdgeID: selectedEdgeID,
                editingNodeName: editingNodeName,
                editingEdgeID: editingEdgeID,
                labelDraft: $labelDraft,
                onNodeSingleTap: selectNode,
                onNodeDoubleTap: editNodeLabel,
                onEdgeSingleTap: selectEdge,
                onEdgeDoubleTap: editEdgeLabel,
                onClearSelection: {
                    clearSelection(resetTool: false)
                },
                onNodeMove: moveNode,
                onNodeResize: resizeNode,
                onNodeDelete: deleteNode,
                onNodeDuplicate: duplicateNode,
                onNodeBringToFront: bringNodeToFront,
                onNodeSendToBack: sendNodeToBack,
                onNodeAddConnectionPoint: addConnectionPoint,
                onEdgeDelete: deleteEdge,
                onEdgeBringToFront: bringEdgeToFront,
                onEdgeSendToBack: sendEdgeToBack,
                onEdgeCurveControlMove: moveCurveControl,
                onEdgeBendMove: moveBendPoint,
                onEdgeBendRemove: removeBendPoint,
                onEdgeAddBendPoint: addBendPoint,
                onLabelCommit: finishLabelEditing,
                onConnectorAutoActivated: activateLastConnectorTool,
                onConnectorDrop: handleConnectorDrop,
                onShapeCreate: createShape
            )

            statusBar
        }
        .sheet(isPresented: $showSource) {
            sourceSheet
        }
        .popover(isPresented: $showCanvasEditor) {
            CanvasSizeEditorView(
                widthText: $canvasWidthText,
                heightText: $canvasHeightText,
                onApply: applyCanvasSize,
                onCancel: {
                    showCanvasEditor = false
                }
            )
        }
        .confirmationDialog(
            "Connector endpoint",
            isPresented: pendingConnectorDialogPresented,
            titleVisibility: .visible
        ) {
            Button("Connect to Rectangle") {
                connectPendingDrop(to: .rectangle)
            }
            Button("Connect to Ellipse") {
                connectPendingDrop(to: .ellipse)
            }
            Button("Delete Connector", role: .destructive) {
                pendingConnectorDrop = nil
            }
        } message: {
            Text(
                "The Pencil was lifted on empty canvas. Choose a new target shape or discard the connector."
            )
        }
        .onAppear {
            normalizeSourceDependencies()
            syncCanvasSizeFromSource()
        }
        .onChange(of: router.tikzPath) { _, _ in
            pendingConnectorDrop = nil
            clearSelection(resetTool: true, commitLabel: false)
            normalizeSourceDependencies()
            syncCanvasSizeFromSource()
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image(systemName: "point.3.connected.trianglepath.dotted")
                .foregroundStyle(Color.accentColor)

            Text(compactPath)
                .font(.subheadline.bold())
                .lineLimit(1)
                .truncationMode(.middle)

            Spacer()

            Menu {
                Button(action: openCanvasSizeEditor) {
                    Label("Canvas size…", systemImage: "aspectratio")
                }

                Menu {
                    ForEach(TikZAutoLayoutDirection.allCases) { direction in
                        Button(direction.title) {
                            autoLayout(direction)
                        }
                    }
                } label: {
                    Label("Auto layout", systemImage: "square.grid.3x3")
                }
                .disabled(graph.nodes.isEmpty)

                Button(action: openSource) {
                    Label(
                        "Source",
                        systemImage: "chevron.left.forwardslash.chevron.right"
                    )
                }
            } label: {
                Image(systemName: "gearshape.fill")
                    .frame(width: 30, height: 30)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("TikZ options")

            Button(action: router.closeTikZ) {
                Image(systemName: "xmark.circle.fill")
                    .font(.title3)
                    .frame(width: 30, height: 30)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close TikZ editor")
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 2)
        .background(.thinMaterial)
    }

    private var drawingToolbar: some View {
        HStack(spacing: 8) {
            toolButton(
                title: "Rectangle",
                systemImage: "rectangle",
                tool: .rectangle
            )
            toolButton(
                title: "Ellipse",
                systemImage: "circle",
                tool: .ellipse
            )
            toolButton(
                title: "Straight",
                systemImage: "arrow.right",
                tool: .straightConnector
            )
            toolButton(
                title: "Curve",
                systemImage: "scribble.variable",
                tool: .curveConnector
            )
            toolButton(
                title: "Polyline",
                systemImage: "point.3.connected.trianglepath.dotted",
                tool: .polylineConnector
            )
            Spacer()
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(.bar)
    }

    private var statusBar: some View {
        HStack {
            Text(router.tikzStatus)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)

            Spacer()

            Text(
                "\(Int(logicalCanvasSize.width)) × \(Int(logicalCanvasSize.height))"
            )
            .font(.caption2.monospacedDigit())
            .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color(uiColor: .tertiarySystemBackground))
    }

    private var sourceSheet: some View {
        NavigationStack {
            TextEditor(text: $sourceDraft)
                .font(.system(.body, design: .monospaced))
                .padding(8)
                .navigationTitle(compactPath)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") {
                            showSource = false
                        }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Apply") {
                            router.updateTikZSource(sourceDraft)
                            logicalCanvasSize =
                                TikZCanvasMetadata.size(in: sourceDraft)
                            showSource = false
                        }
                    }
                }
        }
    }

    private func toolButton(
        title: String,
        systemImage: String,
        tool: TikZCanvasTool
    ) -> some View {
        Button {
            chooseTool(tool)
        } label: {
            Label(title, systemImage: systemImage)
        }
        .buttonStyle(.bordered)
        .tint(activeTool == tool ? Color.accentColor : Color.secondary)
    }

    private func chooseTool(_ tool: TikZCanvasTool) {
        commitInlineLabelIfNeeded()
        if tool.connectorKind != nil {
            lastConnectorTool = tool
        }
        activeTool = activeTool == tool ? .select : tool
        updateLastStyleMode(for: activeTool)
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func activateLastConnectorTool() {
        if lastConnectorTool.connectorKind == nil {
            lastConnectorTool = .straightConnector
        }
        activeTool = lastConnectorTool
        lastStyleMode = .edge
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func selectNode(_ node: TikZNode) {
        commitInlineLabelIfNeeded()
        activeTool = .select
        lastStyleMode = .node
        nodeStyle = node.style
        labelDraft = node.label
        selectedNodeName = node.name
        selectedEdgeID = nil
        editingNodeName = nil
        editingEdgeID = nil
    }

    private func editNodeLabel(_ node: TikZNode) {
        selectNode(node)
        editingNodeName = node.name
    }

    private func selectEdge(_ edge: TikZEdge) {
        commitInlineLabelIfNeeded()
        activeTool = .select
        lastStyleMode = .edge
        edgeStyle = edge.style
        labelDraft = edge.label
        selectedEdgeID = edge.id
        selectedNodeName = nil
        editingNodeName = nil
        editingEdgeID = nil
    }

    private func editEdgeLabel(_ edge: TikZEdge) {
        selectEdge(edge)
        editingEdgeID = edge.id
    }

    private func moveNode(_ node: TikZNode, to point: CGPoint) {
        router.updateTikZSource(
            TikZSourceEditor.moveNode(
                named: node.name,
                to: point,
                in: router.tikzSource
            )
        )
    }

    private func resizeNode(
        _ node: TikZNode,
        center: CGPoint,
        size: CGSize
    ) {
        router.updateTikZSource(
            TikZSourceEditor.resizeNode(
                named: node.name,
                center: center,
                size: size,
                in: router.tikzSource
            )
        )
    }

    private func deleteNode(_ node: TikZNode) {
        let withoutNode = TikZSourceEditor.deleteNode(
            named: node.name,
            in: router.tikzSource
        )
        router.updateTikZSource(
            TikZConnectionPointMetadata.removing(
                nodeName: node.name,
                from: withoutNode
            )
        )
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func duplicateNode(_ node: TikZNode) {
        commitInlineLabelIfNeeded()
        router.updateTikZSource(
            TikZSourceEditor.duplicateNode(
                named: node.name,
                in: router.tikzSource
            )
        )
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func addConnectionPoint(_ node: TikZNode) {
        let current = TikZConnectionPointMetadata.count(
            for: node.name,
            in: router.tikzSource
        )
        router.updateTikZSource(
            TikZConnectionPointMetadata.updating(
                nodeName: node.name,
                count: current + 1,
                in: router.tikzSource
            )
        )
        selectedNodeName = node.name
        selectedEdgeID = nil
    }

    private func bringNodeToFront(_ node: TikZNode) {
        commitInlineLabelIfNeeded()
        router.updateTikZSource(
            TikZSourceEditor.bringNodeToFront(
                named: node.name,
                in: router.tikzSource
            )
        )
        selectedNodeName = node.name
    }

    private func sendNodeToBack(_ node: TikZNode) {
        commitInlineLabelIfNeeded()
        router.updateTikZSource(
            TikZSourceEditor.sendNodeToBack(
                named: node.name,
                in: router.tikzSource
            )
        )
        selectedNodeName = node.name
    }

    private func deleteEdge(_ edge: TikZEdge) {
        router.updateTikZSource(
            TikZSourceEditor.deleteEdge(
                edgeID: edge.id,
                in: router.tikzSource
            )
        )
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func bringEdgeToFront(_ edge: TikZEdge) {
        commitInlineLabelIfNeeded()
        router.updateTikZSource(
            TikZSourceEditor.bringEdgeToFront(
                edgeID: edge.id,
                in: router.tikzSource
            )
        )
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func sendEdgeToBack(_ edge: TikZEdge) {
        commitInlineLabelIfNeeded()
        router.updateTikZSource(
            TikZSourceEditor.sendEdgeToBack(
                edgeID: edge.id,
                in: router.tikzSource
            )
        )
        clearSelection(resetTool: false, commitLabel: false)
    }

    private func handleConnectorDrop(
        sourceNode: TikZNode,
        targetNode: TikZNode?,
        point: CGPoint
    ) {
        if let targetNode {
            createConnector(from: sourceNode, to: targetNode)
            return
        }
        pendingConnectorDrop = TikZPendingConnectorDrop(
            sourceNodeName: sourceNode.name,
            point: point
        )
    }

    private func createConnector(
        from sourceNode: TikZNode,
        to targetNode: TikZNode
    ) {
        let kind = activeTool.connectorKind
            ?? lastConnectorTool.connectorKind
            ?? .straight
        let geometry = TikZConnectorGeometry.initial(
            kind: kind,
            source: sourceNode.position,
            target: targetNode.position
        )
        router.updateTikZSource(
            TikZSourceEditor.addEdge(
                from: sourceNode.name,
                to: targetNode.name,
                label: "",
                style: edgeStyle,
                geometry: geometry,
                in: router.tikzSource
            )
        )
        lastStyleMode = .edge
    }

    private func connectPendingDrop(to shape: TikZNodeShape) {
        guard
            let request = pendingConnectorDrop,
            let sourceNode = graph.nodes.first(
                where: { $0.name == request.sourceNodeName }
            )
        else {
            pendingConnectorDrop = nil
            return
        }

        let targetName = nodeNameAllocator.nextName(in: router.tikzSource)
        let targetSize = shape == .ellipse
            ? CGSize(width: 2.0, height: 1.2)
            : CGSize(width: 2.2, height: 1.2)
        let kind = activeTool.connectorKind
            ?? lastConnectorTool.connectorKind
            ?? .straight

        let withNode = TikZSourceEditor.addNode(
            shape: shape,
            center: request.point,
            size: targetSize,
            style: nodeStyle,
            label: "",
            to: router.tikzSource
        )
        let geometry = TikZConnectorGeometry.initial(
            kind: kind,
            source: sourceNode.position,
            target: request.point
        )
        let withEdge = TikZSourceEditor.addEdge(
            from: sourceNode.name,
            to: targetName,
            label: "",
            style: edgeStyle,
            geometry: geometry,
            in: withNode
        )

        router.updateTikZSource(withEdge)
        pendingConnectorDrop = nil
        lastStyleMode = .edge
    }

    private func moveCurveControl(
        _ edge: TikZEdge,
        index: Int,
        to point: CGPoint
    ) {
        var geometry = edge.geometry
        geometry.setCurveControl(index: index, point: point)
        updateEdgeGeometry(edge, geometry: geometry)
    }

    private func moveBendPoint(
        _ edge: TikZEdge,
        index: Int,
        to point: CGPoint
    ) {
        var geometry = edge.geometry
        geometry.setBendPoint(index: index, point: point)
        updateEdgeGeometry(edge, geometry: geometry)
    }

    private func addBendPoint(
        _ edge: TikZEdge,
        segmentIndex: Int,
        at point: CGPoint
    ) {
        var geometry = edge.geometry
        guard geometry.kind == .polyline else { return }
        geometry.insertBendPoint(point, at: segmentIndex)
        updateEdgeGeometry(edge, geometry: geometry)
    }

    private func removeBendPoint(_ edge: TikZEdge, index: Int) {
        var geometry = edge.geometry
        geometry.removeBendPoint(index: index)
        updateEdgeGeometry(edge, geometry: geometry)
    }

    private func updateEdgeGeometry(
        _ edge: TikZEdge,
        geometry: TikZConnectorGeometry
    ) {
        router.updateTikZSource(
            TikZSourceEditor.updateEdgeGeometry(
                edgeID: edge.id,
                geometry: geometry,
                in: router.tikzSource
            )
        )
        selectedEdgeID = edge.id
        selectedNodeName = nil
        lastStyleMode = .edge
    }

    private func createShape(
        _ shape: TikZNodeShape,
        center: CGPoint,
        size: CGSize
    ) {
        router.updateTikZSource(
            TikZSourceEditor.addNode(
                shape: shape,
                center: center,
                size: size,
                style: nodeStyle,
                label: "",
                to: router.tikzSource
            )
        )
        lastStyleMode = .node
        activeTool = .select
    }

    private func commitSelectedLabel() {
        if let node = selectedNode {
            router.updateTikZSource(
                TikZSourceEditor.updateNodeLabel(
                    named: node.name,
                    label: labelDraft,
                    in: router.tikzSource
                )
            )
        } else if let edge = selectedEdge {
            router.updateTikZSource(
                TikZSourceEditor.updateEdgeLabel(
                    edgeID: edge.id,
                    label: labelDraft,
                    style: edgeStyle,
                    in: router.tikzSource
                )
            )
        }
    }

    private func commitInlineLabelIfNeeded() {
        guard editingNodeName != nil || editingEdgeID != nil else {
            return
        }
        commitSelectedLabel()
        editingNodeName = nil
        editingEdgeID = nil
    }

    private func finishLabelEditing() {
        commitInlineLabelIfNeeded()
    }

    private func openSource() {
        commitInlineLabelIfNeeded()
        sourceDraft = router.tikzSource
        showSource = true
    }

    private func openCanvasSizeEditor() {
        canvasWidthText = String(Int(logicalCanvasSize.width.rounded()))
        canvasHeightText = String(Int(logicalCanvasSize.height.rounded()))
        showCanvasEditor = true
    }

    private func applyCanvasSize() {
        guard
            let width = Double(canvasWidthText),
            let height = Double(canvasHeightText)
        else {
            return
        }

        let size = CGSize(
            width: max(width, 64),
            height: max(height, 64)
        )
        logicalCanvasSize = size
        router.updateTikZSource(
            TikZSourceEditor.updateCanvasSize(
                size,
                in: router.tikzSource
            )
        )
        showCanvasEditor = false
    }

    private func normalizeSourceDependencies() {
        let normalized =
            TikZSourceDependencyManager.ensuringRequiredLibraries(
                in: router.tikzSource
            )
        guard normalized != router.tikzSource else { return }
        router.updateTikZSource(normalized)
    }

    private func syncCanvasSizeFromSource() {
        logicalCanvasSize = TikZCanvasMetadata.size(in: router.tikzSource)
    }

    private func autoLayout(_ direction: TikZAutoLayoutDirection) {
        commitInlineLabelIfNeeded()
        let positions = layoutService.positions(
            for: graph,
            direction: direction
        )
        router.updateTikZSource(
            TikZSourceEditor.applyPositions(
                positions,
                to: router.tikzSource
            )
        )
        clearSelection(resetTool: true, commitLabel: false)
    }

    private func clearSelection(
        resetTool: Bool,
        commitLabel: Bool = true
    ) {
        if commitLabel {
            commitInlineLabelIfNeeded()
        }
        selectedNodeName = nil
        selectedEdgeID = nil
        editingNodeName = nil
        editingEdgeID = nil
        labelDraft = ""
        if resetTool {
            activeTool = .select
        }
    }

    private func updateLastStyleMode(for tool: TikZCanvasTool) {
        if tool.connectorKind != nil {
            lastStyleMode = .edge
        } else if tool == .rectangle || tool == .ellipse {
            lastStyleMode = .node
        }
    }
}
