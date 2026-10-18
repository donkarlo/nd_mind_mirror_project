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
    property string findQuery: ""
    property int findResultIndex: -1
    // Explicit double-click word selection is independent of PDF search and
    // drag selection. Coordinates stay in PDF points as the user scrolls/zooms.
    property string selectedWordText: ""
    property int selectedWordPage: -1
    property var selectedWordRects: []
    readonly property string dragSelectedText: pdfView.selectedText
    property bool mouseSelectionHeld: false
    property int wordOverlayRevision: 0
    signal copyWordRequested(string text)
    property int highlightSearchAttempts: 0
    property bool resetPositionOnReload: false
    property bool restorePositionPending: false
    property bool documentReloadPending: false
    property bool activeReloadResetPosition: false
    property bool pendingResetPositionOnReload: false
    property bool reloadScrollStateCaptured: false
    property url pendingDocumentSource: ""
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

    function projectedWordRect(rect, revision) {
        // Revision is intentionally read as a dependency: the timer updates
        // the highlight coordinates while the PDF is scrolled or resized.
        var refresh = revision
        if (root.selectedWordPage < 0 || !root.documentIsReady())
            return null
        var paper = root.findPagePaper(pdfView, root.selectedWordPage)
        if (!paper || !paper.pageScale || paper.pageScale <= 0)
            return null
        var topLeft = paper.mapToItem(root, rect[0] * paper.pageScale, rect[1] * paper.pageScale)
        var bottomRight = paper.mapToItem(root, (rect[0] + rect[2]) * paper.pageScale,
                                             (rect[1] + rect[3]) * paper.pageScale)
        return {"x": Math.min(topLeft.x, bottomRight.x),
                "y": Math.min(topLeft.y, bottomRight.y),
                "width": Math.abs(bottomRight.x - topLeft.x),
                "height": Math.abs(bottomRight.y - topLeft.y)}
    }

    function toggleNativeMouseFlicking() {
        var scroller = root.findBestScrollable(pdfView)
        if (scroller && scroller.interactive !== undefined)
            scroller.interactive = !root.mouseSelectionHeld
    }
    onMouseSelectionHeldChanged: toggleNativeMouseFlicking()

    function documentIsBusy() {
        return pdfDocument.status === PdfDocument.Loading
            || pdfDocument.status === PdfDocument.Unloading
    }

    function documentIsReady() {
        return pdfDocument.status === PdfDocument.Ready
    }

    function captureScrollState() {
        if (!root.documentIsReady())
            return

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
        if (!root.documentIsReady() || !root.restorePositionPending)
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
        if (!root.documentIsReady())
            return

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

    function queueDocumentReload() {
        // A reset request remains active until the final Ready generation has
        // actually applied it. A newer generation can arrive after Ready but
        // before the restore timer runs, so carry the intent across that gap.
        var carryReset = root.activeReloadResetPosition
        var queuedReset = root.documentReloadPending
            ? root.pendingResetPositionOnReload
            : carryReset

        root.pendingDocumentSource = root.source
        root.pendingResetPositionOnReload = queuedReset
            || root.resetPositionOnReload
        root.documentReloadPending = true

        if (!root.documentIsBusy())
            documentReloadDispatch.restart()
    }

    function startPendingDocumentReload() {
        if (!root.documentReloadPending || root.documentIsBusy())
            return

        var target = root.pendingDocumentSource
        var shouldReset = root.pendingResetPositionOnReload

        root.documentReloadPending = false
        root.pendingResetPositionOnReload = false

        if (String(target).length === 0) {
            root.activeReloadResetPosition = false
            return
        }

        root.activeReloadResetPosition = shouldReset
        if (shouldReset) {
            root.restorePositionPending = false
            root.reloadScrollStateCaptured = false
        } else if (
            !root.reloadScrollStateCaptured
            && root.documentIsReady()
        ) {
            root.captureScrollState()
            root.reloadScrollStateCaptured = root.restorePositionPending
        }

        pdfView.renderScale = root.safeScale(pdfView.renderScale)

        // Every generated preview uses a unique file URL. Assign the new URL
        // directly: an intermediate empty source creates an unnecessary
        // Unloading/Null cycle while PdfMultiPageView still owns old delegates.
        pdfDocument.source = target
    }

    function reloadDocument() {
        root.queueDocumentReload()
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
        if (!root.documentIsReady()) {
            root.reverseClickResultToken = root.reverseClickToken
            return
        }
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
        if (!root.documentIsReady())
            return

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
        var boundedScale = root.safeScale(requestedScale)
        if (!root.documentIsReady()) {
            pdfView.renderScale = boundedScale
            return
        }

        var target = findBestScrollable(pdfView)
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
        if (!root.documentIsReady() || !root.zoomAnchorPending)
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
        if (!root.documentIsReady())
            return

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
        if (!root.documentIsReady())
            return

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
        if (!root.documentIsReady())
            return

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
        if (!root.documentIsReady()) {
            root.explicitHorizontalOverflow = false
            root.explicitVerticalOverflow = false
            return
        }

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
        if (!root.documentIsReady())
            return

        keepNativeScrollBarsVisible(pdfView)
        updateExplicitScrollBars()
    }

    function configureEditHighlightStyle() {
        try {
            var candidates = pdfView.resources
            for (var i = 0; i < candidates.length; ++i) {
                var candidate = candidates[i]
                if (candidate && candidate.pageSearchResultsColor !== undefined) {
                    candidate.pageSearchResultsColor = root.findQuery ? "#66ffeb3b" : "transparent"
                    candidate.currentSearchResultStrokeColor = root.findQuery ? "#e65100" : "#ff9800"
                    candidate.currentSearchResultStrokeWidth = 3
                    break
                }
            }
        } catch (error) {
        }
    }

    function chooseNearestHighlightResult() {
        if (!root.documentIsReady()
                || !root.editHighlightText
                || !pdfView.searchModel)
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
    onPanTokenChanged: {
        if (root.documentIsReady())
            panBy(root.panDeltaX, root.panDeltaY)
    }
    onZoomTokenChanged: {
        if (root.documentIsReady()) {
            zoomAroundAnchor(
                root.zoomAnchorX,
                root.zoomAnchorY,
                root.zoomTargetScale
            )
        }
    }
    onSyncTokenChanged: {
        if (root.documentIsReady()) {
            sourceLocationRetry.restart()
            if (!root.findQuery) scheduleHighlightResultChoice()
        }
    }
    onReverseClickTokenChanged: mapReverseClick()
    onEditHighlightTextChanged: scheduleHighlightResultChoice()
    onFindQueryChanged: { configureEditHighlightStyle(); if (root.findQuery) findResultRetry.restart() }
    onFindResultIndexChanged: { if (root.findQuery) findResultRetry.restart() }
    onFitTokenChanged: fitToPanel()
    onZoomScaleChanged: scrollBarRefresh.restart()
    onWidthChanged: scrollBarRefresh.restart()
    onHeightChanged: scrollBarRefresh.restart()

    Timer {
        id: findResultRetry
        interval: 100
        repeat: true
        property int attempts: 0
        onTriggered: {
            attempts += 1
            root.configureEditHighlightStyle()
            if (pdfView.searchModel && pdfView.searchModel.count > root.findResultIndex && root.findResultIndex >= 0) {
                pdfView.searchModel.currentResult = root.findResultIndex
                attempts = 0
                stop()
            } else if (attempts > 12) { attempts = 0; stop() }
        }
    }

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

    Timer {
        id: documentReloadDispatch
        interval: 0
        repeat: false
        onTriggered: root.startPendingDocumentReload()
    }

    PdfDocument {
        id: pdfDocument
        source: ""
        onStatusChanged: {
            if (pdfDocument.status === PdfDocument.Ready) {
                if (root.documentReloadPending) {
                    // Leave the just-finished intermediate generation alone.
                    // The queued newest generation is started outside this
                    // native status callback to avoid re-entrant QtPdf reloads.
                    documentReloadDispatch.restart()
                    return
                }

                scrollBarRefresh.restart()
                viewRestore.restart()
                if (root.findQuery) findResultRetry.restart()
                else if (root.editHighlightText) root.scheduleHighlightResultChoice()
            } else if (
                pdfDocument.status === PdfDocument.Error
                || pdfDocument.status === PdfDocument.Null
            ) {
                if (root.documentReloadPending)
                    documentReloadDispatch.restart()
            }
        }
    }

    PdfMultiPageView {
        id: pdfView
        anchors.fill: parent
        document: pdfDocument
        clip: true
        searchString: root.findQuery || root.editHighlightText

        Component.onCompleted: root.configureEditHighlightStyle()

        Shortcut {
            sequence: "Ctrl+C"
            onActivated: {
                if (root.selectedWordText)
                    root.copyWordRequested(root.selectedWordText)
                else
                    pdfView.copySelectionToClipboard()
            }
        }

        Shortcut {
            sequence: "Ctrl+A"
            onActivated: pdfView.selectAll()
        }
    }

    // Do not intercept PDF pointer input. Unlike a screenshot overlay, the
    // translucent highlight remains attached to the glyph when scrolling.
    Item {
        id: doubleClickedWordHighlight
        anchors.fill: parent
        clip: true
        z: 100
        enabled: false
        Repeater {
            model: root.selectedWordRects
            delegate: Rectangle {
                required property var modelData
                property var projected: root.projectedWordRect(modelData, root.wordOverlayRevision)
                x: projected ? projected.x : 0
                y: projected ? projected.y : 0
                width: projected ? projected.width : 0
                height: projected ? projected.height : 0
                color: "#669bcfff"
                border.width: 0
                visible: projected !== null
            }
        }
    }
    Timer {
        interval: 80
        running: root.selectedWordText.length > 0
        repeat: true
        onTriggered: root.wordOverlayRevision++
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
            if (pressed && root.documentIsReady())
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
            if (pressed && root.documentIsReady())
                root.setExplicitVerticalPosition(position)
        }
    }

    Timer {
        id: explicitScrollBarState
        interval: 200
        repeat: true
        running: true
        onTriggered: {
            if (root.documentIsReady())
                root.updateExplicitScrollBars()
        }
    }

    Timer {
        id: syncHorizontalCenter
        interval: 0
        repeat: false
        onTriggered: {
            if (!root.documentIsReady())
                return
            root.centerHorizontally()
            syncHorizontalCenterDelayed.restart()
        }
    }

    Timer {
        id: syncHorizontalCenterDelayed
        interval: 55
        repeat: false
        onTriggered: {
            if (!root.documentIsReady())
                return
            root.centerHorizontally()
            syncHorizontalCenterFinal.restart()
        }
    }

    Timer {
        id: syncHorizontalCenterFinal
        interval: 150
        repeat: false
        onTriggered: {
            if (root.documentIsReady())
                root.centerHorizontally()
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

    Timer {
        id: viewRestore
        interval: 90
        repeat: false
        onTriggered: {
            if (!root.documentIsReady())
                return

            if (root.activeReloadResetPosition) {
                root.resetScrollPosition()
                root.resetPositionOnReload = false
                root.restorePositionPending = false
            } else {
                root.restoreScrollState()
            }

            root.activeReloadResetPosition = false
            root.reloadScrollStateCaptured = false

            if (root.syncRecenterHorizontal)
                root.centerHorizontally()
        }
    }

    Timer {
        id: zoomAnchorRestore
        interval: 35
        repeat: false
        onTriggered: {
            if (root.documentIsReady())
                root.restoreZoomAnchor()
        }
    }

    Timer {
        id: fitCenterRestore
        interval: 35
        repeat: false
        onTriggered: {
            if (!root.documentIsReady())
                return
            root.centerHorizontally()
            fitCenterRestoreDelayed.restart()
        }
    }

    Timer {
        id: fitCenterRestoreDelayed
        interval: 120
        repeat: false
        onTriggered: {
            if (root.documentIsReady())
                root.centerHorizontally()
        }
    }

    Timer {
        id: sourceLocationRetry
        interval: 70
        repeat: false
        onTriggered: root.goToSourceLocation()
    }

    Component.onCompleted: scrollBarRefresh.start()
}

