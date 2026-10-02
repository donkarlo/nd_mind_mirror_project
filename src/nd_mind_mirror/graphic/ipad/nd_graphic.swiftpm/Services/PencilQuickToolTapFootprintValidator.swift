import PencilKit

/// Validates that a recognized quick-tool double tap produced only tiny dot-like strokes.
final class PencilQuickToolTapFootprintValidator {
    private let maximumAddedStrokeCount = 2
    private let minimumStrokeSpan: CGFloat = 10
    private let toolWidthMultiplier: CGFloat = 2.25

    func isTapLikeChange(
        before: PKDrawing,
        after: PKDrawing,
        toolWidth: Double
    ) -> Bool {
        let beforeCount = before.strokes.count
        let afterCount = after.strokes.count
        guard afterCount >= beforeCount else {
            return false
        }

        let addedCount = afterCount - beforeCount
        guard addedCount > 0,
              addedCount <= maximumAddedStrokeCount else {
            return false
        }
        let maximumSpan = max(
            minimumStrokeSpan,
            CGFloat(toolWidth) * toolWidthMultiplier
        )

        return after.strokes
            .suffix(addedCount)
            .allSatisfy { stroke in
                let bounds = stroke.renderBounds
                return max(bounds.width, bounds.height) <= maximumSpan
            }
    }
}
