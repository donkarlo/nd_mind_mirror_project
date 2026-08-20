import PencilKit
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var bridge: BridgeClient
    @State private var drawingTool: DrawingTool = .arrow
    @State private var showConnection = false
    @State private var showSource = false
    @State private var sourceDraft = ""

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        .sheet(isPresented: $showConnection) {
            ConnectionView()
                .environmentObject(bridge)
        }
        .sheet(isPresented: $showSource) {
            NavigationStack {
                TextEditor(text: $sourceDraft)
                    .font(.system(.body, design: .monospaced))
                    .padding(8)
                    .navigationTitle(bridge.selectedPath ?? "TikZ Source")
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { showSource = false }
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Apply") {
                                bridge.updateSource(sourceDraft)
                                showSource = false
                            }
                        }
                    }
            }
        }
        .onAppear {
            if !bridge.isConnected { showConnection = true }
        }
    }

    private var sidebar: some View {
        List(selection: Binding(
            get: { bridge.selectedPath },
            set: { if let path = $0 { bridge.openFile(path) } }
        )) {
            Section("Bridge") {
                Button {
                    showConnection = true
                } label: {
                    Label(bridge.isConnected ? "Connected" : "Connect", systemImage: bridge.isConnected ? "link.circle.fill" : "link.circle")
                }
                Button {
                    bridge.refreshFiles()
                } label: {
                    Label("Refresh files", systemImage: "arrow.clockwise")
                }
                .disabled(!bridge.isConnected)
            }
            Section("TikZ files") {
                ForEach(bridge.files, id: \.self) { path in
                    Text(path)
                        .font(.system(.caption, design: .monospaced))
                        .tag(Optional(path))
                }
            }
        }
        .navigationTitle("nd_tikz_sketch")
    }

    private var detail: some View {
        VStack(spacing: 0) {
            HStack {
                ForEach(DrawingTool.allCases) { tool in
                    Button {
                        drawingTool = tool
                    } label: {
                        Label(tool.rawValue, systemImage: tool.symbolName)
                            .labelStyle(.iconOnly)
                            .frame(width: 34, height: 34)
                            .background(drawingTool == tool ? Color.accentColor.opacity(0.16) : Color.clear)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .help(tool.rawValue)
                }
                Divider().frame(height: 24)
                Button {
                    sourceDraft = bridge.source
                    showSource = true
                } label: {
                    Label("Source", systemImage: "chevron.left.forwardslash.chevron.right")
                }
                .disabled(bridge.selectedPath == nil)
                Button {
                    bridge.requestRender()
                } label: {
                    Label("Render", systemImage: "play.fill")
                }
                .disabled(bridge.selectedPath == nil)
                Spacer()
                Text(bridge.status)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.bar)

            GeometryReader { proxy in
                let available = proxy.size
                let canvasSize = fittedCanvas(in: available)
                ZStack {
                    Color(uiColor: .secondarySystemBackground)
                    ZStack {
                        Color.white
                        if let image = bridge.previewImage {
                            Image(uiImage: image)
                                .resizable()
                                .scaledToFit()
                                .allowsHitTesting(false)
                        } else {
                            VStack(spacing: 12) {
                                Image(systemName: "scribble.variable")
                                    .font(.system(size: 44))
                                Text(bridge.selectedPath == nil ? "Choose a TikZ file" : "Waiting for rendered TikZ")
                                    .foregroundStyle(.secondary)
                            }
                        }
                        PencilCanvasView(
                            tool: drawingTool,
                            clearToken: bridge.clearCanvasToken,
                            onStrokeFinished: { points, size in
                                guard let command = TikZSourceEditor.command(
                                    for: drawingTool,
                                    rawPoints: points,
                                    canvasSize: size,
                                    source: bridge.source
                                ) else { return }
                                let newSource = TikZSourceEditor.appending(
                                    command: command,
                                    to: bridge.source
                                )
                                bridge.updateSource(newSource)
                            },
                            onHandwritingFinished: { strokes, size in
                                recognizeAndApplyHandwriting(strokes: strokes, canvasSize: size)
                            }
                        )
                    }
                    .frame(width: canvasSize.width, height: canvasSize.height)
                    .clipped()
                    .shadow(radius: 4, y: 2)
                }
            }
        }
        .navigationTitle(bridge.selectedPath?.split(separator: "/").last.map(String.init) ?? "TikZ Canvas")
        .navigationBarTitleDisplayMode(.inline)
    }

    @MainActor
    private func recognizeAndApplyHandwriting(strokes: [PKStroke], canvasSize: CGSize) {
        guard bridge.selectedPath != nil else { return }
        bridge.reportStatus("Recognizing handwriting…")
        do {
            let recognition = try HandwritingRecognizer.recognize(strokes: strokes)
            let edit = TikZSourceEditor.applyingRecognizedText(
                recognition,
                canvasSize: canvasSize,
                to: bridge.source
            )
            bridge.reportStatus(edit.summary + " — rendering…")
            bridge.updateSource(edit.source)
        } catch {
            bridge.reportStatus(error.localizedDescription)
        }
    }

    private func fittedCanvas(in size: CGSize) -> CGSize {
        let aspect = 16.0 / 11.0
        let widthFromHeight = size.height * aspect
        if widthFromHeight <= size.width {
            return CGSize(width: widthFromHeight, height: size.height)
        }
        return CGSize(width: size.width, height: size.width / aspect)
    }
}
