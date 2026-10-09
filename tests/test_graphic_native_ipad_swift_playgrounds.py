from pathlib import Path
import re


def test_native_ipad_swift_playgrounds_package_is_shipped() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
    manifest = (package / "Package.swift").read_text(encoding="utf-8")
    app = (package / "NDGraphicApp.swift").read_text(encoding="utf-8")
    canvas = (package / "Views/PencilCanvasView.swift").read_text(encoding="utf-8")
    bridge = (package / "Services/GraphicBridgeClient.swift").read_text(encoding="utf-8")
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")

    assert "import AppleProductTypes" in manifest
    assert ".iOSApplication(" in manifest
    assert ".pad" in manifest
    assert 'bundleIdentifier: "com.nd.mindmirror.graphic"' in manifest
    assert re.search(r'displayVersion: "\d+\.\d+\.\d+"', manifest)
    assert ".localNetwork(" not in manifest
    assert ".outgoingNetworkConnections()" not in manifest
    assert "@main" in app
    assert "NDGraphicBootstrapView" in app
    assert 'Text("ND Graphic \\(displayVersion)")' in app
    assert "import PencilKit" in canvas
    controller = (package / "Services/ActiveDrawingToolController.swift").read_text(encoding="utf-8")
    assert "PKInkingTool(" in controller
    assert ".pencil" in controller
    assert "PKEraserTool" in controller
    assert "NWListener(" in bridge
    assert "newConnectionHandler" in bridge
    assert '"type": "ipad_listener"' in bridge
    assert "listenerPort: UInt16 = 8768" in bridge
    assert "update_graphic" in bridge
    assert "Text(graphicContextTitle)" in content
    assert 'Button("Start listening for Ubuntu")' in content
    assert 'connectionScreen' in content
    assert '.sheet(isPresented: $showLiveSyncSettings)' in content
    assert 'saveCurrentState(' in content
    assert 'currentOperation' in bridge
    assert 'operation' in (package / "Models/GraphicMessage.swift").read_text(encoding="utf-8")
