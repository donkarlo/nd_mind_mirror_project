"""Idempotent iPad source updates applied directly to the canonical Swift package.

This module never creates backup files or numbered package copies.  It only
patches known source fragments in-place and writes canonical support files.
"""

from __future__ import annotations

from pathlib import Path
import re


class IpadSourceHotfixMigration:
    """Apply current ND Graphic behavior without rebuilding source from legacy templates."""

    VERSION = "0.31.11"
    BUNDLE_VERSION = "41"

    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = False
        changed |= self._write_history_support()
        changed |= self._write_measurement_grid()
        changed |= self._patch_content_view()
        changed |= self._patch_pencil_canvas()
        changed |= self._patch_bridge_client()
        changed |= self._patch_package_version()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, updated: str) -> bool:
        original = path.read_text(encoding="utf-8") if path.is_file() else ""
        if updated == original:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        return True

    @staticmethod
    def _replace_once(text: str, old: str, new: str) -> str:
        if old not in text:
            return text
        return text.replace(old, new, 1)

    def _write_history_support(self) -> bool:
        """Provide persistent recent-image and recent tool-setting stores."""
        path = self.source_root / "Services" / "RecentGraphicAndToolHistory.swift"
        desired = '''import Foundation
import SwiftUI

/// One recently edited graphic shown from the source/image identity menu.
struct RecentGraphicItem: Codable, Hashable, Identifiable {
    let path: String
    let label: String
    var id: String { path }
}

/// One recent pencil/highlighter combination.
struct RecentToolPreset: Codable, Hashable, Identifiable {
    let colorHex: String
    let width: Double
    var id: String { "\\(colorHex.lowercased())|\\(String(format: "%.2f", width))" }
}

/// Persists the ten most recent color/width combinations separately per inking tool.
@MainActor
final class RecentToolPresetStore: ObservableObject {
    @Published private(set) var revision = 0
    private let defaults = UserDefaults.standard
    private let limit = 10

    func presets(for tool: GraphicTool) -> [RecentToolPreset] {
        guard tool.supportsColor && tool.supportsWidth else { return [] }
        let key = "graphic.recent.tool.presets.\\(tool.storageKey)"
        guard let data = defaults.data(forKey: key),
              let values = try? JSONDecoder().decode([RecentToolPreset].self, from: data) else {
            return []
        }
        return Array(values.prefix(limit))
    }

    func remember(color: Color, width: Double, for tool: GraphicTool) {
        remember(hex: color.hexRGB(), width: width, for: tool)
    }

    func remember(hex: String, width: Double, for tool: GraphicTool) {
        guard tool.supportsColor && tool.supportsWidth else { return }
        let normalized = hex.uppercased()
        let boundedWidth = max(width, 0.1)
        let value = RecentToolPreset(colorHex: normalized, width: boundedWidth)
        var values = presets(for: tool)
        values.removeAll {
            $0.colorHex.caseInsensitiveCompare(normalized) == .orderedSame
                && abs($0.width - boundedWidth) < 0.01
        }
        values.insert(value, at: 0)
        values = Array(values.prefix(limit))
        let key = "graphic.recent.tool.presets.\\(tool.storageKey)"
        if let data = try? JSONEncoder().encode(values) {
            defaults.set(data, forKey: key)
            revision &+= 1
        }
    }
}

/// Persists the ten most recently edited bridge graphics.
enum RecentGraphicStore {
    private static let key = "graphic.recent.edited.graphics"
    private static let limit = 10

    static func load() -> [RecentGraphicItem] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let values = try? JSONDecoder().decode([RecentGraphicItem].self, from: data) else {
            return []
        }
        return Array(values.prefix(limit))
    }

    @discardableResult
    static func remember(path: String, label: String) -> [RecentGraphicItem] {
        guard !path.isEmpty else { return load() }
        var values = load()
        values.removeAll { $0.path == path }
        values.insert(RecentGraphicItem(path: path, label: label), at: 0)
        values = Array(values.prefix(limit))
        if let data = try? JSONEncoder().encode(values) {
            UserDefaults.standard.set(data, forKey: key)
        }
        return values
    }
}
'''
        return self._write_if_changed(path, desired)

    def _write_measurement_grid(self) -> bool:
        """Keep Grid and Ruler independently switchable while remaining view-only."""
        path = self.source_root / "Views" / "MeasurementGridView.swift"
        desired = '''import UIKit

/// View-only measurement overlay with independently switchable grid and rulers.
final class MeasurementGridView: UIView {
    private static let pixelsPerCentimeter: CGFloat = 1240.0 / 21.0
    private static let halfCentimeterSpacing: CGFloat = pixelsPerCentimeter / 2.0
    private static let rulerBand: CGFloat = 30.0
    private static let minorTickLength: CGFloat = 10.0
    private static let majorTickLength: CGFloat = 18.0

    var showGrid = true {
        didSet { if oldValue != showGrid { setNeedsDisplay() } }
    }
    var showRulers = true {
        didSet { if oldValue != showRulers { setNeedsDisplay() } }
    }

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        isOpaque = false
        isUserInteractionEnabled = false
        contentMode = .redraw
    }

    required init?(coder: NSCoder) { nil }

    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        context.saveGState()
        defer { context.restoreGState() }
        let spacing = Self.halfCentimeterSpacing
        guard spacing > 0 else { return }
        if showGrid { drawGrid(in: context, spacing: spacing) }
        if showRulers { drawRulers(in: context, spacing: spacing) }
    }

    private func drawGrid(in context: CGContext, spacing: CGFloat) {
        var index = 0
        var x: CGFloat = 0
        while x <= bounds.width + 0.5 {
            let major = index.isMultiple(of: 2)
            context.setStrokeColor(UIColor.systemGray.withAlphaComponent(major ? 0.20 : 0.10).cgColor)
            context.setLineWidth(major ? 0.95 : 0.55)
            context.move(to: CGPoint(x: x, y: 0))
            context.addLine(to: CGPoint(x: x, y: bounds.height))
            context.strokePath()
            index += 1
            x = CGFloat(index) * spacing
        }
        index = 0
        var y: CGFloat = 0
        while y <= bounds.height + 0.5 {
            let major = index.isMultiple(of: 2)
            context.setStrokeColor(UIColor.systemGray.withAlphaComponent(major ? 0.20 : 0.10).cgColor)
            context.setLineWidth(major ? 0.95 : 0.55)
            context.move(to: CGPoint(x: 0, y: y))
            context.addLine(to: CGPoint(x: bounds.width, y: y))
            context.strokePath()
            index += 1
            y = CGFloat(index) * spacing
        }
    }

    private func drawRulers(in context: CGContext, spacing: CGFloat) {
        let bandColor = UIColor.systemGray6.withAlphaComponent(0.88)
        context.setFillColor(bandColor.cgColor)
        context.fill(CGRect(x: 0, y: 0, width: bounds.width, height: Self.rulerBand))
        context.fill(CGRect(x: 0, y: 0, width: Self.rulerBand, height: bounds.height))

        context.setStrokeColor(UIColor.secondaryLabel.withAlphaComponent(0.72).cgColor)
        context.setLineWidth(1.25)
        context.move(to: CGPoint(x: 0, y: Self.rulerBand))
        context.addLine(to: CGPoint(x: bounds.width, y: Self.rulerBand))
        context.move(to: CGPoint(x: Self.rulerBand, y: 0))
        context.addLine(to: CGPoint(x: Self.rulerBand, y: bounds.height))
        context.strokePath()

        let textAttributes: [NSAttributedString.Key: Any] = [
            .font: UIFont.monospacedDigitSystemFont(ofSize: 11, weight: .medium),
            .foregroundColor: UIColor.secondaryLabel.withAlphaComponent(0.92),
        ]

        var index = 0
        var x: CGFloat = 0
        while x <= bounds.width + 0.5 {
            let major = index.isMultiple(of: 2)
            let length = major ? Self.majorTickLength : Self.minorTickLength
            context.setStrokeColor(UIColor.label.withAlphaComponent(major ? 0.72 : 0.46).cgColor)
            context.setLineWidth(major ? 1.25 : 0.85)
            context.move(to: CGPoint(x: x, y: Self.rulerBand))
            context.addLine(to: CGPoint(x: x, y: Self.rulerBand - length))
            context.strokePath()
            if major && index > 0 {
                NSString(string: "\\(index / 2)").draw(at: CGPoint(x: x + 3, y: 3), withAttributes: textAttributes)
            }
            index += 1
            x = CGFloat(index) * spacing
        }

        index = 0
        var y: CGFloat = 0
        while y <= bounds.height + 0.5 {
            let major = index.isMultiple(of: 2)
            let length = major ? Self.majorTickLength : Self.minorTickLength
            context.setStrokeColor(UIColor.label.withAlphaComponent(major ? 0.72 : 0.46).cgColor)
            context.setLineWidth(major ? 1.25 : 0.85)
            context.move(to: CGPoint(x: Self.rulerBand, y: y))
            context.addLine(to: CGPoint(x: Self.rulerBand - length, y: y))
            context.strokePath()
            if major && index > 0 {
                NSString(string: "\\(index / 2)").draw(at: CGPoint(x: 3, y: y + 2), withAttributes: textAttributes)
            }
            index += 1
            y = CGFloat(index) * spacing
        }
    }
}
'''
        return self._write_if_changed(path, desired)

    def _patch_content_view(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original.replace("ND Graphic v0.30.10", f"ND Graphic v{self.VERSION}")

        marker = "    @StateObject private var recentColors = RecentPencilColors()\n"
        if "RecentToolPresetStore" not in text and marker in text:
            text = text.replace(
                marker,
                marker
                + "    @StateObject private var recentPresets = RecentToolPresetStore()\n"
                + "    @State private var recentGraphics: [RecentGraphicItem] = RecentGraphicStore.load()\n"
                + "    @AppStorage(\"graphic.last.canvas.width\") private var rememberedCanvasWidth: Double = 1240\n"
                + "    @AppStorage(\"graphic.last.canvas.height\") private var rememberedCanvasHeight: Double = 1754\n",
                1,
            )

        text = self._replace_once(
            text,
            "    @State private var showRecentColors = false\n",
            "    @State private var showRecentColors = false\n    @State private var showToolPresets = false\n",
        )
        text = self._replace_once(
            text,
            "    @State private var showMeasurementGrid = true\n",
            "    @State private var showMeasurementGrid = true\n    @State private var showMeasurementRulers = true\n",
        )

        document_pattern = re.compile(
            r"        \.onChange\(of: bridge\.documentToken\) \{ _, token in\n.*?\n        \}\n        \.onChange\(of: tool\)",
            re.S,
        )
        document_replacement = '''        .onChange(of: bridge.documentToken) { _, token in
            guard token != localToken else { return }
            localToken = token
            localDrawing = bridge.drawing
            backgroundImage = GraphicDocumentStore.backgroundImage(from: bridge.document)

            if bridge.currentOperation == "insert" {
                canvasWidth = max(rememberedCanvasWidth.rounded(), 64)
                canvasHeight = max(rememberedCanvasHeight.rounded(), 64)
            } else {
                if let width = bridge.document?.canvasWidth, width > 0 {
                    canvasWidth = Double(width)
                }
                if let height = bridge.document?.canvasHeight, height > 0 {
                    canvasHeight = Double(height)
                }
            }
            canvasWidthText = String(Int(canvasWidth))
            canvasHeightText = String(Int(canvasHeight))
            rememberedCanvasWidth = canvasWidth
            rememberedCanvasHeight = canvasHeight

            canvasToken += 1
            if let remotePencil = bridge.document?.pencil {
                if let width = remotePencil.width { pencil.width = width }
                if let color = remotePencil.color {
                    pencil.color = Color(hex: color)
                    recentColors.remember(hex: color, for: tool)
                    recentPresets.remember(hex: color, width: pencil.width, for: tool)
                }
            }
            rememberCurrentGraphic()
            zoom100RequestToken &+= 1

            if bridge.currentOperation == "insert" {
                DispatchQueue.main.async {
                    bridge.save(
                        drawing: localDrawing,
                        backgroundImage: backgroundImage,
                        logicalCanvasSize: logicalCanvasSize,
                        pencil: pencil
                    )
                }
            }
        }
        .onChange(of: tool)'''
        text, _ = document_pattern.subn(document_replacement, text, count=1)

        old_tool_change = '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            if !newTool.supportsColor {
                showRecentColors = false
            }
        }
'''
        new_tool_change = '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            showRecentColors = false
            if !newTool.supportsColor {
                showToolPresets = false
            } else {
                recentPresets.remember(color: pencil.color, width: pencil.width, for: newTool)
            }
        }
        .onChange(of: pencil.width) { _, newWidth in
            if tool.supportsWidth {
                recentPresets.remember(color: pencil.color, width: newWidth, for: tool)
            }
        }
'''
        text = self._replace_once(text, old_tool_change, new_tool_change)

        text = self._replace_once(
            text,
            "                showMeasurementGrid: showMeasurementGrid,\n                zoom100RequestToken: zoom100RequestToken,",
            "                showMeasurementGrid: showMeasurementGrid,\n                showMeasurementRulers: showMeasurementRulers,\n                zoom100RequestToken: zoom100RequestToken,",
        )

        old_overlay_button = '''                Button {
                    showMeasurementGrid.toggle()
                } label: {
                    Label(showMeasurementGrid ? "Ruler" : "Ruler off", systemImage: "ruler")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Show or hide the 0.5 cm grid and the top/left centimeter rulers")
'''
        new_overlay_buttons = '''                Button {
                    showMeasurementGrid.toggle()
                } label: {
                    Label(showMeasurementGrid ? "Grid" : "Grid off", systemImage: "grid")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Show or hide the 0.5 cm measurement grid")

                Button {
                    showMeasurementRulers.toggle()
                } label: {
                    Label(showMeasurementRulers ? "Ruler" : "Ruler off", systemImage: "ruler")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Show or hide the top and left centimeter rulers")
'''
        text = self._replace_once(text, old_overlay_button, new_overlay_buttons)

        picker_anchor = '''                .pickerStyle(.segmented)
                .frame(width: 184)
                .accessibilityLabel("Drawing tool")
'''
        if "recentToolPresetPopover" not in text.split("private var toolbar", 1)[1].split("private var canvasStatusBar", 1)[0]:
            text = self._replace_once(
                text,
                picker_anchor,
                picker_anchor
                + '''                .simultaneousGesture(
                    TapGesture(count: 2).onEnded {
                        if tool.supportsColor && tool.supportsWidth {
                            showToolPresets = true
                        }
                    }
                )
                .popover(isPresented: $showToolPresets, arrowEdge: .top) {
                    recentToolPresetPopover
                }
''',
            )

        old_recent_button = '''                    Button {
                        showRecentColors.toggle()
                    } label: {
                        Image(systemName: showRecentColors ? "circle.grid.3x3.fill" : "circle.grid.3x3")
                            .frame(width: 28, height: 28)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("Recent colors")
                    .popover(isPresented: $showRecentColors, arrowEdge: .top) {
                        recentColorGrid
                    }
'''
        text = text.replace(old_recent_button, "", 1)

        current_canvas_anchor = '''                Menu {
                    Button("A4 portrait — 21 × 29.7 cm — 1240 × 1754") { setCanvasSize(width: 1240, height: 1754) }
'''
        current_canvas_new = '''                Menu {
                    Text("Current • \\(Int(canvasWidth)) × \\(Int(canvasHeight)) px")
                        .foregroundStyle(.blue)
                    Divider()
                    Button("A4 portrait — 21 × 29.7 cm — 1240 × 1754") { setCanvasSize(width: 1240, height: 1754) }
'''
        text = self._replace_once(text, current_canvas_anchor, current_canvas_new)

        status_pattern = re.compile(
            r'''            if let sourceName = bridge\.document\?\.sourceName,\n               let imageName = bridge\.document\?\.imageName \{\n.*?            \}\n            Menu \{\n                Button\("100%"\)''',
            re.S,
        )
        status_replacement = '''            Menu {
                if recentGraphics.isEmpty {
                    Text("No recent graphics")
                } else {
                    ForEach(recentGraphics) { item in
                        Button(item.label) {
                            bridge.requestOpen(path: item.path)
                        }
                    }
                }
            } label: {
                Text(activeGraphicLabel)
                    .font(.caption2.weight(.semibold))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            .help("Open one of the ten most recently edited graphics")

            Menu {
                Button("100%")'''
        text, _ = status_pattern.subn(status_replacement, text, count=1)

        text = re.sub(
            r'\n\s*Text\("Canvas \\\(Int\(canvasWidth\)\) × \\\(Int\(canvasHeight\)\) px"\)',
            "",
            text,
            count=1,
        )
        text = text.replace(".keyboardType(.numberPad)", ".keyboardType(.asciiCapableNumberPad)")

        old_binding = '''            set: { newColor in
                pencil.color = newColor
                recentColors.remember(newColor, for: tool)
            }
'''
        new_binding = '''            set: { newColor in
                pencil.color = newColor
                recentColors.remember(newColor, for: tool)
                recentPresets.remember(color: newColor, width: pencil.width, for: tool)
            }
'''
        text = self._replace_once(text, old_binding, new_binding)

        helper_marker = '''    private var logicalCanvasSize: CGSize {
'''
        if "private var activeGraphicLabel" not in text and helper_marker in text:
            helpers = '''    private var activeGraphicLabel: String {
        if let sourceName = bridge.document?.sourceName,
           let imageName = bridge.document?.imageName {
            return "\\(sourceName) > \\(imageName)"
        }
        if let imageName = bridge.document?.imageName { return imageName }
        if let path = bridge.selectedPath { return URL(fileURLWithPath: path).lastPathComponent }
        return "Graphic"
    }

    private var minimumCanvasSize: CGSize {
        let bounds = localDrawing.bounds
        return CGSize(
            width: max(64, ceil(max(bounds.maxX, 0) + 8)),
            height: max(64, ceil(max(bounds.maxY, 0) + 8))
        )
    }

    private func rememberCurrentGraphic() {
        guard let path = bridge.selectedPath else { return }
        recentGraphics = RecentGraphicStore.remember(path: path, label: activeGraphicLabel)
    }

    private var recentToolPresetPopover: some View {
        let presets = recentPresets.presets(for: tool)
        return VStack(alignment: .leading, spacing: 8) {
            Text(tool == .highlighter ? "Recent highlighter settings" : "Recent pencil settings")
                .font(.caption.bold())
            if presets.isEmpty {
                Text("No recent settings yet")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(presets) { preset in
                    Button {
                        pencil.color = Color(hex: preset.colorHex)
                        pencil.width = preset.width
                        recentPresets.remember(hex: preset.colorHex, width: preset.width, for: tool)
                        showToolPresets = false
                    } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(Color(hex: preset.colorHex))
                                .frame(width: 104, height: max(3, min(12, preset.width * 0.55)))
                            Text("Width \\(String(format: "%.1f", preset.width))")
                                .font(.caption2.monospacedDigit())
                                .foregroundStyle(.primary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(12)
        .frame(width: 190)
    }

'''
            text = text.replace(helper_marker, helpers + helper_marker, 1)

        old_set_canvas = '''    /// Applies a bounded canvas size without replacing the current drawing/background state.
    private func setCanvasSize(width: Double, height: Double) {
        canvasWidth = min(max(width.rounded(), 64), 8192)
        canvasHeight = min(max(height.rounded(), 64), 8192)
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        bridge.save(
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize,
            pencil: pencil
        )
    }
'''
        new_set_canvas = '''    /// Resizes the logical canvas without clipping existing PencilKit strokes.
    private func setCanvasSize(width: Double, height: Double) {
        let requestedWidth = max(width.rounded(), 64)
        let requestedHeight = max(height.rounded(), 64)
        let minimum = minimumCanvasSize
        guard requestedWidth >= minimum.width && requestedHeight >= minimum.height else {
            bridge.status = "Canvas cannot be smaller than the graphic (minimum \\(Int(ceil(minimum.width))) × \\(Int(ceil(minimum.height))) px)"
            return
        }
        canvasWidth = requestedWidth
        canvasHeight = requestedHeight
        canvasWidthText = String(Int(canvasWidth))
        canvasHeightText = String(Int(canvasHeight))
        rememberedCanvasWidth = canvasWidth
        rememberedCanvasHeight = canvasHeight
        bridge.save(
            drawing: localDrawing,
            backgroundImage: backgroundImage,
            logicalCanvasSize: logicalCanvasSize,
            pencil: pencil
        )
        zoom100RequestToken &+= 1
    }
'''
        text = self._replace_once(text, old_set_canvas, new_set_canvas)

        return self._write_if_changed(path, text)

    def _patch_pencil_canvas(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        text = self._replace_once(
            text,
            "    let showMeasurementGrid: Bool\n    let zoom100RequestToken: Int\n",
            "    let showMeasurementGrid: Bool\n    let showMeasurementRulers: Bool\n    let zoom100RequestToken: Int\n",
        )

        text = text.replace(
            "        measurementGrid.isHidden = !showMeasurementGrid\n",
            "        measurementGrid.showGrid = showMeasurementGrid\n"
            "        measurementGrid.showRulers = showMeasurementRulers\n"
            "        measurementGrid.isHidden = !showMeasurementGrid && !showMeasurementRulers\n",
        )
        text = text.replace(
            "        coordinator.measurementGridView?.isHidden = !showMeasurementGrid\n",
            "        coordinator.measurementGridView?.showGrid = showMeasurementGrid\n"
            "        coordinator.measurementGridView?.showRulers = showMeasurementRulers\n"
            "        coordinator.measurementGridView?.isHidden = !showMeasurementGrid && !showMeasurementRulers\n",
        )

        canvas_anchor = "        canvas.isScrollEnabled = false\n        canvas.bounces = false\n"
        if "canvas.contentSize = logicalCanvasSize" not in text.split(canvas_anchor, 1)[1][:500] if canvas_anchor in text else False:
            text = self._replace_once(
                text,
                canvas_anchor,
                "        canvas.isScrollEnabled = false\n"
                "        canvas.bounces = false\n"
                "        canvas.contentInset = .zero\n"
                "        canvas.contentOffset = .zero\n"
                "        canvas.contentSize = logicalCanvasSize\n"
                "        canvas.minimumZoomScale = 1.0\n"
                "        canvas.maximumZoomScale = 1.0\n"
                "        canvas.zoomScale = 1.0\n",
            )

        size_anchor = "            coordinator.canvas?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
        if size_anchor in text and "coordinator.canvas?.contentSize = logicalCanvasSize" not in text:
            text = text.replace(
                size_anchor,
                size_anchor
                + "            coordinator.canvas?.contentSize = logicalCanvasSize\n"
                + "            coordinator.canvas?.contentInset = .zero\n"
                + "            coordinator.canvas?.contentOffset = .zero\n",
                1,
            )

        # A new/opened/resized document starts at logical 100% rather than an automatic fit.
        text = text.replace("fitCanvas(reset: true)", "setZoomTo100Percent()")

        text = self._replace_once(
            text,
            "            scroll.setZoomScale(1.0, animated: false)\n            centerCanvas()\n",
            "            scroll.setZoomScale(1.0, animated: false)\n"
            "            scroll.contentInset = .zero\n"
            "            scroll.contentOffset = .zero\n",
        )
        text = self._replace_once(
            text,
            "            scroll.setZoomScale(1.0, animated: false)\n",
            "            scroll.setZoomScale(1.0, animated: false)\n"
            "            scroll.contentInset = .zero\n"
            "            scroll.contentOffset = .zero\n",
        )

        return self._write_if_changed(path, text)

    def _patch_bridge_client(self) -> bool:
        path = self.source_root / "Services" / "GraphicBridgeClient.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original.replace('"version": "0.30.10"', f'"version": "{self.VERSION}"')
        marker = '''    /// Encodes one line-delimited JSON object and writes it to the accepted connection.
    private func send(_ object: [String: Any]) {
'''
        if "func requestOpen(path:" not in text and marker in text:
            addition = '''    /// Requests one of the locally remembered bridge graphics from Ubuntu.
    func requestOpen(path: String) {
        guard !path.isEmpty else { return }
        send(["type": "open_recent_graphic", "path": path])
    }

'''
            text = text.replace(marker, addition + marker, 1)
        return self._write_if_changed(path, text)

    def _patch_package_version(self) -> bool:
        path = self.source_root / "Package.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = re.sub(r'displayVersion: "[^"]+"', f'displayVersion: "{self.VERSION}"', original, count=1)
        text = re.sub(r'bundleVersion: "[^"]+"', f'bundleVersion: "{self.BUNDLE_VERSION}"', text, count=1)
        return self._write_if_changed(path, text)
