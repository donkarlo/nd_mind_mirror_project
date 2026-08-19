import QtQuick
import QtQuick.Controls
import QtQuick.Pdf

Rectangle {
    id: root
    property url source: ""
    property int reloadToken: 0
    property alias zoomScale: pdfView.renderScale
    property int currentPageIndex: pdfView.currentPage
    property int pageCount: pdfDocument.pageCount
    property int fitToken: 0
    property real fitWidthRatio: 0.95
    property real zoomAnchorX: 0
    property real zoomAnchorY: 0
    property real zoomTargetScale: 1
    property int zoomToken: 0
    property bool zoomAnchorPending: false
    property real zoomAnchorContentRatioX: 0
    property real zoomAnchorContentRatioY: 0
    property real zoomAnchorViewportX: 0
    property real zoomAnchorViewportY: 0
    property real panDeltaX: 0
    property real panDeltaY: 0
    property int panToken: 0
    property int syncPage: 0
    property real syncX: 0
    property real syncY: 0
    property int syncToken: 0
    property bool resetPositionOnReload: false
    property bool restorePositionPending: false
    property real savedContentX: 0
    property real savedContentY: 0
    property real savedOriginX: 0
    property real savedOriginY: 0
    color: "white"

    function captureScrollState() {
        var target = findBestScrollable(pdfView)
        if (!target) {
            root.restorePositionPending = false
            return
        }

        try {
            root.savedContentX = target.contentX
            root.savedContentY = target.contentY
            root.savedOriginX = target.originX !== undefined ? target.originX : 0
            root.savedOriginY = target.originY !== undefined ? target.originY : 0
            root.restorePositionPending = true
        } catch (error) {
            root.restorePositionPending = false
        }
    }

    function restoreScrollState() {
        if (!root.restorePositionPending)
            return

        var target = findBestScrollable(pdfView)
        if (!target)
            return

        try {
            var originX = target.originX !== undefined ? target.originX : 0
            var originY = target.originY !== undefined ? target.originY : 0
            var maxX = Math.max(originX, originX + target.contentWidth - target.width)
            var maxY = Math.max(originY, originY + target.contentHeight - target.height)

            // Preserve the absolute visual offset from the scroll origin.
            // This keeps the preview at the same place when a later LaTeX
            // pass republishes the same document.
            var desiredX = originX + (root.savedContentX - root.savedOriginX)
            var desiredY = originY + (root.savedContentY - root.savedOriginY)
            target.contentX = Math.max(originX, Math.min(maxX, desiredX))
            target.contentY = Math.max(originY, Math.min(maxY, desiredY))
        } catch (error) {
            return
        }
    }

    function resetScrollPosition() {
        var target = findBestScrollable(pdfView)
        if (!target)
            return


        try {
            var originX = target.originX !== undefined ? target.originX : 0
            var originY = target.originY !== undefined ? target.originY : 0
            target.contentX = originX
            target.contentY = originY
        } catch (error) {
        }
    }

    function reloadDocument() {
        if (root.resetPositionOnReload) {
            root.restorePositionPending = false
        } else {
            root.captureScrollState()
        }

        var target = root.source
        pdfDocument.source = ""
        pdfDocument.source = target
        scrollBarRefresh.restart()
        viewRestore.restart()
    }

    // PdfMultiPageView is a QML composition. Its scrolling surface is an
    // internal Flickable/TableView, so locate the largest scrollable child
    // instead of depending on a private Qt object id.
    function scrollCandidateScore(item) {
        if (!item)
            return -1

        try {
            if (item.contentX === undefined ||
                    item.contentY === undefined ||
                    item.contentWidth === undefined ||
                    item.contentHeight === undefined ||
                    item.width === undefined ||
                    item.height === undefined)
                return -1

            var overflowX = Math.max(0, item.contentWidth - item.width)
            var overflowY = Math.max(0, item.contentHeight - item.height)
            return overflowX + overflowY
        } catch (error) {
            return -1
        }
    }

    function findBestScrollable(item) {
        if (!item)
            return null

        var best = null
        var bestScore = -1
        var ownScore = scrollCandidateScore(item)

        if (ownScore >= 0) {
            best = item
            bestScore = ownScore
        }

        var visualChildren = item.children
        if (!visualChildren)
            return best

        for (var i = 0; i < visualChildren.length; ++i) {
            var candidate = findBestScrollable(visualChildren[i])
            if (!candidate)
                continue

            var candidateScore = scrollCandidateScore(candidate)
            if (candidateScore > bestScore) {
                best = candidate
                bestScore = candidateScore
            }
        }

        return best
    }

    function panBy(dx, dy) {
        var target = findBestScrollable(pdfView)
        if (!target)
            return

        try {
            if (target.cancelFlick !== undefined)
                target.cancelFlick()

            var minX = target.originX !== undefined ? target.originX : 0
            var minY = target.originY !== undefined ? target.originY : 0
            var maxX = Math.max(
                minX,
                minX + target.contentWidth - target.width
            )
            var maxY = Math.max(
                minY,
                minY + target.contentHeight - target.height
            )

            target.contentX = Math.max(
                minX,
                Math.min(maxX, target.contentX + dx)
            )
            target.contentY = Math.max(
                minY,
                Math.min(maxY, target.contentY + dy)
            )
        } catch (error) {
            // Ignore private Qt Quick children that happen to expose
            // similarly named read-only properties.
        }
    }

    function zoomAroundAnchor(viewX, viewY, requestedScale) {
        var target = findBestScrollable(pdfView)
        var boundedScale = Math.max(0.20, Math.min(8.00, requestedScale))
        if (!target) {
            pdfView.renderScale = boundedScale
            scrollBarRefresh.restart()
            return
        }

        try {
            var localPoint = target.mapFromItem(root, viewX, viewY)
            var originX = target.originX !== undefined ? target.originX : 0
            var originY = target.originY !== undefined ? target.originY : 0
            var width = Math.max(target.contentWidth, 1)
            var height = Math.max(target.contentHeight, 1)

            // Store the exact content point underneath the mouse as a ratio
            // of the laid-out scrollable document. After Qt relays out the
            // pages at the new renderScale, restore that same content point
            // underneath the same mouse coordinates.
            root.zoomAnchorContentRatioX = (
                target.contentX - originX + localPoint.x
            ) / width
            root.zoomAnchorContentRatioY = (
                target.contentY - originY + localPoint.y
            ) / height
            root.zoomAnchorViewportX = viewX
            root.zoomAnchorViewportY = viewY
            root.zoomAnchorPending = true
            pdfView.renderScale = boundedScale
            zoomAnchorRestore.restart()
            scrollBarRefresh.restart()
        } catch (error) {
            root.zoomAnchorPending = false
            pdfView.renderScale = boundedScale
            scrollBarRefresh.restart()
        }
    }

    function restoreZoomAnchor() {
        if (!root.zoomAnchorPending)
            return

        var target = findBestScrollable(pdfView)
        if (!target)
            return

        try {
            var localPoint = target.mapFromItem(
                root,
                root.zoomAnchorViewportX,
                root.zoomAnchorViewportY
            )
            var originX = target.originX !== undefined ? target.originX : 0
            var originY = target.originY !== undefined ? target.originY : 0
            var maxX = Math.max(
                originX,
                originX + target.contentWidth - target.width
            )
            var maxY = Math.max(
                originY,
                originY + target.contentHeight - target.height
            )
            var desiredX = originX
                + root.zoomAnchorContentRatioX * target.contentWidth
                - localPoint.x
            var desiredY = originY
                + root.zoomAnchorContentRatioY * target.contentHeight
                - localPoint.y

            target.contentX = Math.max(originX, Math.min(maxX, desiredX))
            target.contentY = Math.max(originY, Math.min(maxY, desiredY))
            root.zoomAnchorPending = false
        } catch (error) {
            root.zoomAnchorPending = false
        }
    }

    function centerHorizontally() {
        var target = findBestScrollable(pdfView)
        if (!target)
            return

        try {
            var originX = target.originX !== undefined ? target.originX : 0
            var overflowX = Math.max(0, target.contentWidth - target.width)
            target.contentX = originX + overflowX / 2
        } catch (error) {
        }
    }

    function fitToPanel() {
        try {
            if (pdfDocument.pageCount <= 0)
                return
            // Width-only fit: use the requested fraction of the visible
            // preview width. The vertical extent is deliberately not a fit
            // constraint; tall pages may require vertical scrolling.
            pdfView.scaleToWidth(
                Math.max(root.width * root.fitWidthRatio, 1),
                Math.max(root.height, 1)
            )
            fitCenterRestore.restart()
            scrollBarRefresh.restart()
        } catch (error) {
        }
    }

    function goToSourceLocation() {
        try {
            pdfView.goToLocation(
                Math.max(root.syncPage, 0),
                Qt.point(root.syncX, root.syncY),
                pdfView.renderScale
            )
            scrollBarRefresh.restart()
        } catch (error) {
            sourceLocationRetry.restart()
        }
    }

    // Depending on the active Qt Quick Controls style, the scrollbars inside
    // PdfMultiPageView may fade away. Keep the native bars visible and
    // interactive without replacing Qt's own multipage/text-selection view.
    function keepNativeScrollBarsVisible(item) {
        if (!item)
            return

        try {
            if (item.policy !== undefined &&
                    item.orientation !== undefined &&
                    item.position !== undefined &&
                    item.size !== undefined) {
                item.policy = ScrollBar.AlwaysOn
                if (item.interactive !== undefined)
                    item.interactive = true
                if (item.hoverEnabled !== undefined)
                    item.hoverEnabled = true
                if (item.active !== undefined)
                    item.active = true
            }
        } catch (error) {
            // Some internal Qt Quick objects expose read-only properties.
        }

        var visualChildren = item.children
        if (!visualChildren)
            return
        for (var i = 0; i < visualChildren.length; ++i)
            keepNativeScrollBarsVisible(visualChildren[i])
    }

    function refreshScrollBars() {
        keepNativeScrollBarsVisible(pdfView)
    }

    onReloadTokenChanged: reloadDocument()
    onPanTokenChanged: panBy(root.panDeltaX, root.panDeltaY)
    onZoomTokenChanged: zoomAroundAnchor(
        root.zoomAnchorX,
        root.zoomAnchorY,
        root.zoomTargetScale
    )
    onSyncTokenChanged: sourceLocationRetry.restart()
    onFitTokenChanged: fitToPanel()
    onZoomScaleChanged: scrollBarRefresh.restart()
    onWidthChanged: scrollBarRefresh.restart()
    onHeightChanged: scrollBarRefresh.restart()

    PdfDocument {
        id: pdfDocument
        source: ""
        onStatusChanged: {
            scrollBarRefresh.restart()
            viewRestore.restart()
        }
    }

    PdfMultiPageView {
        id: pdfView
        anchors.fill: parent
        document: pdfDocument
        clip: true

        Shortcut {
            sequence: "Ctrl+C"
            onActivated: pdfView.copySelectionToClipboard()
        }

        Shortcut {
            sequence: "Ctrl+A"
            onActivated: pdfView.selectAll()
        }
    }

    Timer {
        id: scrollBarRefresh
        interval: 0
        repeat: false
        onTriggered: {
            root.refreshScrollBars()
            delayedScrollBarRefresh.restart()
        }
    }

    Timer {
        id: delayedScrollBarRefresh
        interval: 80
        repeat: false
        onTriggered: root.refreshScrollBars()
    }

    // A successful first LaTeX pass is intentionally shown immediately, and
    // later passes can republish the same PDF a few seconds later. Qt Quick
    // rebuilds the PdfMultiPageView on every source change and otherwise
    // returns to the top. Restore the old scroll offset after the internal
    // Flickable/TableView has had a chance to lay itself out.
    Timer {
        id: viewRestore
        interval: 90
        repeat: false
        onTriggered: {
            if (root.resetPositionOnReload) {
                root.resetScrollPosition()
                root.resetPositionOnReload = false
                root.restorePositionPending = false
            } else {
                root.restoreScrollState()
            }
        }
    }

    Timer {
        id: zoomAnchorRestore
        interval: 35
        repeat: false
        onTriggered: root.restoreZoomAnchor()
    }

    Timer {
        id: fitCenterRestore
        interval: 35
        repeat: false
        onTriggered: root.centerHorizontally()
    }

    Timer {
        id: sourceLocationRetry
        interval: 70
        repeat: false
        onTriggered: root.goToSourceLocation()
    }

    Component.onCompleted: scrollBarRefresh.start()
}
