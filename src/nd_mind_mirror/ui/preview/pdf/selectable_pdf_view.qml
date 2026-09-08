import QtQuick
import QtQuick.Controls

SelectablePdfViewBoundary {
    id: root

    property int savedPageIndex: 0
    property int pageRestoreAttempts: 0

    function captureScrollState() {
        var bounds = currentPageScrollBounds()
        if (!bounds) {
            root.restorePositionPending = false
            return
        }

        root.savedPageIndex = Math.max(root.currentPageIndex, 0)
        root.savedPageHorizontalRatio = 0.0
        root.savedPageVerticalRatio = 0.0

        var horizontalRange = bounds.maximumX - bounds.minimumX
        var verticalRange = bounds.maximumY - bounds.minimumY
        if (horizontalRange > 0.5) {
            root.savedPageHorizontalRatio = clampValue(
                (bounds.target.contentX - bounds.minimumX) / horizontalRange,
                0.0,
                1.0
            )
        }
        if (verticalRange > 0.5) {
            root.savedPageVerticalRatio = clampValue(
                (bounds.target.contentY - bounds.minimumY) / verticalRange,
                0.0,
                1.0
            )
        }

        root.savedRenderScale = root.safeScale(root.zoomScale)
        root.pageRestoreAttempts = 0
        root.restorePositionPending = true
    }

    function restoreScrollState() {
        if (!root.restorePositionPending)
            return

        if (root.savedRenderScale > 0)
            root.zoomScale = root.savedRenderScale

        var desiredPage = Math.max(root.savedPageIndex, 0)
        if (root.pageCount > 0)
            desiredPage = Math.min(desiredPage, root.pageCount - 1)

        if (root.pageCount > 0 &&
                root.currentPageIndex !== desiredPage &&
                root.pageRestoreAttempts < 8) {
            root.syncPage = desiredPage
            root.syncX = 0
            root.syncY = 0
            root.syncRecenterHorizontal = false
            root.syncToken += 1
            root.pageRestoreAttempts += 1
            pageRestoreRetry.restart()
            return
        }

        var bounds = currentPageScrollBounds()
        if (!bounds) {
            if (root.pageRestoreAttempts < 8) {
                root.pageRestoreAttempts += 1
                pageRestoreRetry.restart()
            }
            return
        }

        var horizontalRange = bounds.maximumX - bounds.minimumX
        var verticalRange = bounds.maximumY - bounds.minimumY
        bounds.target.contentX = bounds.minimumX
            + root.savedPageHorizontalRatio * horizontalRange
        bounds.target.contentY = bounds.minimumY
            + root.savedPageVerticalRatio * verticalRange

        root.pageRestoreAttempts = 0
        if (root.syncRecenterHorizontal)
            root.centerHorizontally()
        root.updateExplicitScrollBars()
    }

    function updateExplicitScrollBars() {
        var bounds = currentPageScrollBounds()
        if (!bounds) {
            root.explicitHorizontalOverflow = false
            root.explicitVerticalOverflow = false
            return
        }

        // Do not clamp the viewport here. This function is called after wheel
        // scrolling, document reloads, zoom changes, and resize events. Clamping
        // to the current page during a passive refresh prevents PdfMultiPageView
        // from crossing a page boundary and makes full documents snap upward.
        // Explicit page-local panning and scrollbar writes still use the same
        // page bounds through panBy(), setExplicitHorizontalPosition(), and
        // setExplicitVerticalPosition().
        var pageWidth = Math.max(bounds.pageRight - bounds.pageLeft, 1)
        var pageHeight = Math.max(bounds.pageBottom - bounds.pageTop, 1)
        var horizontalRange = Math.max(
            bounds.maximumX - bounds.minimumX,
            0
        )
        var verticalRange = Math.max(
            bounds.maximumY - bounds.minimumY,
            0
        )

        root.explicitHorizontalOverflow = horizontalRange > 0.5
        root.explicitVerticalOverflow = verticalRange > 0.5
        root.explicitHorizontalSize = Math.max(
            0.02,
            Math.min(1.0, bounds.target.width / pageWidth)
        )
        root.explicitVerticalSize = Math.max(
            0.02,
            Math.min(1.0, bounds.target.height / pageHeight)
        )

        var horizontalRatio = 0.0
        var verticalRatio = 0.0
        if (horizontalRange > 0.5) {
            horizontalRatio = clampValue(
                (bounds.target.contentX - bounds.minimumX) / horizontalRange,
                0.0,
                1.0
            )
        }
        if (verticalRange > 0.5) {
            verticalRatio = clampValue(
                (bounds.target.contentY - bounds.minimumY) / verticalRange,
                0.0,
                1.0
            )
        }

        var horizontalPositionRange = Math.max(
            1.0 - root.explicitHorizontalSize,
            0.0
        )
        var verticalPositionRange = Math.max(
            1.0 - root.explicitVerticalSize,
            0.0
        )
        root.explicitHorizontalPosition = horizontalRatio
            * horizontalPositionRange
        root.explicitVerticalPosition = verticalRatio
            * verticalPositionRange

        var horizontalBar = findBoundaryScrollBar(root, Qt.Horizontal)
        var verticalBar = findBoundaryScrollBar(root, Qt.Vertical)
        if (horizontalBar && !horizontalBar.pressed) {
            horizontalBar.size = root.explicitHorizontalSize
            horizontalBar.position = root.explicitHorizontalPosition
        }
        if (verticalBar && !verticalBar.pressed) {
            verticalBar.size = root.explicitVerticalSize
            verticalBar.position = root.explicitVerticalPosition
        }
    }

    Timer {
        id: pageRestoreRetry
        interval: 70
        repeat: false
        onTriggered: root.restoreScrollState()
    }
}
