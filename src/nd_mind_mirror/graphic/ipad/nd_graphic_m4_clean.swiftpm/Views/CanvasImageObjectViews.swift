import UIKit

/// Renders editable image objects below PencilKit strokes.
final class CanvasImageObjectLayerView: UIView {
    private var objectViews: [UUID: UIImageView] = [:]

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        isUserInteractionEnabled = false
    }

    required init?(coder: NSCoder) {
        nil
    }

    func setObjects(_ objects: [CanvasImageObject]) {
        let ids = Set(objects.map(\.id))
        let staleIDs = objectViews.keys.filter { !ids.contains($0) }
        for id in staleIDs {
            objectViews[id]?.removeFromSuperview()
            objectViews.removeValue(forKey: id)
        }
        for object in objects {
            let view: UIImageView
            if let existing = objectViews[object.id] {
                view = existing
            } else {
                view = UIImageView()
                view.backgroundColor = .clear
                view.contentMode = .scaleAspectFit
                view.clipsToBounds = true
                addSubview(view)
                objectViews[object.id] = view
            }
            view.image = object.image
            view.frame = object.frame
        }
        for object in objects {
            if let view = objectViews[object.id] {
                bringSubviewToFront(view)
            }
        }
    }
}

/// Finger-only interaction layer for selecting, moving, and proportionally resizing bitmap objects.
/// Apple Pencil touches deliberately pass through to PencilKit.
final class CanvasImageObjectInteractionView: UIView, UIGestureRecognizerDelegate {
    enum Corner: Int, CaseIterable {
        case topLeft = 0
        case topRight = 1
        case bottomLeft = 2
        case bottomRight = 3
    }

    var onSelectionChanged: ((UUID?) -> Void)?
    var onPreviewObjectsChanged: (([CanvasImageObject]) -> Void)?
    var onCommit: (([CanvasImageObject], UUID?, String) -> Void)?

    private let borderLayer = CAShapeLayer()
    private let handles: [UIView]
    private let moveHandle = UIView()
    private var objects: [CanvasImageObject] = []
    private var selectedID: UUID?
    private var selectionEnabled = false
    private var zoomScale: CGFloat = 1.0
    private var gestureStartObjects: [CanvasImageObject] = []
    private var gestureStartFrame: CGRect = .zero
    private var gestureStartPoint: CGPoint = .zero

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
        borderLayer.fillColor = UIColor.clear.cgColor
        borderLayer.strokeColor = UIColor.systemOrange.cgColor
        layer.addSublayer(borderLayer)

        for handle in handles {
            addSubview(handle)
            let resize = UIPanGestureRecognizer(target: self, action: #selector(handleResize(_:)))
            resize.maximumNumberOfTouches = 1
            resize.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
            resize.delegate = self
            handle.addGestureRecognizer(resize)
        }

        moveHandle.backgroundColor = .systemOrange
        moveHandle.layer.borderColor = UIColor.white.cgColor
        moveHandle.layer.borderWidth = 1.5
        moveHandle.isUserInteractionEnabled = true
        addSubview(moveHandle)
        let move = UIPanGestureRecognizer(target: self, action: #selector(handleMove(_:)))
        move.maximumNumberOfTouches = 1
        move.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        move.delegate = self
        moveHandle.addGestureRecognizer(move)

        let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap(_:)))
        tap.numberOfTouchesRequired = 1
        tap.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        tap.cancelsTouchesInView = false
        tap.delegate = self
        addGestureRecognizer(tap)

        let bodyMove = UIPanGestureRecognizer(target: self, action: #selector(handleBodyMove(_:)))
        bodyMove.maximumNumberOfTouches = 1
        bodyMove.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        bodyMove.delegate = self
        addGestureRecognizer(bodyMove)
        updateSelectionAppearance()
    }

    required init?(coder: NSCoder) {
        nil
    }

    func setState(
        objects: [CanvasImageObject],
        selectedID: UUID?,
        selectionEnabled: Bool,
        zoomScale: CGFloat
    ) {
        self.objects = objects
        self.selectionEnabled = selectionEnabled
        self.zoomScale = max(zoomScale, 0.05)
        if let selectedID, objects.contains(where: { $0.id == selectedID }) {
            self.selectedID = selectedID
        } else {
            self.selectedID = nil
        }
        updateSelectionAppearance()
    }

    func updateZoom(_ zoomScale: CGFloat) {
        self.zoomScale = max(zoomScale, 0.05)
        setNeedsLayout()
    }

    func clearSelection(notify: Bool) {
        guard selectedID != nil else { return }
        selectedID = nil
        updateSelectionAppearance()
        if notify { onSelectionChanged?(nil) }
    }

    /// Selects the topmost image object enclosed or crossed by an Apple Pencil lasso polygon.
    func selectObject(inLasso polygon: [CGPoint]) {
        guard selectionEnabled, polygon.count >= 3 else { return }
        let hit = objects.reversed().first { object in
            let frame = object.frame
            let probes = [
                CGPoint(x: frame.midX, y: frame.midY),
                CGPoint(x: frame.minX, y: frame.minY),
                CGPoint(x: frame.maxX, y: frame.minY),
                CGPoint(x: frame.minX, y: frame.maxY),
                CGPoint(x: frame.maxX, y: frame.maxY),
            ]
            return probes.contains(where: { pointInPolygon($0, polygon: polygon) })
                || polygon.contains(where: { frame.contains($0) })
        }?.id
        selectedID = hit
        updateSelectionAppearance()
        onSelectionChanged?(hit)
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        borderLayer.frame = bounds
        guard selectionEnabled, let frame = selectedFrame else {
            borderLayer.path = nil
            handles.forEach { $0.isHidden = true }
            moveHandle.isHidden = true
            return
        }

        let scale = max(zoomScale, 0.05)
        borderLayer.lineWidth = max(1.8 / scale, 0.45)
        borderLayer.path = UIBezierPath(rect: frame).cgPath

        let diameter = 28.0 / scale
        for corner in Corner.allCases {
            let handle = handles[corner.rawValue]
            handle.isHidden = false
            handle.bounds = CGRect(x: 0, y: 0, width: diameter, height: diameter)
            handle.center = point(for: corner, in: frame)
            handle.layer.cornerRadius = diameter / 2
            handle.layer.borderWidth = max(1.6 / scale, 0.6)
        }

        let moveWidth = 54.0 / scale
        let moveHeight = 24.0 / scale
        moveHandle.isHidden = false
        moveHandle.bounds = CGRect(x: 0, y: 0, width: moveWidth, height: moveHeight)
        moveHandle.center = CGPoint(
            x: frame.midX,
            y: max(moveHeight / 2, frame.minY - 16.0 / scale)
        )
        moveHandle.layer.cornerRadius = moveHeight / 2
        moveHandle.layer.borderWidth = max(1.5 / scale, 0.6)
    }

    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        guard selectionEnabled, isDirectTouchEvent(event) else { return nil }

        if !moveHandle.isHidden {
            let local = moveHandle.convert(point, from: self)
            if moveHandle.point(inside: local, with: event) { return moveHandle }
        }
        for handle in handles.reversed() where !handle.isHidden {
            let local = handle.convert(point, from: self)
            if handle.point(inside: local, with: event) { return handle }
        }
        if objects.reversed().contains(where: { $0.frame.insetBy(dx: -6 / zoomScale, dy: -6 / zoomScale).contains(point) }) {
            return self
        }
        return nil
    }

    private var selectedFrame: CGRect? {
        guard let selectedID,
              let object = objects.first(where: { $0.id == selectedID }) else { return nil }
        return object.frame
    }

    private func updateSelectionAppearance() {
        setNeedsLayout()
    }

    private func selectObject(at point: CGPoint) -> UUID? {
        let hit = objects.reversed().first { object in
            object.frame.insetBy(dx: -6 / zoomScale, dy: -6 / zoomScale).contains(point)
        }?.id
        if selectedID != hit {
            selectedID = hit
            onSelectionChanged?(hit)
            updateSelectionAppearance()
        }
        return hit
    }

    @objc private func handleTap(_ recognizer: UITapGestureRecognizer) {
        guard recognizer.state == .ended, selectionEnabled else { return }
        _ = selectObject(at: recognizer.location(in: self))
    }

    @objc private func handleBodyMove(_ recognizer: UIPanGestureRecognizer) {
        guard selectionEnabled else { return }
        let point = recognizer.location(in: self)
        switch recognizer.state {
        case .began:
            guard let id = selectObject(at: point),
                  let frame = objects.first(where: { $0.id == id })?.frame else { return }
            gestureStartObjects = objects
            gestureStartFrame = frame
            gestureStartPoint = point
        case .changed, .ended:
            guard selectedID != nil, !gestureStartObjects.isEmpty else { return }
            let delta = CGPoint(x: point.x - gestureStartPoint.x, y: point.y - gestureStartPoint.y)
            applyMove(delta: delta)
            if recognizer.state == .ended {
                commitGesture(actionName: "Move Image")
            }
        case .cancelled, .failed:
            cancelGesture()
        default:
            break
        }
    }

    @objc private func handleMove(_ recognizer: UIPanGestureRecognizer) {
        guard selectionEnabled, let frame = selectedFrame else { return }
        let point = recognizer.location(in: self)
        switch recognizer.state {
        case .began:
            gestureStartObjects = objects
            gestureStartFrame = frame
            gestureStartPoint = point
        case .changed, .ended:
            guard !gestureStartObjects.isEmpty else { return }
            let delta = CGPoint(x: point.x - gestureStartPoint.x, y: point.y - gestureStartPoint.y)
            applyMove(delta: delta)
            if recognizer.state == .ended {
                commitGesture(actionName: "Move Image")
            }
        case .cancelled, .failed:
            cancelGesture()
        default:
            break
        }
    }

    private func applyMove(delta: CGPoint) {
        guard let selectedID,
              let index = gestureStartObjects.firstIndex(where: { $0.id == selectedID }) else { return }
        var frame = gestureStartFrame
        frame.origin.x = min(max(gestureStartFrame.origin.x + delta.x, 0), max(bounds.width - frame.width, 0))
        frame.origin.y = min(max(gestureStartFrame.origin.y + delta.y, 0), max(bounds.height - frame.height, 0))
        objects = gestureStartObjects
        objects[index].frame = frame
        onPreviewObjectsChanged?(objects)
        updateSelectionAppearance()
    }

    @objc private func handleResize(_ recognizer: UIPanGestureRecognizer) {
        guard selectionEnabled,
              let handle = recognizer.view,
              let corner = Corner(rawValue: handle.tag),
              let frame = selectedFrame else { return }
        let point = recognizer.location(in: self)
        switch recognizer.state {
        case .began:
            gestureStartObjects = objects
            gestureStartFrame = frame
            gestureStartPoint = point
        case .changed, .ended:
            guard !gestureStartObjects.isEmpty else { return }
            applyResize(corner: corner, point: point)
            if recognizer.state == .ended {
                commitGesture(actionName: "Resize Image")
            }
        case .cancelled, .failed:
            cancelGesture()
        default:
            break
        }
    }

    private func applyResize(corner: Corner, point: CGPoint) {
        guard let selectedID,
              let index = gestureStartObjects.firstIndex(where: { $0.id == selectedID }) else { return }
        let original = gestureStartFrame
        guard original.width > 0, original.height > 0 else { return }
        let fixed = self.point(for: opposite(corner), in: original)
        let rawWidth = abs(point.x - fixed.x)
        let rawHeight = abs(point.y - fixed.y)
        var scale = max(rawWidth / original.width, rawHeight / original.height)
        let minimumScale = max(24.0 / original.width, 24.0 / original.height)
        scale = max(scale, minimumScale)

        let availableWidth: CGFloat
        let availableHeight: CGFloat
        switch corner {
        case .topLeft:
            availableWidth = fixed.x
            availableHeight = fixed.y
        case .topRight:
            availableWidth = bounds.width - fixed.x
            availableHeight = fixed.y
        case .bottomLeft:
            availableWidth = fixed.x
            availableHeight = bounds.height - fixed.y
        case .bottomRight:
            availableWidth = bounds.width - fixed.x
            availableHeight = bounds.height - fixed.y
        }
        let maxScale = max(
            minimumScale,
            min(availableWidth / original.width, availableHeight / original.height)
        )
        scale = min(scale, maxScale)

        let size = CGSize(width: original.width * scale, height: original.height * scale)
        var frame = CGRect(origin: .zero, size: size)
        switch corner {
        case .topLeft:
            frame.origin = CGPoint(x: fixed.x - size.width, y: fixed.y - size.height)
        case .topRight:
            frame.origin = CGPoint(x: fixed.x, y: fixed.y - size.height)
        case .bottomLeft:
            frame.origin = CGPoint(x: fixed.x - size.width, y: fixed.y)
        case .bottomRight:
            frame.origin = fixed
        }

        objects = gestureStartObjects
        objects[index].frame = frame.standardized
        onPreviewObjectsChanged?(objects)
        updateSelectionAppearance()
    }

    private func commitGesture(actionName: String) {
        let finalObjects = objects
        gestureStartObjects = []
        onCommit?(finalObjects, selectedID, actionName)
    }

    private func cancelGesture() {
        guard !gestureStartObjects.isEmpty else { return }
        objects = gestureStartObjects
        gestureStartObjects = []
        onPreviewObjectsChanged?(objects)
        updateSelectionAppearance()
    }

    private func point(for corner: Corner, in frame: CGRect) -> CGPoint {
        switch corner {
        case .topLeft: return CGPoint(x: frame.minX, y: frame.minY)
        case .topRight: return CGPoint(x: frame.maxX, y: frame.minY)
        case .bottomLeft: return CGPoint(x: frame.minX, y: frame.maxY)
        case .bottomRight: return CGPoint(x: frame.maxX, y: frame.maxY)
        }
    }

    private func opposite(_ corner: Corner) -> Corner {
        switch corner {
        case .topLeft: return .bottomRight
        case .topRight: return .bottomLeft
        case .bottomLeft: return .topRight
        case .bottomRight: return .topLeft
        }
    }

    private func pointInPolygon(_ point: CGPoint, polygon: [CGPoint]) -> Bool {
        guard polygon.count >= 3 else { return false }
        var inside = false
        var j = polygon.count - 1
        for i in polygon.indices {
            let pi = polygon[i]
            let pj = polygon[j]
            let crosses = (pi.y > point.y) != (pj.y > point.y)
            if crosses {
                let denominator = pj.y - pi.y
                if abs(denominator) > 0.000_001 {
                    let x = (pj.x - pi.x) * (point.y - pi.y) / denominator + pi.x
                    if point.x < x { inside.toggle() }
                }
            }
            j = i
        }
        return inside
    }

    private func isDirectTouchEvent(_ event: UIEvent?) -> Bool {
        guard let touch = event?.allTouches?.first else { return true }
        return touch.type == .direct || touch.type == .indirectPointer
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        false
    }
}
