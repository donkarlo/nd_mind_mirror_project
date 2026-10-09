from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"


def read(relative: str) -> str:
    return (PACKAGE / relative).read_text(encoding="utf-8")


def test_toolbar_visibility_is_persisted_and_controlled_from_gear_settings() -> None:
    store = read("Services/DrawingToolbarSettingsStore.swift")
    settings = read("Views/DrawingToolbarSettingsSectionView.swift")
    content = read("Views/ContentView.swift")

    assert 'static let visible = "graphic.drawing.toolbar.visible"' in store
    assert 'Toggle(' in settings
    assert '"Show drawing toolbar"' in settings
    assert "toolbarSettings.setToolbarVisible" in settings
    assert "if toolbarSettings.isToolbarVisible" in content


def test_top_toolbar_and_quick_palette_share_one_persisted_order() -> None:
    store = read("Services/DrawingToolbarSettingsStore.swift")
    toolbar = read("Views/DrawingToolbarView.swift")
    quick = read("Views/QuickDrawingToolPaletteView.swift")
    settings = read("Views/DrawingToolbarSettingsSectionView.swift")

    shared_expression = "toolbarSettings.items(for: savedTools.tools)"
    assert shared_expression in toolbar
    assert shared_expression in quick
    assert 'static let order = "graphic.drawing.toolbar.order.v1"' in store
    assert ".onMove" in settings
    assert "toolbarSettings.move(" in settings


def test_lasso_and_import_image_are_part_of_shared_order() -> None:
    model = read("Models/DrawingToolbarItem.swift")
    store = read("Services/DrawingToolbarSettingsStore.swift")

    assert "case lasso" in model
    assert "case addImage" in model
    assert "DrawingToolbarItem.lasso.id" in store
    assert "DrawingToolbarItem.addImage.id" in store


def test_photo_import_handler_survives_hidden_toolbar() -> None:
    content = read("Views/ContentView.swift")

    drawing_screen = content.split(
        "    private var drawingScreen: some View {", 1
    )[1].split(
        "    private func loadRemoteDocument(token: Int) {", 1
    )[0]

    assert ".onChange(of: selectedPhotoItem)" in drawing_screen
    conditional = drawing_screen.split(
        "if toolbarSettings.isToolbarVisible", 1
    )[1].split("MeasurementRulerFrameView(", 1)[0]
    assert ".onChange(of: selectedPhotoItem)" not in conditional


def test_primary_image_header_contains_active_icon_and_canvas_size_before_back() -> None:
    content = read("Views/ContentView.swift")
    indicator = read("Views/ActiveToolHeaderIndicatorView.swift")
    header = content.split("    private var header: some View {", 1)[1].split(
        "    private var connectionScreen: some View {", 1
    )[0]

    icon = header.index("ActiveToolHeaderIndicatorView(activeTool: activeTool)")
    dimensions = header.index('Text("\\(Int(canvasWidth)) × \\(Int(canvasHeight))")')
    back = header.index("Button(action: navigateBack)")
    assert icon < dimensions < back
    assert "Image(systemName: symbolName)" in indicator
    assert "activeTool.color.opacity(activeTool.opacity)" in indicator
    assert "statusBar" not in content
    assert 'Text("Ubuntu ' not in content


def test_image_header_does_not_duplicate_history_controls() -> None:
    header = read("Views/HeaderDrawingControlsView.swift")
    content = read("Views/ContentView.swift")
    quick_palette = read("Views/QuickDrawingToolPaletteView.swift")

    assert "onRedo" not in header and "onUndo" not in header
    assert 'image: "ruler"' in header
    assert 'image: "square.grid.3x3"' in header
    assert "onRedo: performRedo" in content
    assert "onUndo: performUndo" in content
    assert "onRedo" in quick_palette and "onUndo" in quick_palette


def test_ipad_status_bar_area_has_same_editor_background() -> None:
    app = read("NDGraphicApp.swift")
    content = read("Views/ContentView.swift")

    assert "(openWorkspace ? Color(uiColor: .systemBackground) : Color.indigo)" in app
    assert "VStack(spacing: 0)" in content
    assert ".ignoresSafeArea(edges: .top)" in content
