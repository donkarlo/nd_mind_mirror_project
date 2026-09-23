"""Regression for Mind Mirror-owned graphic bridge startup."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = (
    ROOT
    / "src/nd_mind_mirror/core/settings/defaults/settings.yaml"
).read_text(encoding="utf-8")


def test_graphic_bridge_autostarts_with_mind_mirror_by_default() -> None:
    graphic_section = DEFAULT_SETTINGS.split("\ngraphic:\n", 1)[1]
    assert "  auto_start_bridge: true" in graphic_section
