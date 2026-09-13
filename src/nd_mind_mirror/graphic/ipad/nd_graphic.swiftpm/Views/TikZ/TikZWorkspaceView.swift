// Complete TikZ tab: file loading, node dragging, edges, labels, shapes, source and auto layout.

import SwiftUI

struct TikZWorkspaceView: View {
    @ObservedObject var bridge: TikZBridgeClient
    @State private var columnVisibility: NavigationSplitViewVisibility = .detailOnly
    @State private var searchText = ""
    @State private var selectedNodeName: String?
    @State private var selectedEdgeID: String?
    @State private var edgeStartNodeName: String?
    @State private var isAddingEdge = false
    @State private var pendingEdgeLabel = ""
    @State private var labelDraft = ""
    @State private var sourceDraft = ""
    @State private var showSource = false
    @State private var showConnection = false
    private let layoutService = TikZAutoLayoutService()

    private var graph: TikZGraph { TikZGraphParser.parse(bridge.source) }
    private var filteredFiles: [String] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        return query.isEmpty ? bridge.files : bridge.files.filter { $0.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            sidebar
        } detail: {
            VStack(spacing: 0) {
                toolbar
                HStack(spacing: 0) {
                    TikZCanvasView(
                        graph: graph,
                        previewImage: bridge.previewImage,
                        selectedNodeName: selectedNodeName,
                        edgeStartNodeName: edgeStartNodeName,
                        onNodeTap: handleNodeTap,
                        onNodeMove: moveNode
                    )
                    inspector
                        .frame(width: 280)
                        .background(Color(uiColor: .secondarySystemBackground))
                }
                statusBar
            }
        }
        .sheet(isPresented: $showSource) {
            NavigationStack {
                TextEditor(text: $sourceDraft)
                    .font(.system(.body, design: .monospaced))
                    .padding(8)
                    .navigationTitle(bridge.selectedPath ?? "TikZ Source")
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) { Button("Cancel") { showSource = false } }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Apply") {
                                bridge.updateSource(sourceDraft)
                                showSource = false
                            }
                        }
                    }
            }
        }
        .sheet(isPresented: $showConnection) {
            NavigationStack {
                Form {
                    TextField("ws://computer.local:8765/ws", text: $bridge.serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button(bridge.isConnected ? "Reconnect" : "Connect") {
                        bridge.connect()
                        showConnection = false
                    }
                }
                .navigationTitle("TikZ bridge")
            }
        }
    }

    private var sidebar: some View {
        List(selection: Binding(
            get: { bridge.selectedPath },
            set: { path in
                if let path {
                    bridge.openFile(path)
                    clearSelection()
                }
            }
        )) {
            Section("Bridge") {
                Button { showConnection = true } label: {
                    Label(bridge.isConnected ? "Connected" : "Connection", systemImage: bridge.isConnected ? "link.circle.fill" : "link.circle")
                }
                Button { bridge.refreshFiles() } label: { Label("Refresh files", systemImage: "arrow.clockwise") }
                    .disabled(!bridge.isConnected)
            }
            Section("TikZ files") {
                Text("Optional browser for opening a TikZ file manually. Normal use starts from Create/Edit TikZ in Mind Mirror.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                TextField("Search", text: $searchText)
                ForEach(filteredFiles, id: \.self) { path in
                    Text(path)
                        .font(.system(.caption, design: .monospaced))
                        .tag(Optional(path))
                }
            }
        }
        .navigationTitle("TikZ Files")
    }

    private var toolbar: some View {
        HStack(spacing: 8) {
            Button { addNode(.rectangle) } label: { Label("Rectangle", systemImage: "rectangle") }
                .disabled(bridge.selectedPath == nil)
            Button { addNode(.ellipse) } label: { Label("Ellipse", systemImage: "circle") }
                .disabled(bridge.selectedPath == nil)
            Button {
                isAddingEdge = true
                edgeStartNodeName = nil
                selectedEdgeID = nil
                selectedNodeName = nil
            } label: {
                Label(isAddingEdge ? (edgeStartNodeName == nil ? "Choose source" : "Choose target") : "Add edge", systemImage: "arrow.triangle.branch")
            }
            .disabled(bridge.selectedPath == nil || graph.nodes.count < 2)
            TextField("New edge label", text: $pendingEdgeLabel)
                .textFieldStyle(.roundedBorder)
                .frame(width: 170)
            Divider().frame(height: 26)
            Button { autoLayout() } label: { Label("Auto layout", systemImage: "square.grid.3x3") }
                .disabled(graph.nodes.isEmpty)
            Button {
                sourceDraft = bridge.source
                showSource = true
            } label: { Label("Source", systemImage: "chevron.left.forwardslash.chevron.right") }
                .disabled(bridge.selectedPath == nil)
            Button { bridge.requestRender() } label: { Label("Render", systemImage: "play.fill") }
                .disabled(bridge.selectedPath == nil)
            Spacer()
        }
        .padding(.leading, 8)
        .padding(.trailing, 182)
        .padding(.vertical, 8)
        .background(.bar)
    }

    private var inspector: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Inspector").font(.headline)
            if let node = graph.nodes.first(where: { $0.name == selectedNodeName }) {
                Text("Node: \(node.name)").font(.caption.monospaced())
                TextField("Node label", text: $labelDraft)
                    .textFieldStyle(.roundedBorder)
                Button("Save node label") {
                    bridge.updateSource(TikZSourceEditor.updateNodeLabel(named: node.name, label: labelDraft, in: bridge.source))
                }
            } else if let edge = graph.edges.first(where: { $0.id == selectedEdgeID }) {
                Text("Edge: \(edge.source) → \(edge.target)").font(.caption.monospaced())
                TextField("Edge label", text: $labelDraft)
                    .textFieldStyle(.roundedBorder)
                Button("Save edge label") {
                    bridge.updateSource(TikZSourceEditor.updateEdgeLabel(edgeID: edge.id, label: labelDraft, in: bridge.source))
                }
            } else {
                Text("Tap a node to edit it or start a new edge.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Divider()
            Text("Edges").font(.subheadline.bold())
            ScrollView {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(graph.edges) { edge in
                        Button {
                            selectedEdgeID = edge.id
                            selectedNodeName = nil
                            edgeStartNodeName = nil
                            labelDraft = edge.label
                        } label: {
                            HStack {
                                Text("\(edge.source) → \(edge.target)")
                                    .font(.caption.monospaced())
                                Spacer()
                                Text(edge.label).font(.caption2).foregroundStyle(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            Spacer()
        }
        .padding(12)
    }

    private var statusBar: some View {
        HStack {
            Text(bridge.status).font(.caption).foregroundStyle(.secondary).lineLimit(1)
            Spacer()
            if let path = bridge.selectedPath {
                Text(path).font(.caption2.monospaced()).foregroundStyle(.secondary).lineLimit(1)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(Color(uiColor: .tertiarySystemBackground))
    }

    private func handleNodeTap(_ node: TikZNode) {
        if isAddingEdge {
            if let start = edgeStartNodeName {
                guard start != node.name else { return }
                bridge.updateSource(TikZSourceEditor.addEdge(from: start, to: node.name, label: pendingEdgeLabel, in: bridge.source))
                pendingEdgeLabel = ""
                edgeStartNodeName = nil
                isAddingEdge = false
                selectedNodeName = node.name
                labelDraft = node.label
            } else {
                edgeStartNodeName = node.name
            }
            return
        }
        selectedNodeName = node.name
        selectedEdgeID = nil
        labelDraft = node.label
    }

    private func moveNode(_ node: TikZNode, to point: CGPoint) {
        bridge.updateSource(TikZSourceEditor.moveNode(named: node.name, to: point, in: bridge.source))
    }

    private func addNode(_ shape: TikZNodeShape) {
        bridge.updateSource(TikZSourceEditor.addNode(shape: shape, at: CGPoint(x: 8, y: 5.5), to: bridge.source))
    }

    private func autoLayout() {
        let positions = layoutService.positions(for: graph)
        bridge.updateSource(TikZSourceEditor.applyPositions(positions, to: bridge.source))
        clearSelection()
    }

    private func clearSelection() {
        selectedNodeName = nil
        selectedEdgeID = nil
        edgeStartNodeName = nil
        isAddingEdge = false
        labelDraft = ""
    }
}
