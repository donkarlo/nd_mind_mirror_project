import SwiftUI
import UIKit

/// A UIKit-backed toolbar control with independent tap selection and long-press editing gestures.
struct SavedDrawingToolControl: UIViewRepresentable {
    let savedTool: SavedDrawingTool
    let isActive: Bool
    let onSelect: () -> Void
    let onEdit: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onSelect: onSelect, onEdit: onEdit)
    }

    func makeUIView(context: Context) -> UIButton {
        let button = UIButton(type: .system)
        button.imageView?.contentMode = .scaleAspectFit
        button.layer.cornerRadius = 8
        button.addTarget(context.coordinator, action: #selector(Coordinator.selectTool), for: .touchDown)

        let longPress = UILongPressGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.editTool(_:))
        )
        longPress.minimumPressDuration = 1.0
        longPress.allowableMovement = 12
        longPress.cancelsTouchesInView = true
        button.addGestureRecognizer(longPress)
        configure(button)
        return button
    }

    func updateUIView(_ button: UIButton, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onEdit = onEdit
        configure(button)
    }

    private func configure(_ button: UIButton) {
        let configuration = UIImage.SymbolConfiguration(pointSize: symbolPointSize, weight: symbolWeight)
        button.setImage(UIImage(systemName: symbolName, withConfiguration: configuration), for: .normal)
        button.tintColor = tintColor
        button.backgroundColor = isActive ? UIColor.systemBlue.withAlphaComponent(0.16) : UIColor.clear
        button.layer.borderWidth = isActive ? 2.5 : 0.75
        button.layer.borderColor = isActive
            ? UIColor.systemBlue.cgColor
            : UIColor.separator.withAlphaComponent(0.35).cgColor
        button.accessibilityLabel = accessibilityLabel
        button.accessibilityValue = isActive ? "Selected" : "Not selected"
        button.accessibilityHint = "Tap to select. Hold for settings."
    }

    private var symbolName: String {
        switch savedTool.kind {
        case .pencil: return "pencil"
        case .highlighter: return "highlighter"
        case .eraser: return savedTool.eraserMode == .whole ? "eraser.fill" : "eraser"
        case .lasso: return "lasso"
        }
    }

    private var tintColor: UIColor {
        if savedTool.kind == .eraser {
            return .label
        }
        return UIColor(Color(hex: savedTool.colorHex)).withAlphaComponent(CGFloat(savedTool.opacity))
    }

    private var symbolPointSize: CGFloat {
        if savedTool.kind == .eraser {
            return CGFloat(min(max(17.0 + savedTool.width * 0.08, 18.0), 29.0))
        }
        return CGFloat(min(max(16.0 + savedTool.width * 0.22, 18.0), 29.0))
    }

    private var accessibilityLabel: String {
        switch savedTool.kind {
        case .pencil: return "Pencil"
        case .highlighter: return "Highlighter"
        case .eraser: return "\(savedTool.eraserMode.title) eraser, \(Int(savedTool.width)) pixels"
        case .lasso: return "Lasso"
        }
    }

    private var symbolWeight: UIImage.SymbolWeight {
        if savedTool.width >= 40 { return .black }
        if savedTool.width >= 24 { return .bold }
        if savedTool.width >= 12 { return .semibold }
        if savedTool.width >= 5 { return .medium }
        return .regular
    }

    final class Coordinator: NSObject {
        var onSelect: () -> Void
        var onEdit: () -> Void

        init(onSelect: @escaping () -> Void, onEdit: @escaping () -> Void) {
            self.onSelect = onSelect
            self.onEdit = onEdit
        }

        @objc func selectTool() { onSelect() }

        @objc func editTool(_ recognizer: UILongPressGestureRecognizer) {
            guard recognizer.state == .began else { return }
            onEdit()
        }
    }
}
