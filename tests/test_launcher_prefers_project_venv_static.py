from pathlib import Path


def test_launcher_prefers_phd_venv_and_has_diagnostics() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "nd_mind_mirror_project").read_text(encoding="utf-8")
    app = (
        root
        / "src"
        / "nd_mind_mirror"
        / "app"
        / "mind_mirror_application.py"
    ).read_text(encoding="utf-8")

    assert 'Path.home() / "phd-venv" / "bin" / "python"' in launcher
    assert "ND_MIND_MIRROR_PYTHON" in launcher
    assert "os.execve" in launcher
    assert "startup.log" in launcher
    assert "ensure_linux_desktop_integration" not in app
    assert "QApplication lastWindowClosed" in app
