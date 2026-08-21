"""Replace the long Navigator context menu with semantic lateral submenus and GitHub actions."""

from configparser import ConfigParser
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu


class NavigatorContextController:
    """Group Navigator commands and provide repository-aware Copy/Open GitHub URL actions."""

    def __init__(self, file_system_panel, pin_callback=None) -> None:
        """Replace the panel's original flat context-menu slot with grouped submenus."""
        self._panel = file_system_panel
        self._tree = file_system_panel._tree
        self._pin_callback = pin_callback
        try:
            self._tree.customContextMenuRequested.disconnect(file_system_panel._show_context_menu)
        except (RuntimeError, TypeError):
            pass
        self._tree.customContextMenuRequested.connect(self.show_menu)

    def show_menu(self, position) -> None:
        """Show Open, Copy/Share, Create, and Manage submenus for the selected path."""
        index = self._tree.indexAt(position)
        if not index.isValid():
            return
        path = Path(self._panel._path_for_view_index(index))
        menu = QMenu(self._panel)
        open_menu = menu.addMenu("Open")
        copy_menu = menu.addMenu("Copy / Share")
        create_menu = menu.addMenu("Create")
        manage_menu = menu.addMenu("Manage")

        open_files = open_menu.addAction("Open in Files")
        open_files.triggered.connect(lambda: self._panel._open_in_file_manager(path))

        managed_graphic = (
            path.suffix.lower() == ".ndgraphic"
            or (path.suffix.lower() == ".png" and path.with_suffix(".ndgraphic").is_file())
        )
        if managed_graphic:
            edit_ipad = open_menu.addAction("Edit image in iPad…")
            edit_ipad.triggered.connect(
                lambda: self._panel.graphic_edit_requested.emit(str(path.expanduser().resolve()))
            )
        if path.is_file() and self._pin_callback is not None:
            pin_action = open_menu.addAction("Pin File in Tabs")
            pin_action.triggered.connect(lambda: self._pin_callback(path))

        copy_path = copy_menu.addAction("Copy Absolute Path")
        copy_path.triggered.connect(
            lambda: QApplication.clipboard().setText(str(path.expanduser().resolve()))
        )
        copy_name = copy_menu.addAction("Copy File Name")
        copy_name.triggered.connect(lambda: QApplication.clipboard().setText(path.name))

        github_url = self._github_url(path)
        copy_github = copy_menu.addAction("Copy GitHub URL")
        open_github = copy_menu.addAction("Open GitHub URL")
        copy_github.setEnabled(bool(github_url))
        open_github.setEnabled(bool(github_url))
        copy_github.triggered.connect(lambda: QApplication.clipboard().setText(github_url))
        open_github.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(github_url)))

        paste_image = create_menu.addAction("Paste Clipboard Image Here")
        paste_image.triggered.connect(
            lambda: self._panel._save_current_clipboard_image(
                self._panel._target_directory(path), one_shot=False
            )
        )
        new_latex = create_menu.addAction("New LaTeX File…")
        new_latex.triggered.connect(lambda: self._panel._create_file(path, latex=True))
        new_file = create_menu.addAction("New File…")
        new_file.triggered.connect(lambda: self._panel._create_file(path, latex=False))
        new_folder = create_menu.addAction("New Folder…")
        new_folder.triggered.connect(lambda: self._panel._create_folder(path))

        rename = manage_menu.addAction("Rename…")
        delete = manage_menu.addAction("Delete…")
        rename.setEnabled(path != self._panel._root_path)
        delete.setEnabled(path != self._panel._root_path)
        rename.triggered.connect(lambda: self._panel._rename_path(path))
        delete.triggered.connect(lambda: self._panel._delete_path(path))

        menu.exec(self._tree.viewport().mapToGlobal(position))

    def _github_url(self, path: Path) -> str:
        """Return a blob/tree URL for the nearest GitHub-backed repository containing path."""
        repo_root, git_dir = self._find_git_root(path)
        if repo_root is None or git_dir is None:
            return ""
        remote = self._github_remote(git_dir)
        if not remote:
            return ""
        branch = self._branch_name(git_dir) or "main"
        try:
            relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
        except (OSError, ValueError):
            return ""
        if not relative or relative == ".":
            return remote
        kind = "tree" if path.is_dir() else "blob"
        return f"{remote}/{kind}/{quote(branch, safe='')}/{quote(relative, safe='/')}"

    @staticmethod
    def _find_git_root(path: Path) -> tuple[Path | None, Path | None]:
        """Walk upward from a file or directory until a Git metadata directory is found."""
        current = path if path.is_dir() else path.parent
        for candidate in (current, *current.parents):
            dot_git = candidate / ".git"
            if dot_git.is_dir():
                return candidate, dot_git
            if dot_git.is_file():
                try:
                    text = dot_git.read_text(encoding="utf-8").strip()
                except OSError:
                    continue
                if text.startswith("gitdir:"):
                    resolved = (candidate / text.split(":", 1)[1].strip()).resolve()
                    if resolved.is_dir():
                        return candidate, resolved
        return None, None

    @staticmethod
    def _github_remote(git_dir: Path) -> str:
        """Read the preferred Git remote and normalize GitHub SSH/HTTPS syntax to an HTTPS repository URL."""
        parser = ConfigParser()
        config_path = git_dir / "config"
        if not config_path.is_file():
            try:
                common_dir = (
                    git_dir / (git_dir / "commondir").read_text(encoding="utf-8").strip()
                ).resolve()
                config_path = common_dir / "config"
            except OSError:
                pass
        try:
            parser.read(config_path, encoding="utf-8")
        except (OSError, ValueError):
            return ""
        sections = [section for section in parser.sections() if section.startswith('remote "')]
        sections.sort(key=lambda section: (0 if section == 'remote "origin"' else 1, section))
        for section in sections:
            raw = parser.get(section, "url", fallback="").strip()
            normalized = NavigatorContextController._normalize_github_remote(raw)
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _normalize_github_remote(raw: str) -> str:
        """Convert common GitHub SSH and HTTPS remote forms into a browser repository URL."""
        value = str(raw).strip()
        if value.startswith("git@github.com:"):
            value = "https://github.com/" + value.split(":", 1)[1]
        elif value.startswith("ssh://git@github.com/"):
            value = "https://github.com/" + value.split("github.com/", 1)[1]
        elif not value.startswith("https://github.com/"):
            return ""
        return value[:-4] if value.endswith(".git") else value.rstrip("/")

    @staticmethod
    def _branch_name(git_dir: Path) -> str:
        """Read the checked-out branch from HEAD and return an empty string for detached heads."""
        try:
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        prefix = "ref: refs/heads/"
        return head[len(prefix):] if head.startswith(prefix) else ""
