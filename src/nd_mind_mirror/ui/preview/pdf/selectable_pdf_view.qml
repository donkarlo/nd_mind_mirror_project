import QtQuick
import QtQuick.Controls
import QtQuick.Pdf

Rectangle {
    id: root
    property url source: ""
    property int reloadToken: 0
    property alias zoomScale: pdfView.renderScale
    property real minSafeZoomScale: 0.20
    property real maxSafeZoomScale: 5.00
    property int currentPageIndex: pdfView.currentPage
    property int pageCount: pdfDocument.pageCount
    property int fitToken: 0
    property real fitWidthRatio: 0.95
    property real fitTargetWidth: 0
    property real fitPageWidthPoints: 0
    property real fitContentWidthPoints: 0
    property real fitContentCenterRatioX: 0.5
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
    property bool syncRecenterHorizontal: false
    property real reverseClickX: 0
    property real reverseClickY: 0
    property int reverseClickToken: 0
    property int reverseClickResultToken: 0
    property int reverseClickPage: -1
    property real reverseClickPdfX: 0
    property real reverseClickPdfY: 0
    property string editHighlightText: ""
    property int highlightSearchAttempts: 0
    property bool resetPositionOnReload: false
    property bool restorePositionPending: false
    property real savedContentX: 0
    property real savedContentY: 0
    property real savedOriginX: 0
    property real savedOriginY: 0
    property real savedRenderScale: 1.0
    property bool explicitHorizontalOverflow: false
    property bool explicitVerticalOverflow: false
    property real explicitHorizontalPosition: 0
    property real explicitVerticalPosition: 0
    property real explicitHorizontalSize: 1
    property real explicitVerticalSize: 1

    // A faint canvas makes the real PDF page edges visible when the complete
    // paper is shown. Content-aware Fit itself crops unused white margins.
    color: "#f5f7fa"

    function safeScale(value) {
        if (!isFinite(value) || value <= 0)
            return 1.0
        return Math.max(root.minSafeZoomScale,
                        Math.min(root.maxSafeZoomScale, value))
    }

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
            root.savedRenderScale = root.safeScale(pdfView.renderScale)
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
            if (root.savedRenderScale > 0)
                pdfView.renderScale = root.savedRenderScale

            var originX = target.originX !== undefined ? target.originX : 0
            var originY = target.originY !== undefined ? target.originY : 0
            var maxX = Math.max(originX, originX + target.contentWidth - target.width)
            var maxY = Math.max(originY, originY + target.contentHeight - target.height)
            var desiredX = originX + (root.savedContentX - root.savedOriginX)
            var desiredY = originY + (root.savedContentY - root.savedOriginY)
            target.contentX = Math.max(originX, Math.min(maxX, desiredX))
            target.contentY = Math.max(originY, Math.min(maxY, desiredY))
            if (root.syncRecenterHorizontal)
                root.centerHorizontally()
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

        pdfView.renderScale = root.safeScale(pdfView.renderScale)
        var target = root.source
        pdfDocument.source = ""
        pdfDocument.source = target
        scrollBarRefresh.restart()
        viewRestore.restart()
    }

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

    function pageIndexForPaper(item) {
        var holder = item
        while (holder) {
            try {
                if (holder.index !== undefined) {
                    var value = Number(holder.index)
                    if (isFinite(value) && value >= 0)
                        return Math.floor(value)
                }
            } catch (error) {
            }
            holder = holder.parent
        }
        return -1
    }

    function findPagePaper(item, pageIndex) {
        if (!item)
            return null

        try {
            if (item.pageScale !== undefined &&
                    item.pagePointSize !== undefined &&
                    root.pageIndexForPaper(item) === pageIndex)
                return item
        } catch (error) {
        }

        var visualChildren = item.children
        if (!visualChildren)
            return null
        for (var i = 0; i < visualChildren.length; ++i) {
            var found = root.findPagePaper(visualChildren[i], pageIndex)
            if (found)
                return found
        }
        return null
    }

    function findPaperAtPoint(item, viewX, viewY) {
        if (!item)
            return null

        try {
            if (item.pageScale !== undefined && item.pagePointSize !== undefined) {
                var local = item.mapFromItem(root, viewX, viewY)
                if (local.x >= 0 && local.y >= 0 &&
                        local.x <= item.width && local.y <= item.height) {
                    var page = root.pageIndexForPaper(item)
                    if (page >= 0)
                        return { "paper": item, "page": page, "local": local }
                }
            }
        } catch (error) {
        }

        var visualChildren = item.children
        if (!visualChildren)
            return null
        for (var i = visualChildren.length - 1; i >= 0; --i) {
            var found = root.findPaperAtPoint(visualChildren[i], viewX, viewY)
            if (found)
                return found
        }
        return null
    }

    function mapReverseClick() {
        root.reverseClickPage = -1
        root.reverseClickPdfX = 0
        root.reverseClickPdfY = 0
        try {
            var result = root.findPaperAtPoint(
                pdfView,
                root.reverseClickX,
                root.reverseClickY
            )
            if (result) {
                var scale = Number(result.paper.pageScale)
                if (isFinite(scale) && scale > 0) {
                    root.reverseClickPage = result.page
                    root.reverseClickPdfX = result.local.x / scale
                    root.reverseClickPdfY = result.local.y / scale
                }
            }
        } catch (error) {
            root.reverseClickPage = -1
        }
        root.reverseClickResultToken = root.reverseClickToken
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
            var maxX = Math.max(minX, minX + target.contentWidth - target.width)
            var maxY = Math.max(minY, minY + target.contentHeight - target.height)
            target.contentX = Math.max(minX, Math.min(maxX, target.contentX + dx))
            target.contentY = Math.max(minY, Math.min(maxY, target.contentY + dy))
        } catch (error) {
        }
    }

    function zoomAroundAnchor(viewX, viewY, requestedScale) {
        var target = findBestScrollable(pdfView)
        var boundedScale = root.safeScale(requestedScale)
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
            var maxX = Math.max(originX, originX + target.contentWidth - target.width)
            var maxY = Math.max(originY, originY + target.contentHeight - target.height)
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
            var maxX = Math.max(originX, originX + overflowX)
            var desired = originX + overflowX / 2

            if (root.fitContentWidthPoints > 1 && root.fitPageWidthPoints > 1) {
                var paper = root.findPagePaper(pdfView, Math.max(pdfView.currentPage, 0))
                if (paper) {
                    var pageScale = Number(paper.pageScale)
                    if (!isFinite(pageScale) || pageScale <= 0)
                        pageScale = pdfView.renderScale
                    var centerPoints = root.fitContentCenterRatioX * root.fitPageWidthPoints
                    var halfPoints = root.fitContentWidthPoints / 2
                    var leftPoints = Math.max(0, centerPoints - halfPoints)
                    var rightPoints = Math.min(root.fitPageWidthPoints, centerPoints + halfPoints)
                    var coordinateItem = target.contentItem !== undefined
                        ? target.contentItem
                        : target
                    var left = paper.mapToItem(
                        coordinateItem,
                        leftPoints * pageScale,
                        0
                    ).x
                    var right = paper.mapToItem(
                        coordinateItem,
                        rightPoints * pageScale,
                        0
                    ).x
                    var contentCenter = (left + right) / 2
                    desired = contentCenter - target.width / 2
                }
            }

            target.contentX = Math.max(originX, Math.min(maxX, desired))
        } catch (error) {
        }
    }

    function fitToPanel() {
        try {
            if (pdfDocument.pageCount <= 0)
                return

            var pageIndex = Math.max(0, Math.min(pdfView.currentPage,
                                                  pdfDocument.pageCount - 1))
            var pageSize = pdfDocument.pagePointSize(pageIndex)
            if (!pageSize || pageSize.width <= 0 || pageSize.height <= 0)
                return

            var scrollTarget = findBestScrollable(pdfView)
            var viewportWidth = root.width
            if (scrollTarget && scrollTarget.width !== undefined &&
                    scrollTarget.width > 1)
                viewportWidth = scrollTarget.width

            root.fitTargetWidth = Math.max(
                viewportWidth * root.fitWidthRatio,
                1
            )

            var rotation = Math.abs(pdfView.pageRotation) % 180
            var pageWidthPoints = rotation === 90
                ? pageSize.height
                : pageSize.width
            if (pageWidthPoints <= 0)
                return

            var effectiveWidthPoints = root.fitContentWidthPoints > 1
                ? root.fitContentWidthPoints
                : pageWidthPoints
            pdfView.renderScale = root.safeScale(root.fitTargetWidth / effectiveWidthPoints)
            root.centerHorizontally()
            fitCenterRestore.restart()
            scrollBarRefresh.restart()
        } catch (error) {
        }
    }

    function goToSourceLocation() {
        try {
            var target = findBestScrollable(pdfView)
            var previousX = 0
            var hadTarget = false
            if (target && target.contentX !== undefined) {
                previousX = target.contentX
                hadTarget = true
            }

            pdfView.goToLocation(
                Math.max(root.syncPage, 0),
                Qt.point(root.syncX, root.syncY),
                pdfView.renderScale
            )

            if (root.syncRecenterHorizontal) {
                if (hadTarget)
                    target.contentX = previousX
                root.centerHorizontally()
                syncHorizontalCenter.restart()
            }
            scrollBarRefresh.restart()
        } catch (error) {
            sourceLocationRetry.restart()
        }
    }

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
        }

        var visualChildren = item.children
        if (!visualChildren)
            return
        for (var i = 0; i < visualChildren.length; ++i)
            keepNativeScrollBarsVisible(visualChildren[i])
    }

    function updateExplicitScrollBars() {
        var target = findBestScrollable(pdfView)
        if (!target) {
            root.explicitHorizontalOverflow = false
            root.explicitVerticalOverflow = false
            return
        }

        try {
            var originX = target.originX !== undefined ? target.originX : 0
            var originY = target.originY !== undefined ? target.originY : 0
            var contentWidth = Math.max(target.contentWidth, 1)
            var contentHeight = Math.max(target.contentHeight, 1)
            var overflowX = Math.max(0, contentWidth - target.width)
            var overflowY = Math.max(0, contentHeight - target.height)

            root.explicitHorizontalOverflow = overflowX > 0.5
            root.explicitVerticalOverflow = overflowY > 0.5
            root.explicitHorizontalSize = Math.max(0.02, Math.min(1, target.width / contentWidth))
            root.explicitVerticalSize = Math.max(0.02, Math.min(1, target.height / contentHeight))
            root.explicitHorizontalPosition = root.explicitHorizontalOverflow
                ? Math.max(0, Math.min(1 - root.explicitHorizontalSize,
                                      (target.contentX - originX) / contentWidth))
                : 0
            root.explicitVerticalPosition = root.explicitVerticalOverflow
                ? Math.max(0, Math.min(1 - root.explicitVerticalSize,
                                      (target.contentY - originY) / contentHeight))
                : 0
            if (!explicitHorizontalBar.pressed)
                explicitHorizontalBar.position = root.explicitHorizontalPosition
            if (!explicitVerticalBar.pressed)
                explicitVerticalBar.position = root.explicitVerticalPosition
        } catch (error) {
            root.explicitHorizontalOverflow = false
            root.explicitVerticalOverflow = false
        }
    }

    function setExplicitHorizontalPosition(position) {
        var target = findBestScrollable(pdfView)
        if (!target)
            return
        try {
            var originX = target.originX !== undefined ? target.originX : 0
            var maxX = Math.max(originX, originX + target.contentWidth - target.width)
            var desired = originX + Math.max(0, position) * Math.max(target.contentWidth, 1)
            target.contentX = Math.max(originX, Math.min(maxX, desired))
        } catch (error) {
        }
    }

    function setExplicitVerticalPosition(position) {
        var target = findBestScrollable(pdfView)
        if (!target)
            return
        try {
            var originY = target.originY !== undefined ? target.originY : 0
            var maxY = Math.max(originY, originY + target.contentHeight - target.height)
            var desired = originY + Math.max(0, position) * Math.max(target.contentHeight, 1)
            target.contentY = Math.max(originY, Math.min(maxY, desired))
        } catch (error) {
        }
    }

    function refreshScrollBars() {
        keepNativeScrollBarsVisible(pdfView)
        updateExplicitScrollBars()
    }

    function configureEditHighlightStyle() {
        try {
            var candidates = pdfView.resources
            for (var i = 0; i < candidates.length; ++i) {
                var candidate = candidates[i]
                if (candidate && candidate.pageSearchResultsColor !== undefined) {
                    candidate.pageSearchResultsColor = "transparent"
                    candidate.currentSearchResultStrokeColor = "#ff9800"
                    candidate.currentSearchResultStrokeWidth = 3
                    break
                }
            }
        } catch (error) {
        }
    }

    function chooseNearestHighlightResult() {
        if (!root.editHighlightText || !pdfView.searchModel)
            return false
        var count = pdfView.searchModel.count
        if (!count || count <= 0)
            return false

        var best = -1
        var bestScore = Number.MAX_VALUE
        for (var i = 0; i < count; ++i) {
            try {
                pdfView.searchModel.currentResult = i
                var link = pdfView.searchModel.currentResultLink
                if (!link || link.page !== root.syncPage)
                    continue
                var lx = link.location ? link.location.x : 0
                var ly = link.location ? link.location.y : 0
                var dx = lx - root.syncX
                var dy = ly - root.syncY
                var score = dx * dx + dy * dy
                if (score < bestScore) {
                    best = i
                    bestScore = score
                }
            } catch (error) {
            }
        }
        if (best < 0)
            best = 0
        pdfView.searchModel.currentResult = best
        return true
    }

    function scheduleHighlightResultChoice() {
        // ND_MIGRATION4_SINGLE_HIGHLIGHT
        // Qt may recreate the search-result resource after a PDF reload. Make
        // every non-current match transparent again before choosing the one
        // nearest to the SyncTeX cursor location.
        root.configureEditHighlightStyle()
        root.highlightSearchAttempts = 0
        highlightResultRetry.restart()
    }

    onReloadTokenChanged: reloadDocument()
    onPanTokenChanged: panBy(root.panDeltaX, root.panDeltaY)
    onZoomTokenChanged: zoomAroundAnchor(
        root.zoomAnchorX,
        root.zoomAnchorY,
        root.zoomTargetScale
    )
    onSyncTokenChanged: {
        sourceLocationRetry.restart()
        scheduleHighlightResultChoice()
    }
    onReverseClickTokenChanged: mapReverseClick()
    onEditHighlightTextChanged: scheduleHighlightResultChoice()
    onFitTokenChanged: fitToPanel()
    onZoomScaleChanged: scrollBarRefresh.restart()
    onWidthChanged: scrollBarRefresh.restart()
    onHeightChanged: scrollBarRefresh.restart()

    Timer {
        id: highlightResultRetry
        interval: 80
        repeat: true
        onTriggered: {
            root.highlightSearchAttempts += 1
            if (root.chooseNearestHighlightResult() || root.highlightSearchAttempts >= 8)
                stop()
        }
    }

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
        searchString: root.editHighlightText

        Component.onCompleted: root.configureEditHighlightStyle()

        Shortcut {
            sequence: "Ctrl+C"
            onActivated: pdfView.copySelectionToClipboard()
        }

        Shortcut {
            sequence: "Ctrl+A"
            onActivated: pdfView.selectAll()
        }
    }

    ScrollBar {
        id: explicitHorizontalBar
        orientation: Qt.Horizontal
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: explicitVerticalBar.visible ? explicitVerticalBar.width : 0
        height: 12
        z: 1000
        visible: root.explicitHorizontalOverflow
        active: visible
        policy: ScrollBar.AlwaysOn
        size: root.explicitHorizontalSize
        onPositionChanged: {
            if (pressed)
                root.setExplicitHorizontalPosition(position)
        }
    }

    ScrollBar {
        id: explicitVerticalBar
        orientation: Qt.Vertical
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.bottomMargin: explicitHorizontalBar.visible ? explicitHorizontalBar.height : 0
        width: 12
        z: 1000
        visible: root.explicitVerticalOverflow
        active: visible
        policy: ScrollBar.AlwaysOn
        size: root.explicitVerticalSize
        onPositionChanged: {
            if (pressed)
                root.setExplicitVerticalPosition(position)
        }
    }

    Timer {
        id: explicitScrollBarState
        interval: 200
        repeat: true
        running: true
        onTriggered: root.updateExplicitScrollBars()
    }

    Timer {
        id: syncHorizontalCenter
        interval: 0
        repeat: false
        onTriggered: {
            root.centerHorizontally()
            syncHorizontalCenterDelayed.restart()
        }
    }

    Timer {
        id: syncHorizontalCenterDelayed
        interval: 55
        repeat: false
        onTriggered: {
            root.centerHorizontally()
            syncHorizontalCenterFinal.restart()
        }
    }

    Timer {
        id: syncHorizontalCenterFinal
        interval: 150
        repeat: false
        onTriggered: root.centerHorizontally()
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
            if (root.syncRecenterHorizontal)
                root.centerHorizontally()
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
        onTriggered: {
            root.centerHorizontally()
            fitCenterRestoreDelayed.restart()
        }
    }

    Timer {
        id: fitCenterRestoreDelayed
        interval: 120
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
