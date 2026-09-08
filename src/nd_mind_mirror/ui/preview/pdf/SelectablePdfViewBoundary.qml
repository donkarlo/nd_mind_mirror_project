import QtQuick
import QtQuick.Controls

SelectablePdfViewBase {
    id: root

    property real savedPageHorizontalRatio: 0.0
    property real savedPageVerticalRatio: 0.0

    function clampValue(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value))
    }

    function fallbackScrollBounds(target) {
        var originX = 0
        var originY = 0
        if (target.originX !== undefined)
            originX = target.originX
        if (target.originY !== undefined)
            originY = target.originY

        var maximumX = Math.max(
            originX,
            originX + target.contentWidth - target.width
        )
        var maximumY = Math.max(
            originY,
            originY + target.contentHeight - target.height
        )
        return {
            "target": target,
            "paper": null,
            "coordinateItem": null,
            "minimumX": originX,
            "maximumX": maximumX,
            "minimumY": originY,
            "maximumY": maximumY,
            "pageLeft": originX,
            "pageRight": maximumX + target.width,
            "pageTop": originY,
            "pageBottom": maximumY + target.height
        }
    }

    function currentPageScrollBounds() {
        var target = findBestScrollable(root)
        if (!target)
            return null

        var fallback = fallbackScrollBounds(target)
        try {
            var pageIndex = Math.max(root.currentPageIndex, 0)
            var paper = findPagePaper(root, pageIndex)
            if (!paper)
                return fallback

            var coordinateItem = target
            if (target.contentItem !== undefined)
                coordinateItem = target.contentItem

            var topLeft = paper.mapToItem(coordinateItem, 0, 0)
            var topRight = paper.mapToItem(coordinateItem, paper.width, 0)
            var bottomLeft = paper.mapToItem(coordinateItem, 0, paper.height)
            var bottomRight = paper.mapToItem(
                coordinateItem,
                paper.width,
                paper.height
            )

            var pageLeft = Math.min(
                topLeft.x,
                topRight.x,
                bottomLeft.x,
                bottomRight.x
            )
            var pageRight = Math.max(
                topLeft.x,
                topRight.x,
                bottomLeft.x,
                bottomRight.x
            )
            var pageTop = Math.min(
                topLeft.y,
                topRight.y,
                bottomLeft.y,
                bottomRight.y
            )
            var pageBottom = Math.max(
                topLeft.y,
                topRight.y,
                bottomLeft.y,
                bottomRight.y
            )

            if (!isFinite(pageLeft) || !isFinite(pageRight) ||
                    !isFinite(pageTop) || !isFinite(pageBottom))
                return fallback

            var pageWidth = pageRight - pageLeft
            var pageHeight = pageBottom - pageTop
            if (pageWidth <= 1 || pageHeight <= 1)
                return fallback

            var minimumX = pageLeft
            var maximumX = pageRight - target.width
            if (pageWidth <= target.width) {
                minimumX = pageLeft + (pageWidth - target.width) / 2
                maximumX = minimumX
            }

            var minimumY = pageTop
            var maximumY = pageBottom - target.height
            if (pageHeight <= target.height) {
                minimumY = pageTop + (pageHeight - target.height) / 2
                maximumY = minimumY
            }

            return {
                "target": target,
                "paper": paper,
                "coordinateItem": coordinateItem,
                "minimumX": minimumX,
                "maximumX": maximumX,
                "minimumY": minimumY,
                "maximumY": maximumY,
                "pageLeft": pageLeft,
                "pageRight": pageRight,
                "pageTop": pageTop,
                "pageBottom": pageBottom
            }
        } catch (error) {
            return fallback
        }
    }

    function captureScrollState() {
        var bounds = currentPageScrollBounds()
        if (!bounds) {
            root.restorePositionPending = false
            return
        }

        var horizontalRange = bounds.maximumX - bounds.minimumX
        var verticalRange = bounds.maximumY - bounds.minimumY
        root.savedPageHorizontalRatio = 0.0
        root.savedPageVerticalRatio = 0.0
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
        root.restorePositionPending = true
    }

    function restoreScrollState() {
        if (!root.restorePositionPending)
            return

        if (root.savedRenderScale > 0)
            root.zoomScale = root.savedRenderScale

        var bounds = currentPageScrollBounds()
        if (!bounds)
            return

        var horizontalRange = bounds.maximumX - bounds.minimumX
        var verticalRange = bounds.maximumY - bounds.minimumY
        bounds.target.contentX = bounds.minimumX
            + root.savedPageHorizontalRatio * horizontalRange
        bounds.target.contentY = bounds.minimumY
            + root.savedPageVerticalRatio * verticalRange
        clampToCurrentPage()
        if (root.syncRecenterHorizontal)
            root.centerHorizontally()
    }

    function resetScrollPosition() {
        var bounds = currentPageScrollBounds()
        if (!bounds)
            return
        bounds.target.contentX = bounds.minimumX
        bounds.target.contentY = bounds.minimumY
    }

    function clampToCurrentPage() {
        var bounds = currentPageScrollBounds()
        if (!bounds)
            return
        bounds.target.contentX = clampValue(
            bounds.target.contentX,
            bounds.minimumX,
            bounds.maximumX
        )
        bounds.target.contentY = clampValue(
            bounds.target.contentY,
            bounds.minimumY,
            bounds.maximumY
        )
    }

    function panBy(deltaX, deltaY) {
        var bounds = currentPageScrollBounds()
        if (!bounds)
            return

        try {
            if (bounds.target.cancelFlick !== undefined)
                bounds.target.cancelFlick()
            bounds.target.contentX = clampValue(
                bounds.target.contentX + deltaX,
                bounds.minimumX,
                bounds.maximumX
            )
            bounds.target.contentY = clampValue(
                bounds.target.contentY + deltaY,
                bounds.minimumY,
                bounds.maximumY
            )
        } catch (error) {
        }
    }

    function zoomAroundAnchor(viewX, viewY, requestedScale) {
        var bounds = currentPageScrollBounds()
        var boundedScale = root.safeScale(requestedScale)
        if (!bounds) {
            root.zoomScale = boundedScale
            return
        }

        try {
            var localPoint = bounds.target.mapFromItem(root, viewX, viewY)
            var pageWidth = Math.max(bounds.pageRight - bounds.pageLeft, 1)
            var pageHeight = Math.max(bounds.pageBottom - bounds.pageTop, 1)
            var anchorContentX = bounds.target.contentX + localPoint.x
            var anchorContentY = bounds.target.contentY + localPoint.y
            root.zoomAnchorContentRatioX = clampValue(
                (anchorContentX - bounds.pageLeft) / pageWidth,
                0.0,
                1.0
            )
            root.zoomAnchorContentRatioY = clampValue(
                (anchorContentY - bounds.pageTop) / pageHeight,
                0.0,
                1.0
            )
            root.zoomAnchorViewportX = viewX
            root.zoomAnchorViewportY = viewY
            root.zoomAnchorPending = true
            root.zoomScale = boundedScale
            pageBoundaryZoomRestore.restart()
        } catch (error) {
            root.zoomAnchorPending = false
            root.zoomScale = boundedScale
        }
    }

    function restoreZoomAnchor() {
        if (!root.zoomAnchorPending)
            return

        var bounds = currentPageScrollBounds()
        if (!bounds)
            return

        try {
            var localPoint = bounds.target.mapFromItem(
                root,
                root.zoomAnchorViewportX,
                root.zoomAnchorViewportY
            )
            var pageWidth = Math.max(bounds.pageRight - bounds.pageLeft, 1)
            var pageHeight = Math.max(bounds.pageBottom - bounds.pageTop, 1)
            var desiredX = bounds.pageLeft
                + root.zoomAnchorContentRatioX * pageWidth
                - localPoint.x
            var desiredY = bounds.pageTop
                + root.zoomAnchorContentRatioY * pageHeight
                - localPoint.y
            bounds.target.contentX = clampValue(
                desiredX,
                bounds.minimumX,
                bounds.maximumX
            )
            bounds.target.contentY = clampValue(
                desiredY,
                bounds.minimumY,
                bounds.maximumY
            )
            root.zoomAnchorPending = false
            updateExplicitScrollBars()
        } catch (error) {
            root.zoomAnchorPending = false
        }
    }

    function centerHorizontally() {
        var bounds = currentPageScrollBounds()
        if (!bounds)
            return

        var desired = (
            bounds.pageLeft + bounds.pageRight - bounds.target.width
        ) / 2
        try {
            if (root.fitContentWidthPoints > 1 &&
                    root.fitPageWidthPoints > 1 && bounds.paper) {
                var pageScale = Number(bounds.paper.pageScale)
                if (!isFinite(pageScale) || pageScale <= 0)
                    pageScale = root.zoomScale

                var centerPoints = root.fitContentCenterRatioX
                    * root.fitPageWidthPoints
                var halfPoints = root.fitContentWidthPoints / 2
                var leftPoints = Math.max(0, centerPoints - halfPoints)
                var rightPoints = Math.min(
                    root.fitPageWidthPoints,
                    centerPoints + halfPoints
                )
                var left = bounds.paper.mapToItem(
                    bounds.coordinateItem,
                    leftPoints * pageScale,
                    0
                ).x
                var right = bounds.paper.mapToItem(
                    bounds.coordinateItem,
                    rightPoints * pageScale,
                    0
                ).x
                desired = (left + right - bounds.target.width) / 2
            }
        } catch (error) {
        }

        bounds.target.contentX = clampValue(
            desired,
            bounds.minimumX,
            bounds.maximumX
        )
    }

    function findBoundaryScrollBar(item, orientation) {
        if (!item)
            return null

        try {
            if (item.orientation !== undefined &&
                    item.position !== undefined &&
                    item.size !== undefined &&
                    item.pressed !== undefined &&
                    item.z !== undefined &&
                    Number(item.z) >= 900 &&
                    item.orientation === orientation)
                return item
        } catch (error) {
        }

        var visualChildren = item.children
        if (!visualChildren)
            return null
        for (var index = 0; index < visualChildren.length; ++index) {
            var found = findBoundaryScrollBar(
                visualChildren[index],
                orientation
            )
            if (found)
                return found
        }
        return null
    }

    function updateExplicitScrollBars() {
        var bounds = currentPageScrollBounds()
        if (!bounds) {
            root.explicitHorizontalOverflow = false
            root.explicitVerticalOverflow = false
            return
        }

        clampToCurrentPage()

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

    function setExplicitHorizontalPosition(position) {
        var bounds = currentPageScrollBounds()
        if (!bounds)
            return

        var positionRange = Math.max(
            1.0 - root.explicitHorizontalSize,
            0.0
        )
        var ratio = 0.0
        if (positionRange > 0.0001)
            ratio = clampValue(position / positionRange, 0.0, 1.0)
        bounds.target.contentX = bounds.minimumX
            + ratio * (bounds.maximumX - bounds.minimumX)
    }

    function setExplicitVerticalPosition(position) {
        var bounds = currentPageScrollBounds()
        if (!bounds)
            return

        var positionRange = Math.max(
            1.0 - root.explicitVerticalSize,
            0.0
        )
        var ratio = 0.0
        if (positionRange > 0.0001)
            ratio = clampValue(position / positionRange, 0.0, 1.0)
        bounds.target.contentY = bounds.minimumY
            + ratio * (bounds.maximumY - bounds.minimumY)
    }

    Timer {
        id: pageBoundaryZoomRestore
        interval: 40
        repeat: false
        onTriggered: root.restoreZoomAnchor()
    }
}
