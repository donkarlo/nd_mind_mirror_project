"""Provide multi-path Copy/Cut/Paste semantics for the Navigator."""

from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import QItemSelectionModel, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
)

from nd_mind_mirror.ui.window.main.navigator_context_controller import (
    NavigatorContextController,
)


class NavigatorMultiPathContextController(NavigatorContextController):
    """Extend Navigator context actions to multi-selection Copy, Cut, and Paste."""

    def __init__(self, file_system_panel, pin_callback=None) -> None:
        """Install multi-selection and Navigator-only clipboard shortcuts."""
        self._clipboard_paths: list[Path] = []
        self._clipboard_mode = ""
        super().__init__(file_system_panel, pin_callback)

        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self._cut_shortcut = QShortcut(QKeySequence("Ctrl+X"), self._tree)
        self._cut_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._cut_shortcut.activated.connect(self.cut_selected_paths)

    @classmethod
    def replace(
        cls,
        existing,
        file_system_panel,
        pin_callback=None,
    ) -> "NavigatorMultiPathContextController":
        """Replace the previous single-path controller without leaving duplicate shortcuts."""
        if existing is not None:
            try:
                file_system_panel._tree.customContextMenuRequested.disconnect(
                    existing.show_menu
                )
            except (RuntimeError, TypeError):
                pass
            for name in ("_copy_shortcut", "_paste_shortcut"):
                shortcut = getattr(existing, name, None)
                if shortcut is None:
                    continue
                try:
                    shortcut.setEnabled(False)
                    shortcut.deleteLater()
                except RuntimeError:
                    pass
        return cls(file_system_panel, pin_callback)

    def show_menu(self, position) -> None:
        """Show Copy/Cut/Paste for the clicked row while preserving a multi-selection."""
        index = self._tree.indexAt(position)
        if not index.isValid():
            return
        path = Path(self._panel._path_for_view_index(index))
        self._prepare_context_selection(index)
        selected_paths = self.selected_paths()

        menu = QMenu(self._panel)

        copy_item = menu.addAction("Copy")
        copy_item.setShortcut(QKeySequence("Ctrl+C"))
        copy_item.setEnabled(bool(selected_paths))
        copy_item.triggered.connect(self.copy_selected_path)

        cut_item = menu.addAction("Cut")
        cut_item.setShortcut(QKeySequence("Ctrl+X"))
        cut_item.setEnabled(bool(selected_paths))
        cut_item.triggered.connect(self.cut_selected_paths)

        paste_item = menu.addAction("Paste")
        paste_item.setShortcut(QKeySequence("Ctrl+V"))
        paste_item.setEnabled(self.can_paste())
        paste_item.triggered.connect(lambda: self.paste_into_path(path))
        menu.addSeparator()

        open_menu = menu.addMenu("Open")
        copy_menu = menu.addMenu("Copy / Share")
        create_menu = menu.addMenu("Create")
        manage_menu = menu.addMenu("Manage")

        open_files = open_menu.addAction("Open in Files")
        open_files.triggered.connect(
            lambda: self._panel._open_in_file_manager(path)
        )

        managed_graphic = (
            path.suffix.lower() == ".ndgraphic"
            or (
                path.suffix.lower() == ".png"
                and path.with_suffix(".ndgraphic").is_file()
            )
        )
        if managed_graphic:
            edit_ipad = open_menu.addAction("Edit image in iPad…")
            edit_ipad.triggered.connect(
                lambda: self._panel.graphic_edit_requested.emit(
                    str(path.expanduser().resolve())
                )
            )
        if path.is_file() and self._pin_callback is not None:
            pin_action = open_menu.addAction("Pin File in Tabs")
            pin_action.triggered.connect(lambda: self._pin_callback(path))

        copy_path = copy_menu.addAction("Copy Absolute Path")
        copy_path.triggered.connect(self._copy_selected_absolute_paths)
        copy_name = copy_menu.addAction("Copy File Name")
        copy_name.triggered.connect(self._copy_selected_names)

        github_url = self._github_url(path)
        copy_github = copy_menu.addAction("Copy GitHub URL")
        open_github = copy_menu.addAction("Open GitHub URL")
        copy_github.setEnabled(bool(github_url))
        open_github.setEnabled(bool(github_url))
        copy_github.triggered.connect(
            lambda: QApplication.clipboard().setText(github_url)
        )
        open_github.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(github_url))
        )

        paste_image = create_menu.addAction("Paste Clipboard Image Here")
        paste_image.triggered.connect(
            lambda: self._panel._save_current_clipboard_image(
                self._panel._target_directory(path),
                one_shot=False,
            )
        )
        new_latex = create_menu.addAction("New LaTeX File…")
        new_latex.triggered.connect(
            lambda: self._panel._create_file(path, latex=True)
        )
        new_file = create_menu.addAction("New File…")
        new_file.triggered.connect(
            lambda: self._panel._create_file(path, latex=False)
        )
        new_folder = create_menu.addAction("New Folder…")
        new_folder.triggered.connect(lambda: self._panel._create_folder(path))

        rename = manage_menu.addAction("Rename…")
        delete = manage_menu.addAction("Delete…")
        single_selection = len(selected_paths) == 1
        rename.setEnabled(
            single_selection and path != self._panel._root_path
        )
        delete.setEnabled(bool(selected_paths))
        rename.triggered.connect(lambda: self._panel._rename_path(path))
        if len(selected_paths) > 1:
            delete.triggered.connect(self._panel._delete_selected_path)
        else:
            delete.triggered.connect(lambda: self._panel._delete_path(path))

        menu.exec(self._tree.viewport().mapToGlobal(position))

    def copy_selected_path(self) -> None:
        """Store every Ctrl/Shift-selected top-level path for copying."""
        self._store_selection("copy")

    def cut_selected_paths(self) -> None:
        """Store every Ctrl/Shift-selected top-level path for a later move."""
        self._store_selection("cut")

    def paste_into_selected_path(self) -> None:
        """Paste the internal file clipboard into the current Navigator destination."""
        selected = self._panel.selected_path()
        if not selected:
            return
        if self.can_paste():
            self.paste_into_path(Path(selected))
            return
        directory = self._panel._target_directory(Path(selected))
        self._panel._save_current_clipboard_image(
            directory,
            one_shot=False,
        )

    def paste_into_path(self, path: Path) -> None:
        """Paste all stored paths into a folder or the selected file's parent."""
        sources = self._existing_clipboard_paths()
        if not sources:
            return

        try:
            destination = self._panel._target_directory(path).expanduser().resolve()
        except OSError as exc:
            QMessageBox.warning(self._panel, "Paste", str(exc))
            return
        if not destination.is_dir():
            QMessageBox.warning(
                self._panel,
                "Paste",
                "The paste destination is not a folder.",
            )
            return

        mappings = self._destination_mappings(sources, destination)
        if mappings is None:
            return

        if self._clipboard_mode == "cut":
            self._paste_cut(mappings)
            return
        self._paste_copy(mappings)

    def can_paste(self) -> bool:
        """Return whether the internal Navigator clipboard still has live sources."""
        return bool(self._existing_clipboard_paths())

    def selected_paths(self) -> list[Path]:
        """Return selected existing paths, collapsed so selected parents own descendants."""
        selection = self._tree.selectionModel()
        indexes = selection.selectedRows(0) if selection is not None else []
        paths: list[Path] = []
        for index in indexes:
            raw_path = self._panel._path_for_view_index(index)
            if not raw_path:
                continue
            try:
                candidate = Path(raw_path).expanduser().resolve()
            except OSError:
                continue
            if candidate == self._panel._root_path or not candidate.exists():
                continue
            paths.append(candidate)
        return self._top_level_paths(paths)

    def _prepare_context_selection(self, index) -> None:
        """Keep a right-clicked selected row in its group; otherwise select it alone."""
        selection = self._tree.selectionModel()
        if selection is None:
            return
        if selection.isSelected(index):
            selection.setCurrentIndex(
                index,
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )
            return
        selection.select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        selection.setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.NoUpdate,
        )

    def _store_selection(self, mode: str) -> None:
        """Capture a stable path list for Copy or Cut."""
        paths = self.selected_paths()
        if not paths:
            return
        self._clipboard_paths = paths
        self._clipboard_mode = mode
        action = "Copied" if mode == "copy" else "Cut"
        self._panel.window().statusBar().showMessage(
            f"{action} {len(paths)} Navigator item(s).",
            2500,
        )

    def _existing_clipboard_paths(self) -> list[Path]:
        """Drop stale sources while preserving clipboard order."""
        existing = [
            path
            for path in self._clipboard_paths
            if path.exists() or path.is_symlink()
        ]
        self._clipboard_paths = existing
        if not existing:
            self._clipboard_mode = ""
        return list(existing)

    def _destination_mappings(
        self,
        sources: list[Path],
        destination: Path,
    ) -> list[tuple[Path, Path]] | None:
        """Resolve every destination, prompting with name_0/name_1 on collisions."""
        mappings: list[tuple[Path, Path]] = []
        reserved: set[Path] = set()
        for source in sources:
            if source.is_dir() and self._is_same_or_child(destination, source):
                QMessageBox.warning(
                    self._panel,
                    "Paste",
                    f"{source.name} cannot be pasted into itself or one of its descendants.",
                )
                return None

            target = (destination / source.name).resolve(strict=False)
            if target.exists() or target.is_symlink() or target in reserved:
                target = self._prompt_collision_target(
                    source,
                    destination,
                    reserved,
                )
                if target is None:
                    return None
            reserved.add(target)
            mappings.append((source, target))
        return mappings

    def _paste_cut(self, mappings: list[tuple[Path, Path]]) -> None:
        """Queue Cut/Paste through the existing background move/reference pipeline."""
        window = self._panel.window()
        controller = getattr(
            window,
            "_workspace_filesystem_operation_controller",
            None,
        )
        request_moves = getattr(controller, "request_moves", None)
        if not callable(request_moves):
            QMessageBox.warning(
                self._panel,
                "Paste",
                "The background workspace move controller is not available.",
            )
            return

        for source, _target in mappings:
            self._panel.path_about_to_move.emit(str(source))
        if request_moves(mappings):
            window.statusBar().showMessage(
                f"Moving {len(mappings)} cut item(s) in the background…",
                3000,
            )

    def _paste_copy(self, mappings: list[tuple[Path, Path]]) -> None:
        """Copy every selected source and publish the created paths to Navigator."""
        created: list[Path] = []
        errors: list[str] = []
        for source, target in mappings:
            try:
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
                created.append(target.resolve(strict=False))
            except OSError as exc:
                errors.append(f"{source}: {exc}")

        if created:
            self._panel._proxy_model.invalidateFilter()
            for target in created:
                self._panel.path_created.emit(str(target))
            self._panel.select_path(created[-1], force_reveal=True)
            self._panel.state_changed.emit()

        if errors:
            QMessageBox.critical(
                self._panel,
                "Paste",
                "\n\n".join(errors[:8]),
            )

    def _prompt_collision_target(
        self,
        source: Path,
        destination: Path,
        reserved: set[Path],
    ) -> Path | None:
        """Offer the first source_0/source_1 name and validate a user override."""
        suggested = self._next_available_target(
            source,
            destination,
            reserved,
        )
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
            if (
                not normalized
                or normalized in {".", ".."}
                or "/" in normalized
                or "\\" in normalized
            ):
                QMessageBox.warning(
                    self._panel,
                    "Paste",
                    "Enter a valid file or folder name.",
                )
                continue
            target = (destination / normalized).resolve(strict=False)
            if target.exists() or target.is_symlink() or target in reserved:
                QMessageBox.warning(
                    self._panel,
                    "Paste",
                    f"{normalized} already exists.",
                )
                suggested = self._next_available_target(
                    source,
                    destination,
                    reserved,
                )
                continue
            return target

    @staticmethod
    def _next_available_target(
        source: Path,
        destination: Path,
        reserved: set[Path],
    ) -> Path:
        """Return source_0, source_1, ... while preserving a file extension."""
        if source.is_dir():
            base_name = source.name
            extension = ""
        else:
            extension = source.suffix
            base_name = (
                source.name[: -len(extension)]
                if extension
                else source.name
            )
        counter = 0
        while True:
            candidate = (
                destination / f"{base_name}_{counter}{extension}"
            ).resolve(strict=False)
            if (
                not candidate.exists()
                and not candidate.is_symlink()
                and candidate not in reserved
            ):
                return candidate
            counter += 1

    def _copy_selected_absolute_paths(self) -> None:
        """Copy all selected absolute paths, one per line."""
        paths = self.selected_paths()
        if paths:
            QApplication.clipboard().setText(
                "\n".join(str(path) for path in paths)
            )

    def _copy_selected_names(self) -> None:
        """Copy all selected basenames, one per line."""
        paths = self.selected_paths()
        if paths:
            QApplication.clipboard().setText(
                "\n".join(path.name for path in paths)
            )

    @classmethod
    def _top_level_paths(cls, paths: list[Path]) -> list[Path]:
        """Deduplicate selections and remove children whose parent is selected."""
        unique = sorted(set(paths), key=lambda item: len(item.parts))
        result: list[Path] = []
        for path in unique:
            if any(cls._is_same_or_child(path, parent) for parent in result):
                continue
            result.append(path)
        return result
