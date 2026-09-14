// Direct-manipulation TikZ editor opened automatically by Ubuntu.

import SwiftUI

struct TikZWorkspaceView: View {
    @ObservedObject var router: GraphicEditorSessionRouter

    @State private var activeTool: TikZCanvasTool = .select
    @State private var selectedNodeName: String?
    @State private var selectedEdgeID: String?
    @State private var editingNodeName: String?
    @State private var editingEdgeID: String?

    @State private var pendingNodeLabel = ""
    @State private var pendingConnectorLabel = ""
    @State private var labelDraft = ""
    @State private var sourceDraft = ""

    @State private var showSource = false
    @State private var showCanvasEditor = false
    @State private var canvasWidthText = "760"
    @State private var canvasHeightText = "980"
    @State private var logicalCanvasSize = TikZCanvasMetadata.defaultSize

    @State private var nodeStyle = TikZNodeStyle()
    @State private var edgeStyle = TikZEdgeStyle()

    private let layoutService = TikZAutoLayoutService()

    private var graph: TikZGraph {
        TikZGraphParser.parse(router.tikzSource)
    }

    private var selectedNode: TikZNode? {
        guard let selectedNodeName else {
            return nil
        }
        return graph.nodes.first {
            $0.name == selectedNodeName
        }
    }

    private var selectedEdge: TikZEdge? {
        guard let selectedEdgeID else {
            return nil
        }
        return graph.edges.first {
            $0.id == selectedEdgeID
        }
    }

    private var compactPath: String {
        guard
            let path = router.tikzPath,
            !path.isEmpty
        else {
            return "TikZ"
        }

        return path
            .split(separator: "/")
            .suffix(2)
            .joined(separator: "/")
    }

    private var hasSelection: Bool {
        selectedNode != nil || selectedEdge != nil
    }

    private var styleMode: TikZStyleToolbarView.Mode {
        if selectedNode != nil {
            return .node
        }
        if selectedEdge != nil {
            return .edge
        }
        if activeTool == .rectangle || activeTool == .ellipse {
            return .node
        }
        if activeTool == .connector {
            return .edge
        }
        return .hidden
    }

    private var propertyLabel: Binding<String> {
        if hasSelection {
            return $labelDraft
        }
        if activeTool == .rectangle || activeTool == .ellipse {
            return $pendingNodeLabel
        }
        if activeTool == .connector {
            return $pendingConnectorLabel
        }
        return $labelDraft
    }

    private var nodeStyleBinding: Binding<TikZNodeStyle> {
        Binding(
            get: {
                nodeStyle
            },
            set: { style in
                nodeStyle = style
                guard let node = selectedNode else {
                    return
                }
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
            get: {
                edgeStyle
            },
            set: { style in
                edgeStyle = style
                guard let edge = selectedEdge else {
                    return
                }
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

    var body: some View {
        VStack(spacing: 0) {
            header
            drawingToolbar

            TikZStyleToolbarView(
                mode: styleMode,
                nodeStyle: nodeStyleBinding,
                edgeStyle: edgeStyleBinding,
                label: propertyLabel,
                labelPlaceholder: (
                    selectedEdge != nil || activeTool == .connector
                )
                    ? "Connector label"
                    : "Node label",
                onCommitLabel: hasSelection
                    ? commitSelectedLabel
                    : nil
            )

            TikZCanvasView(
                graph: graph,
                previewImage: router.tikzPreviewImage,
                logicalCanvasSize: logicalCanvasSize,
                activeTool: activeTool,
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
                onEdgeDelete: deleteEdge,
                onEdgeBringToFront: bringEdgeToFront,
                onEdgeSendToBack: sendEdgeToBack,
                onLabelCommit: finishLabelEditing,
                onConnectorCreate: createConnector,
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
        .onAppear {
            normalizeSourceDependencies()
            syncCanvasSizeFromSource()
        }
        .onChange(of: router.tikzPath) { _, _ in
            clearSelection(resetTool: true)
            normalizeSourceDependencies()
            syncCanvasSizeFromSource()
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image(
                systemName: "point.3.connected.trianglepath.dotted"
            )
            .foregroundStyle(Color.accentColor)

            Text(compactPath)
                .font(.subheadline.bold())
                .lineLimit(1)
                .truncationMode(.middle)

            Spacer()

            Menu {
                Button(
                    action: openCanvasSizeEditor
                ) {
                    Label(
                        "Canvas size…",
                        systemImage: "aspectratio"
                    )
                }

                Button(
                    action: autoLayout
                ) {
                    Label(
                        "Auto layout",
                        systemImage: "square.grid.3x3"
                    )
                }
                .disabled(graph.nodes.isEmpty)

                Button(
                    action: openSource
                ) {
                    Label(
                        "Source",
                        systemImage: "chevron.left.forwardslash.chevron.right"
                    )
                }
            } label: {
                Image(
                    systemName: "gearshape.fill"
                )
                .frame(
                    width: 30,
                    height: 30
                )
            }
            .buttonStyle(.plain)
            .accessibilityLabel("TikZ options")

            Button(
                action: router.closeTikZ
            ) {
                Image(
                    systemName: "xmark.circle.fill"
                )
                .font(.title3)
                .frame(
                    width: 30,
                    height: 30
                )
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
                title: "Connector",
                systemImage: "arrow.right",
                tool: .connector
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
            .font(
                .caption2
                    .monospacedDigit()
            )
            .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(
            Color(
                uiColor: .tertiarySystemBackground
            )
        )
    }

    private var sourceSheet: some View {
        NavigationStack {
            TextEditor(
                text: $sourceDraft
            )
            .font(
                .system(
                    .body,
                    design: .monospaced
                )
            )
            .padding(8)
            .navigationTitle(compactPath)
            .toolbar {
                ToolbarItem(
                    placement: .cancellationAction
                ) {
                    Button("Cancel") {
                        showSource = false
                    }
                }

                ToolbarItem(
                    placement: .confirmationAction
                ) {
                    Button("Apply") {
                        router.updateTikZSource(
                            sourceDraft
                        )
                        logicalCanvasSize =
                            TikZCanvasMetadata.size(
                                in: sourceDraft
                            )
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
            Label(
                title,
                systemImage: systemImage
            )
        }
        .buttonStyle(.bordered)
        .tint(
            activeTool == tool
                ? Color.accentColor
                : Color.secondary
        )
    }

    private func chooseTool(
        _ tool: TikZCanvasTool
    ) {
        activeTool =
            activeTool == tool
                ? .select
                : tool
        clearSelection(
            resetTool: false
        )
    }

    private func selectNode(
        _ node: TikZNode
    ) {
        activeTool = .select
        nodeStyle = node.style
        labelDraft = node.label
        selectedNodeName = node.name
        selectedEdgeID = nil
        editingNodeName = nil
        editingEdgeID = nil
    }

    private func editNodeLabel(
        _ node: TikZNode
    ) {
        selectNode(node)
        editingNodeName = node.name
    }

    private func selectEdge(
        _ edge: TikZEdge
    ) {
        activeTool = .select
        edgeStyle = edge.style
        labelDraft = edge.label
        selectedEdgeID = edge.id
        selectedNodeName = nil
        editingNodeName = nil
        editingEdgeID = nil
    }

    private func editEdgeLabel(
        _ edge: TikZEdge
    ) {
        selectEdge(edge)
        editingEdgeID = edge.id
    }

    private func moveNode(
        _ node: TikZNode,
        to point: CGPoint
    ) {
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

    private func deleteNode(
        _ node: TikZNode
    ) {
        router.updateTikZSource(
            TikZSourceEditor.deleteNode(
                named: node.name,
                in: router.tikzSource
            )
        )
        clearSelection(
            resetTool: false
        )
    }

    private func duplicateNode(
        _ node: TikZNode
    ) {
        router.updateTikZSource(
            TikZSourceEditor.duplicateNode(
                named: node.name,
                in: router.tikzSource
            )
        )
        clearSelection(
            resetTool: false
        )
    }

    private func bringNodeToFront(
        _ node: TikZNode
    ) {
        router.updateTikZSource(
            TikZSourceEditor.bringNodeToFront(
                named: node.name,
                in: router.tikzSource
            )
        )
        selectedNodeName = node.name
    }

    private func sendNodeToBack(
        _ node: TikZNode
    ) {
        router.updateTikZSource(
            TikZSourceEditor.sendNodeToBack(
                named: node.name,
                in: router.tikzSource
            )
        )
        selectedNodeName = node.name
    }

    private func deleteEdge(
        _ edge: TikZEdge
    ) {
        router.updateTikZSource(
            TikZSourceEditor.deleteEdge(
                edgeID: edge.id,
                in: router.tikzSource
            )
        )
        clearSelection(
            resetTool: false
        )
    }

    private func bringEdgeToFront(
        _ edge: TikZEdge
    ) {
        router.updateTikZSource(
            TikZSourceEditor.bringEdgeToFront(
                edgeID: edge.id,
                in: router.tikzSource
            )
        )
        clearSelection(resetTool: false)
    }

    private func sendEdgeToBack(
        _ edge: TikZEdge
    ) {
        router.updateTikZSource(
            TikZSourceEditor.sendEdgeToBack(
                edgeID: edge.id,
                in: router.tikzSource
            )
        )
        clearSelection(resetTool: false)
    }

    private func createConnector(
        from sourceNode: TikZNode,
        to targetNode: TikZNode
    ) {
        let updated = TikZSourceEditor.addEdge(
            from: sourceNode.name,
            to: targetNode.name,
            label: pendingConnectorLabel,
            style: edgeStyle,
            in: router.tikzSource
        )
        router.updateTikZSource(updated)
        pendingConnectorLabel = ""
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
                label: pendingNodeLabel,
                to: router.tikzSource
            )
        )
        pendingNodeLabel = ""
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

    private func finishLabelEditing() {
        commitSelectedLabel()
        editingNodeName = nil
        editingEdgeID = nil
    }

    private func openSource() {
        sourceDraft = router.tikzSource
        showSource = true
    }

    private func openCanvasSizeEditor() {
        canvasWidthText =
            String(
                Int(
                    logicalCanvasSize
                        .width
                        .rounded()
                )
            )
        canvasHeightText =
            String(
                Int(
                    logicalCanvasSize
                        .height
                        .rounded()
                )
            )
        showCanvasEditor = true
    }

    private func applyCanvasSize() {
        guard
            let width = Double(
                canvasWidthText
            ),
            let height = Double(
                canvasHeightText
            )
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
            TikZSourceDependencyManager
                .ensuringRequiredLibraries(
                    in: router.tikzSource
                )
        guard normalized != router.tikzSource else {
            return
        }
        router.updateTikZSource(normalized)
    }

    private func syncCanvasSizeFromSource() {
        logicalCanvasSize =
            TikZCanvasMetadata.size(
                in: router.tikzSource
            )
    }

    private func autoLayout() {
        let positions =
            layoutService.positions(
                for: graph
            )
        router.updateTikZSource(
            TikZSourceEditor.applyPositions(
                positions,
                to: router.tikzSource
            )
        )
        clearSelection(
            resetTool: true
        )
    }

    private func clearSelection(
        resetTool: Bool
    ) {
        selectedNodeName = nil
        selectedEdgeID = nil
        editingNodeName = nil
        editingEdgeID = nil
        labelDraft = ""
        if resetTool {
            activeTool = .select
        }
    }
}
