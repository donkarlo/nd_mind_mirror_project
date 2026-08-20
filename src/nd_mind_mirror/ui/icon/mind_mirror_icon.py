from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import sys

from PySide6.QtGui import QIcon


_DESKTOP_ID = "nd-mind-mirror"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _packaged_icon_path() -> Path:
    return _project_root() / "resources" / "icons" / "mind_mirror.png"


def build_mind_mirror_icon(size: int = 128) -> QIcon:
    """Load the static Mind Mirror icon without doing runtime painting."""
    del size
    icon_path = _packaged_icon_path()
    if icon_path.is_file():
        return QIcon(str(icon_path))
    return QIcon()


def ensure_linux_desktop_integration(launcher: str | Path) -> None:
    """Install a safe per-user GNOME desktop identity.

    This routine only copies an already packaged PNG.  It deliberately avoids
    QPainter/QPixmap work during application startup because desktop
    integration must never destabilize the editor.
    """
    if not sys.platform.startswith("linux"):
        return

    try:
        launcher_path = Path(launcher).expanduser().resolve()
        source_icon = _packaged_icon_path()
        data_home = Path.home() / ".local" / "share"
        applications_dir = data_home / "applications"
        icon_dir = data_home / "icons" / "hicolor" / "256x256" / "apps"
        applications_dir.mkdir(parents=True, exist_ok=True)
        icon_dir.mkdir(parents=True, exist_ok=True)

        installed_icon = icon_dir / f"{_DESKTOP_ID}.png"
        if source_icon.is_file():
            shutil.copyfile(source_icon, installed_icon)

        icon_value = str(installed_icon) if installed_icon.is_file() else _DESKTOP_ID
        desktop_path = applications_dir / f"{_DESKTOP_ID}.desktop"
        desktop_path.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=Mind Mirror",
                    f"Exec={shlex.quote(str(launcher_path))}",
                    f"Icon={icon_value}",
                    "Terminal=false",
                    "StartupNotify=true",
                    "StartupWMClass=nd_mind_mirror_project",
                    "Categories=Office;Development;",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        desktop_path.chmod(0o755)
    except (OSError, shutil.Error):
        return
