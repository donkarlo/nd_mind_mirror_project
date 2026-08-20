from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browser_graphic_client_remains_available_as_fallback() -> None:
    js = (ROOT / "src/nd_mind_mirror/graphic/web/app.js").read_text(encoding="utf-8")
    assert "ev.pressure" in js
    assert "pointerType" in js
    assert "update_graphic" in js
    assert "web_strokes" in js
    assert "toDataURL('image/png')" in js


def test_native_swift_playgrounds_client_is_active_without_xcode() -> None:
    assert (ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm").exists()
    assert (ROOT / "src/nd_mind_mirror/graphic/native_future/ipad_xcode").exists()


def test_bridge_still_serves_optional_graphic_web_application() -> None:
    server = (ROOT / "src/nd_mind_mirror/graphic/bridge/server.py").read_text(encoding="utf-8")
    assert 'self.app.mount("/graphic"' in server
    assert '"web_strokes"' in server
