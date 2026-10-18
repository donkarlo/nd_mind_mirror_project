import QtQuick
import QtQuick.Controls

Item {
    id: root

    // Public API consumed by the Python QQuickWidget bridge.  The active PDF
    // generation is never reloaded in place; every new source is loaded by a
    // freshly instantiated SelectablePdfGenerationView and promoted only once
    // its PdfDocument reports Ready.
    property url source: ""
    property int reloadToken: 0
    property real minSafeZoomScale: 0.20
    property real maxSafeZoomScale: 5.00
    property real zoomScale: 1.0
    property int currentPageIndex: 0
    property int pageCount: 0

    property int fitToken: 0
    property real fitWidthRatio: 0.95
    property real fitPageWidthPoints: 0
    property real fitContentWidthPoints: 0
    property real fitContentCenterRatioX: 0.5

    property real zoomAnchorX: 0
    property real zoomAnchorY: 0
    property real zoomTargetScale: 1
    property int zoomToken: 0

    property real panDeltaX: 0
    property real panDeltaY: 0
    property int panToken: 0

    property int syncPage: 0
    property real syncX: 0
    property real syncY: 0
    property int syncToken: 0
    property bool syncRecenterHorizontal: false

    property string editHighlightText: ""
    property string findQuery: ""
    property int findResultIndex: -1
    property string selectedWordText: ""
    property int selectedWordPage: -1
    property var selectedWordRects: []
    property bool mouseSelectionHeld: false
    property real reverseClickX: 0
    property real reverseClickY: 0
    property real reverseClickPdfX: 0
    property real reverseClickPdfY: 0
    property int reverseClickPage: -1
    signal copyWordRequested(string text)

    function mapReverseClick() {
        var view = root.activeView
        root.reverseClickPage = -1
        if (!view || !view.documentIsReady())
            return
        view.reverseClickX = root.reverseClickX
        view.reverseClickY = root.reverseClickY
        view.mapReverseClick()
        root.reverseClickPage = view.reverseClickPage
        root.reverseClickPdfX = view.reverseClickPdfX
        root.reverseClickPdfY = view.reverseClickPdfY
    }

    function applyWordSelection(view) {
        if (!view) return
        view.selectedWordText = root.selectedWordText
        view.selectedWordPage = root.selectedWordPage
        view.selectedWordRects = root.selectedWordRects
        view.mouseSelectionHeld = root.mouseSelectionHeld
    }
    property bool resetPositionOnReload: false

    // Lifecycle state for the double-buffered generation handoff.
    property int activeSlot: -1
    property int loadingSlot: -1
    property int loadingToken: -1
    property url loadingSource: ""
    property bool loadingResetPosition: false
    property int requestedToken: 0
    property url requestedSource: ""
    property bool requestedResetPosition: false
    property bool generationPending: false
    property bool synchronizingZoomFromActive: false

    readonly property var activeView: activeSlot === 0
        ? slotA.item
        : (activeSlot === 1 ? slotB.item : null)
    readonly property var loadingView: loadingSlot === 0
        ? slotA.item
        : (loadingSlot === 1 ? slotB.item : null)

    function loaderForSlot(slot) {
        return slot === 0 ? slotA : slotB
    }

    function requestGeneration() {
        if (String(root.source).length === 0)
            return

        root.requestedToken = root.reloadToken
        root.requestedSource = root.source
        root.requestedResetPosition = root.resetPositionOnReload
        root.generationPending = true

        // Keep the last known-good PDF visible, but expose pageCount=0 to the
        // Python bridge so its "qt_pdf_ready" timing belongs to the new
        // generation rather than the still-visible old one.
        root.pageCount = 0

        if (root.loadingSlot < 0)
            root.beginLatestGeneration()
    }

    function beginLatestGeneration() {
        if (root.loadingSlot >= 0 || String(root.requestedSource).length === 0)
            return

        var slot = root.activeSlot === 0 ? 1 : 0
        if (root.activeSlot < 0)
            slot = 0

        root.loadingSlot = slot
        root.loadingToken = root.requestedToken
        root.loadingSource = root.requestedSource
        root.loadingResetPosition = root.requestedResetPosition

        // Recreate the inactive slot instead of assigning a new source to a
        // PdfDocument that may still have stale PdfMultiPageView page/link
        // delegates. One event-loop turn guarantees the previous QML object is
        // destroyed before its replacement is instantiated.
        var loader = root.loaderForSlot(slot)
        loader.active = false
        recreateInactiveSlot.restart()
    }

    function configureLoadingView(slot, view) {
        if (!view || slot !== root.loadingSlot)
            return

        // If another render won while the inactive Loader was being recreated,
        // discard this fresh-but-not-yet-loaded view before touching QtPdf.
        if (root.loadingToken !== root.requestedToken ||
                String(root.loadingSource) !== String(root.requestedSource)) {
            root.loadingSlot = -1
            root.loadingToken = -1
            Qt.callLater(root.beginLatestGeneration)
            return
        }

        root.applyPersistentSettings(view)
        root.transferViewState(root.activeView, view, root.loadingResetPosition)

        view.resetPositionOnReload = root.loadingResetPosition
        view.source = root.loadingSource
        view.reloadToken = root.loadingToken
        lifecyclePoll.start()
        Qt.callLater(root.completeLoadingIfReady)
    }

    function applyPersistentSettings(view) {
        if (!view)
            return
        view.minSafeZoomScale = root.minSafeZoomScale
        view.maxSafeZoomScale = root.maxSafeZoomScale
        view.fitWidthRatio = root.fitWidthRatio
        view.fitPageWidthPoints = root.fitPageWidthPoints
        view.fitContentWidthPoints = root.fitContentWidthPoints
        view.fitContentCenterRatioX = root.fitContentCenterRatioX
        view.editHighlightText = root.editHighlightText
        view.findQuery = root.findQuery
        view.findResultIndex = root.findResultIndex
        root.applyWordSelection(view)
    }

    function transferViewState(fromView, toView, resetPosition) {
        if (!toView)
            return

        if (resetPosition || !fromView || !fromView.documentIsReady()) {
            toView.restorePositionPending = false
            toView.zoomScale = root.zoomScale
            return
        }

        try {
            fromView.captureScrollState()
            toView.savedPageIndex = fromView.savedPageIndex
            toView.savedPageHorizontalRatio = fromView.savedPageHorizontalRatio
            toView.savedPageVerticalRatio = fromView.savedPageVerticalRatio
            toView.savedRenderScale = fromView.savedRenderScale
            toView.restorePositionPending = fromView.restorePositionPending
            toView.zoomScale = fromView.zoomScale
        } catch (error) {
            toView.restorePositionPending = false
            toView.zoomScale = root.zoomScale
        }
    }

    function completeLoadingIfReady() {
        var view = root.loadingView
        if (!view || !view.documentIsReady() || view.pageCount <= 0)
            return

        lifecyclePoll.stop()

        // A newer successful render arrived while this native PDF was loading.
        // Never mutate this completed generation. Discard it while hidden and
        // instantiate one fresh viewer for the newest request instead.
        if (root.loadingToken !== root.requestedToken ||
                String(root.loadingSource) !== String(root.requestedSource)) {
            root.loadingSlot = -1
            root.loadingToken = -1
            Qt.callLater(root.beginLatestGeneration)
            return
        }

        // Refresh scroll/zoom from the still-visible old generation at the
        // promotion boundary so user interaction during the native load is not
        // lost.
        root.transferViewState(root.activeView, view, root.loadingResetPosition)
        if (!root.loadingResetPosition && view.restorePositionPending)
            view.restoreScrollState()

        root.activeSlot = root.loadingSlot
        root.loadingSlot = -1
        root.loadingToken = -1
        root.generationPending = false
        root.syncActiveStatus(view)
    }

    function syncActiveStatus(view) {
        if (!view)
            return
        root.synchronizingZoomFromActive = true
        root.zoomScale = view.zoomScale
        root.synchronizingZoomFromActive = false
        root.currentPageIndex = view.currentPageIndex
        root.pageCount = view.pageCount
    }

    function documentIsReady() {
        return root.activeView !== null && root.activeView.documentIsReady()
    }

    function forwardZoomRequest() {
        var view = root.activeView
        if (!view)
            return
        view.zoomAnchorX = root.zoomAnchorX
        view.zoomAnchorY = root.zoomAnchorY
        view.zoomTargetScale = root.zoomTargetScale
        view.zoomToken = root.zoomToken
    }

    function forwardPanRequest() {
        var view = root.activeView
        if (!view)
            return
        view.panDeltaX = root.panDeltaX
        view.panDeltaY = root.panDeltaY
        view.panToken = root.panToken
    }

    function forwardFitRequest() {
        var view = root.activeView
        if (!view)
            return
        view.fitWidthRatio = root.fitWidthRatio
        view.fitPageWidthPoints = root.fitPageWidthPoints
        view.fitContentWidthPoints = root.fitContentWidthPoints
        view.fitContentCenterRatioX = root.fitContentCenterRatioX
        view.fitToken = root.fitToken
    }

    function forwardSyncRequest() {
        var view = root.activeView
        if (!view)
            return
        view.syncPage = root.syncPage
        view.syncX = root.syncX
        view.syncY = root.syncY
        view.syncRecenterHorizontal = root.syncRecenterHorizontal
        view.syncToken = root.syncToken
    }

    onReloadTokenChanged: root.requestGeneration()

    onZoomScaleChanged: {
        if (root.synchronizingZoomFromActive)
            return
        var view = root.activeView
        if (view && Math.abs(view.zoomScale - root.zoomScale) > 0.0001)
            view.zoomScale = root.zoomScale
    }

    onMinSafeZoomScaleChanged: {
        if (root.activeView)
            root.activeView.minSafeZoomScale = root.minSafeZoomScale
        if (root.loadingView)
            root.loadingView.minSafeZoomScale = root.minSafeZoomScale
    }

    onMaxSafeZoomScaleChanged: {
        if (root.activeView)
            root.activeView.maxSafeZoomScale = root.maxSafeZoomScale
        if (root.loadingView)
            root.loadingView.maxSafeZoomScale = root.maxSafeZoomScale
    }

    onFitWidthRatioChanged: {
        if (root.activeView)
            root.activeView.fitWidthRatio = root.fitWidthRatio
        if (root.loadingView)
            root.loadingView.fitWidthRatio = root.fitWidthRatio
    }

    onFitTokenChanged: root.forwardFitRequest()
    onZoomTokenChanged: root.forwardZoomRequest()
    onPanTokenChanged: root.forwardPanRequest()
    onSyncTokenChanged: root.forwardSyncRequest()

    onSelectedWordTextChanged: root.applyWordSelection(root.activeView)
    onSelectedWordPageChanged: root.applyWordSelection(root.activeView)
    onSelectedWordRectsChanged: root.applyWordSelection(root.activeView)
    onMouseSelectionHeldChanged: root.applyWordSelection(root.activeView)

    onFindQueryChanged: {
        if (root.activeView) root.activeView.findQuery = root.findQuery
        if (root.loadingView) root.loadingView.findQuery = root.findQuery
    }
    onFindResultIndexChanged: {
        if (root.activeView) root.activeView.findResultIndex = root.findResultIndex
        if (root.loadingView) root.loadingView.findResultIndex = root.findResultIndex
    }

    onEditHighlightTextChanged: {
        if (root.activeView)
            root.activeView.editHighlightText = root.editHighlightText
        if (root.loadingView)
            root.loadingView.editHighlightText = root.editHighlightText
    }

    Component {
        id: generationComponent
        SelectablePdfGenerationView { }
    }

    Loader {
        id: slotA
        anchors.fill: parent
        active: false
        visible: root.activeSlot === 0
        sourceComponent: generationComponent
        onLoaded: root.configureLoadingView(0, item)
    }

    Loader {
        id: slotB
        anchors.fill: parent
        active: false
        visible: root.activeSlot === 1
        sourceComponent: generationComponent
        onLoaded: root.configureLoadingView(1, item)
    }

    Connections {
        target: root.activeView
        ignoreUnknownSignals: true
        function onCopyWordRequested(text) { root.copyWordRequested(text) }

        function onZoomScaleChanged() {
            if (!root.activeView)
                return
            root.synchronizingZoomFromActive = true
            root.zoomScale = root.activeView.zoomScale
            root.synchronizingZoomFromActive = false
        }

        function onCurrentPageIndexChanged() {
            if (root.activeView)
                root.currentPageIndex = root.activeView.currentPageIndex
        }

        function onPageCountChanged() {
            if (root.activeView && !root.generationPending)
                root.pageCount = root.activeView.pageCount
        }
    }

    Connections {
        target: root.loadingView
        ignoreUnknownSignals: true

        function onPageCountChanged() {
            root.completeLoadingIfReady()
        }
    }

    Timer {
        id: recreateInactiveSlot
        interval: 0
        repeat: false
        onTriggered: {
            if (root.loadingSlot < 0)
                return
            root.loaderForSlot(root.loadingSlot).active = true
        }
    }

    // Poll native readiness, not elapsed time. The timer does not decide when a
    // handoff is safe; it merely observes the PdfDocument lifecycle exposed by
    // the freshly-created generation view.
    Timer {
        id: lifecyclePoll
        interval: 25
        repeat: true
        onTriggered: root.completeLoadingIfReady()
    }
}
