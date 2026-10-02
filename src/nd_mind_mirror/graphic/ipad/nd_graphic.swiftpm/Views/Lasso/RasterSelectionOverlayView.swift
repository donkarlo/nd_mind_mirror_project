import UIKit

/// Displays and exposes interaction surfaces for one selected raster fragment.
final class RasterSelectionOverlayView: UIView {
    enum Corner: Int, CaseIterable {
        case topLeft = 0
        case topRight = 1
        case bottomLeft = 2
        case bottomRight = 3
    }

    private let borderLayer = CAShapeLayer()
    let handles: [UIView]
    let moveHandle = UIView()
    let moveSurface = UIView()
    private(set) var selectionBounds: CGRect?
    private var zoomScale: CGFloat = 1

    override init(frame: CGRect) {
        handles = Corner.allCases.map { corner in
            let handle = UIView()
            handle.tag = corner.rawValue
            handle.backgroundColor = .systemBackground
            handle.layer.borderColor = UIColor.systemOrange.cgColor
            handle.isUserInteractionEnabled = true
            return handle
        }
        super.init(frame: frame)

        backgroundColor = .clear
        isOpaque = false
        isHidden = true
        borderLayer.fillColor = UIColor.clear.cgColor
        borderLayer.strokeColor = UIColor.systemOrange.cgColor
        layer.addSublayer(borderLayer)

        moveSurface.backgroundColor = .clear
        moveSurface.isUserInteractionEnabled = true
        addSubview(moveSurface)

        for handle in handles {
            addSubview(handle)
        }

        moveHandle.backgroundColor = UIColor.systemGray3.withAlphaComponent(0.68)
        moveHandle.layer.borderColor = UIColor.systemGray5.cgColor
        moveHandle.isUserInteractionEnabled = true
        addSubview(moveHandle)
    }

    required init?(coder: NSCoder) {
        nil
    }

    func setSelection(bounds: CGRect, zoomScale: CGFloat) {
        selectionBounds = bounds.standardized
        self.zoomScale = max(zoomScale, 0.05)
        isHidden = false
        setNeedsLayout()
    }

    func updateZoom(_ zoomScale: CGFloat) {
        self.zoomScale = max(zoomScale, 0.05)
        if selectionBounds != nil {
            setNeedsLayout()
        }
    }

    func clearSelection() {
        selectionBounds = nil
        isHidden = true
        borderLayer.path = nil
    }

    func cornerPoint(_ corner: Corner) -> CGPoint? {
        guard let bounds = selectionBounds else { return nil }
        switch corner {
        case .topLeft:
            return CGPoint(x: bounds.minX, y: bounds.minY)
        case .topRight:
            return CGPoint(x: bounds.maxX, y: bounds.minY)
        case .bottomLeft:
            return CGPoint(x: bounds.minX, y: bounds.maxY)
        case .bottomRight:
            return CGPoint(x: bounds.maxX, y: bounds.maxY)
        }
    }

    func containsSelectionInteraction(at point: CGPoint) -> Bool {
        guard !isHidden, let selectionBounds else { return false }
        if selectionBounds.contains(point) {
            return true
        }

        let movePoint = moveHandle.convert(point, from: self)
        if moveHandle.point(inside: movePoint, with: nil) {
            return true
        }
        return handles.contains { handle in
            let local = handle.convert(point, from: self)
            return handle.point(inside: local, with: nil)
        }
    }

    static func opposite(_ corner: Corner) -> Corner {
        switch corner {
        case .topLeft: return .bottomRight
        case .topRight: return .bottomLeft
        case .bottomLeft: return .topRight
        case .bottomRight: return .topLeft
        }
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        guard let bounds = selectionBounds else { return }
        let scale = max(zoomScale, 0.05)

        borderLayer.frame = self.bounds
        borderLayer.lineWidth = max(1.8 / scale, 0.45)
        borderLayer.path = UIBezierPath(rect: bounds).cgPath
        moveSurface.frame = bounds

        let handleDiameter = 28.0 / scale
        for corner in Corner.allCases {
            let handle = handles[corner.rawValue]
            guard let center = cornerPoint(corner) else { continue }
            handle.bounds = CGRect(
                x: 0,
                y: 0,
                width: handleDiameter,
                height: handleDiameter
            )
            handle.center = center
            handle.layer.cornerRadius = handleDiameter / 2
            handle.layer.borderWidth = max(1.6 / scale, 0.6)
        }

        let moveWidth = 34.0 / scale
        let moveHeight = 18.0 / scale
        moveHandle.bounds = CGRect(x: 0, y: 0, width: moveWidth, height: moveHeight)
        moveHandle.center = CGPoint(
            x: bounds.midX,
            y: max(moveHeight / 2, bounds.minY - 13.0 / scale)
        )
        moveHandle.layer.cornerRadius = moveHeight / 2
        moveHandle.layer.borderWidth = max(1.0 / scale, 0.5)
    }

    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        guard !isHidden, let selectionBounds else { return nil }

        let movePoint = moveHandle.convert(point, from: self)
        if moveHandle.point(inside: movePoint, with: event) {
            return moveHandle
        }
        for handle in handles.reversed() {
            let local = handle.convert(point, from: self)
            if handle.point(inside: local, with: event) {
                return handle
            }
        }
        if selectionBounds.contains(point) {
            return moveSurface
        }
        return nil
    }
}
