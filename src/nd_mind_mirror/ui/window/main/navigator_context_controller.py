"""Replace the long Navigator context menu with semantic actions and repository-aware sharing."""

from configparser import ConfigParser
from pathlib import Path
import shutil
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox


class NavigatorContextController:
    """Own Navigator context actions, file copy/paste, and repository-aware sharing."""

    def __init__(self, file_system_panel, pin_callback=None) -> None:
        """Replace the panel's flat context menu and install Navigator-only shortcuts."""
        self._panel = file_system_panel
        self._tree = file_system_panel._tree
        self._pin_callback = pin_callback
        self._copied_path: Path | None = None

        try:
            self._tree.customContextMenuRequested.disconnect(file_system_panel._show_context_menu)
        except (RuntimeError, TypeError):
            pass
        self._tree.customContextMenuRequested.connect(self.show_menu)

        self._copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self._tree)
        self._copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._copy_shortcut.activated.connect(self.copy_selected_path)

        self._paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self._tree)
        self._paste_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._paste_shortcut.activated.connect(self.paste_into_selected_path)

    def show_menu(self, position) -> None:
        """Show Copy/Paste plus grouped Open, Copy/Share, Create, and Manage actions."""
        index = self._tree.indexAt(position)
        if not index.isValid():
            return
        path = Path(self._panel._path_for_view_index(index))
        menu = QMenu(self._panel)

        copy_item = menu.addAction("Copy")
        copy_item.setShortcut(QKeySequence("Ctrl+C"))
        copy_item.triggered.connect(lambda: self.copy_path(path))

        paste_item = menu.addAction("Paste")
        paste_item.setShortcut(QKeySequence("Ctrl+V"))
        paste_item.setEnabled(self._can_paste_copied_path())
        paste_item.triggered.connect(lambda: self.paste_into_path(path))
        menu.addSeparator()

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

    def copy_selected_path(self) -> None:
        """Store the currently selected Navigator file/folder for an in-app copy operation."""
        selected = self._panel.selected_path()
        if selected:
            self.copy_path(Path(selected))

    def copy_path(self, path: Path) -> None:
        """Store a concrete existing file or folder as the Navigator copy source."""
        try:
            source = path.expanduser().resolve()
        except OSError as exc:
            QMessageBox.warning(self._panel, "Copy", str(exc))
            return
        if not source.exists():
            QMessageBox.warning(self._panel, "Copy", f"{source.name} no longer exists.")
            return
        self._copied_path = source

    def paste_into_selected_path(self) -> None:
        """Paste the Navigator copy into the selected folder, preserving clipboard-image fallback."""
        selected = self._panel.selected_path()
        if not selected:
            return
        target_path = Path(selected)
        if self._can_paste_copied_path():
            self.paste_into_path(target_path)
            return
        directory = self._panel._target_directory(target_path)
        self._panel._save_current_clipboard_image(directory, one_shot=False)

    def paste_into_path(self, path: Path) -> None:
        """Copy the stored source into path or its parent, prompting only on a name collision."""
        source = self._copied_path
        if source is None or not source.exists():
            self._copied_path = None
            return

        destination = self._panel._target_directory(path)
        try:
            destination = destination.expanduser().resolve()
        except OSError as exc:
            QMessageBox.warning(self._panel, "Paste", str(exc))
            return
        if not destination.is_dir():
            QMessageBox.warning(self._panel, "Paste", "The paste destination is not a folder.")
            return
        if source.is_dir() and self._is_same_or_child(destination, source):
            QMessageBox.warning(
                self._panel,
                "Paste",
                "A folder cannot be copied into itself or one of its descendants.",
            )
            return

        target = destination / source.name
        if target.exists():
            target = self._prompt_collision_target(source, destination)
            if target is None:
                return

        try:
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        except OSError as exc:
            QMessageBox.critical(self._panel, "Paste", str(exc))
            return

        self._panel._proxy_model.invalidateFilter()
        self._panel.path_created.emit(str(target))
        self._panel.select_path(target, force_reveal=True)
        self._panel.state_changed.emit()

    def _prompt_collision_target(self, source: Path, destination: Path) -> Path | None:
        """Suggest source_0, source_1, ... while preserving a file extension."""
        suggested = self._next_available_target(source, destination)
        while True:
            name, accepted = QInputDialog.getText(
                self._panel,
                "Paste",
                "An item with this name already exists. New name:",
                text=suggested.name,
            )
            if not accepted:
                return None
            normalized = name.strip()
            if not normalized or normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
                QMessageBox.warning(self._panel, "Paste", "Enter a valid file or folder name.")
                continue
            target = destination / normalized
            if target.exists():
                QMessageBox.warning(self._panel, "Paste", f"{normalized} already exists.")
                suggested = self._next_available_target(source, destination)
                continue
            return target

    @staticmethod
    def _next_available_target(source: Path, destination: Path) -> Path:
        """Return source_0, source_1, ... using a suffix-aware name for files."""
        if source.is_dir():
            base_name = source.name
            extension = ""
        else:
            extension = source.suffix
            base_name = source.name[:-len(extension)] if extension else source.name
        counter = 0
        while True:
            candidate = destination / f"{base_name}_{counter}{extension}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _can_paste_copied_path(self) -> bool:
        """Return whether the internal Navigator copy source still exists."""
        return self._copied_path is not None and self._copied_path.exists()

    @staticmethod
    def _is_same_or_child(candidate: Path, parent: Path) -> bool:
        """Return whether candidate resolves to parent or a descendant of parent."""
        try:
            candidate.resolve().relative_to(parent.resolve())
            return True
        except (OSError, ValueError):
            return False

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
