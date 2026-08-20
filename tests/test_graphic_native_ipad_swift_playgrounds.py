from pathlib import Path


def test_native_ipad_swift_playgrounds_package_is_shipped() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
    manifest = (package / "Package.swift").read_text(encoding="utf-8")
    app = (package / "NDGraphicApp.swift").read_text(encoding="utf-8")
    canvas = (package / "Views/PencilCanvasView.swift").read_text(encoding="utf-8")
    bridge = (package / "Services/GraphicBridgeClient.swift").read_text(encoding="utf-8")
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")
    info_plist = (package / "Info.plist").read_text(encoding="utf-8")
    permission = (package / "Services/LocalNetworkPermissionRequester.swift").read_text(encoding="utf-8")

    assert "import AppleProductTypes" in manifest
    assert ".iOSApplication(" in manifest
    assert ".pad" in manifest
    assert ".localNetwork(" in manifest
    assert "_ndmindmirror._tcp" in manifest
    assert "additionalInfoPlistContentFilePath" in manifest
    assert "@main" in app
    assert "NDGraphicBootstrapView" in app
    assert "ND Graphic 0.30" in app
    assert "import PencilKit" in canvas
    assert "PKInkingTool(" in canvas
    assert ".pencil" in canvas
    assert "PKEraserTool" in canvas
    assert "import Network" in bridge
    assert "NWConnection(to: .url(url), using: parameters)" in bridge
    assert "NWProtocolWebSocket.Options" in bridge
    assert "URLSessionWebSocketTask" not in bridge
    assert "update_graphic" in bridge
    assert 'Text("ND Graphic v0.30")' in content
    assert 'connectionScreen' in content
    assert '.sheet(' not in content
    assert 'scheduleAutosave' in content
    assert 'currentOperation' in bridge
    assert 'operation' in (package / "Models/GraphicMessage.swift").read_text(encoding="utf-8")
    assert "NSAllowsLocalNetworking" in info_plist
    assert "NWBrowser" in permission

