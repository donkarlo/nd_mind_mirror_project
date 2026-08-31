"""FIX11 desktop behavior for hierarchical search, image drag/edit, and batch delete."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QMenu, QMessageBox

from nd_mind_mirror.core.clipboard.image.image_mime_reference_resolver import ImageMimeReferenceResolver
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import WorkspaceReferenceResolver
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.panel.file_system.file_system_panel import FileSystemPanel
from nd_mind_mirror.ui.search.thread.file_search_thread import FileSearchThread
from nd_mind_mirror.ui.window.main.main_window import MainWindow


class Fix11DesktopController:
    """Install focused class-level behavior before ordinary user interaction."""

    _installed = False
    _original_search_init: Callable | None = None
    _original_insert_from_mime: Callable | None = None
    _original_clicked: Callable | None = None
    _original_context_menu: Callable | None = None
    _original_edit_graphic: Callable | None = None

    _IMAGE_SUFFIXES = {
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"
    }

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return
        cls._install_hierarchical_search()
        cls._install_exact_image_drop()
        cls._install_navigator_behavior()
        cls._install_edit_any_image()
        cls._installed = True

    @classmethod
    def _install_hierarchical_search(cls) -> None:
        cls._original_search_init = FileSearchThread.__init__

        def search_init(thread, generation, entries, query, max_results, fuzzy_threshold,
                        hierarchical_path_matching=True, parent=None) -> None:
            raw = str(query)
            chain = [part.strip().casefold() for part in raw.split(">") if part.strip()]
            leaf_query = chain[-1] if len(chain) >= 2 else raw
            cls._original_search_init(
                thread,
                generation,
                entries,
                leaf_query,
                max_results,
                fuzzy_threshold,
                hierarchical_path_matching,
                parent,
            )
            thread._nd_hierarchy_chain = chain if len(chain) >= 2 else []

        def run(thread) -> None:
            chain = list(getattr(thread, "_nd_hierarchy_chain", []))
            if not chain:
                return cls._run_plain_search(thread)

            scored_results = []
            for entry in thread._entries:
                if thread.isInterruptionRequested():
                    return
                path_text, name_text, stem_text, normalized_name, normalized_stem, is_directory, relative_path = entry
                score = cls._score_hierarchy(thread, relative_path, name_text, stem_text, chain)
                if score is None:
                    continue
                scored_results.append((score, 0 if is_directory else 1, path_text))

            scored_results.sort(
                key=lambda item: (-item[0], item[1], len(Path(item[2]).name), item[2].casefold())
            )
            truncated = len(scored_results) > thread._max_results
            thread.results_ready.emit(
                thread._generation,
                [path for _, _, path in scored_results[:thread._max_results]],
                truncated,
            )

        FileSearchThread.__init__ = search_init
        FileSearchThread.run = run

    @staticmethod
    def _run_plain_search(thread) -> None:
        if not thread._tokens:
            thread.results_ready.emit(thread._generation, [], False)
            return
        scored_results = []
        for path_text, name_text, stem_text, normalized_name, normalized_stem, is_directory, relative_path in thread._entries:
            if thread.isInterruptionRequested():
                return
            score = thread._score_name(
                name_text=name_text,
                stem_text=stem_text,
                name=normalized_name,
                stem=normalized_stem,
            )
            if (
                score is None
                and thread._hierarchical_path_matching
                and not thread._strict_filename_query
                and len(thread._tokens) >= 2
            ):
                score = thread._score_hierarchical_path(relative_path)
            if score is not None:
                scored_results.append((score, 0 if is_directory else 1, path_text))
        scored_results.sort(
            key=lambda item: (-item[0], item[1], len(Path(item[2]).name), item[2].casefold())
        )
        truncated = len(scored_results) > thread._max_results
        thread.results_ready.emit(
            thread._generation,
            [path for _, _, path in scored_results[:thread._max_results]],
            truncated,
        )

    @staticmethod
    def _score_hierarchy(thread, relative_path: str, name_text: str, stem_text: str, chain: list[str]) -> float | None:
        components = [part for part in Path(relative_path).parts if part]
        if not components:
            return None
        child_name = Path(components[-1]).name
        child_stem = Path(child_name).stem
        leaf = chain[-1]
        leaf_score = thread._score_token(
            token=leaf,
            name=child_name.casefold(),
            stem=child_stem.casefold(),
            name_text=child_name,
            stem_text=child_stem,
        )
        if leaf_score is None:
            return None

        ancestors = components[:-1]
        search_from = 0
        parent_score = 0.0
        for token in chain[:-1]:
            matched = None
            for index in range(search_from, len(ancestors)):
                component = ancestors[index]
                stem = Path(component).stem
                score = thread._score_token(
                    token=token,
                    name=component.casefold(),
                    stem=stem.casefold(),
                    name_text=component,
                    stem_text=stem,
                )
                if score is None:
                    score = thread._family_prefix_score(token, stem.casefold())
                if score is not None:
                    matched = (index, score)
                    break
            if matched is None:
                return None
            search_from = matched[0] + 1
            parent_score += matched[1]
        return min(5.0, 3.6 + leaf_score * 0.25 + parent_score * 0.08)

    @classmethod
    def _install_exact_image_drop(cls) -> None:
        cls._original_insert_from_mime = LatexEditor.insertFromMimeData
        resolver = ImageMimeReferenceResolver()

        def insert_from_mime(editor: LatexEditor, source) -> None:
            image_path = resolver.local_image_path(source)
            if image_path is None and source.hasFormat("application/x-qabstractitemmodeldatalist"):
                try:
                    selected = editor.window()._file_system_panel.selected_path()
                    candidate = Path(selected).expanduser().resolve() if selected else None
                except (AttributeError, OSError, RuntimeError, ValueError):
                    candidate = None
                if candidate is not None and candidate.is_file() and candidate.suffix.lower() in cls._IMAGE_SUFFIXES:
                    image_path = candidate

            if image_path is None:
                cls._original_insert_from_mime(editor, source)
                return

            relative = os.path.relpath(image_path, start=editor.source_path.parent)
            editor._insert_figure(Path(relative).as_posix())

        LatexEditor.insertFromMimeData = insert_from_mime

    @classmethod
    def _install_navigator_behavior(cls) -> None:
        cls._original_clicked = FileSystemPanel._on_clicked
        cls._original_context_menu = FileSystemPanel._show_context_menu

        from nd_mind_mirror.ui.window.main.workspace_interaction_controller import WorkspaceInteractionController
        original_workspace_init = WorkspaceInteractionController.__init__
        original_workspace_menu = WorkspaceInteractionController._show_navigator_menu

        def workspace_init(controller, main_window) -> None:
            original_workspace_init(controller, main_window)
            controller._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        def workspace_menu(controller, position) -> None:
            index = controller._tree.indexAt(position)
            if not index.isValid():
                original_workspace_menu(controller, position)
                return
            text = controller._panel._path_for_view_index(index)
            path = Path(text).expanduser() if text else None
            if path is None or path.suffix.lower() not in cls._IMAGE_SUFFIXES:
                original_workspace_menu(controller, position)
                return

            cls._ensure_image_sidecar(controller._window, path)
            if path.suffix.lower() == ".png":
                original_workspace_menu(controller, position)
                return

            menu = QMenu(controller._panel)
            edit = menu.addAction("Edit image in iPad…")
            more = menu.addAction("More actions…")
            chosen = menu.exec(controller._tree.viewport().mapToGlobal(position))
            if chosen == edit:
                controller._panel.graphic_edit_requested.emit(str(path.resolve()))
            elif chosen == more:
                original_workspace_menu(controller, position)

        WorkspaceInteractionController.__init__ = workspace_init
        WorkspaceInteractionController._show_navigator_menu = workspace_menu

        def clicked(panel: FileSystemPanel, index) -> None:
            panel._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            if index.isValid():
                panel.state_changed.emit()

        def delete_selected(panel: FileSystemPanel) -> bool:
            panel._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            selection = panel._tree.selectionModel()
            indexes = selection.selectedRows(0) if selection is not None else []
            paths = []
            for index in indexes:
                text = panel._path_for_view_index(index)
                if not text:
                    continue
                try:
                    path = Path(text).expanduser().resolve()
                except OSError:
                    continue
                if path != panel._root_path and path.exists():
                    paths.append(path)
            if not paths:
                selected = panel.selected_path()
                if selected:
                    path = Path(selected).expanduser().resolve()
                    if path != panel._root_path and path.exists():
                        paths = [path]
            paths = cls._top_level_paths(paths)
            if not paths:
                return False

            decision = QMessageBox.question(
                panel,
                "Delete selected paths",
                "Delete the selected file(s)/folder(s)?\n\n"
                "Yes: search the source root and remove LaTeX commands that reference them.\n"
                "No: delete the paths only.\n"
                "Cancel: do nothing.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                return True
            remove_references = decision == QMessageBox.StandardButton.Yes

            usages_by_target = {}
            resolver = None
            window = panel.window()
            if remove_references:
                settings = getattr(window, "_app_settings", None)
                root = Path(getattr(settings, "search_default_path", panel._root_path)).expanduser().resolve()
                resolver = WorkspaceReferenceResolver(root)
                ignore_path = getattr(settings, "search_ignore_file_path", None)
                for target in paths:
                    usages_by_target[target] = resolver.find_usages(root, target, ignore_file_path=ignore_path)

            for target in sorted(paths, key=lambda value: len(value.parts), reverse=True):
                try:
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                except OSError as exc:
                    QMessageBox.critical(panel, "Delete", f"{target}\n\n{exc}")
                    continue
                panel.path_deleted.emit(str(target))

                if remove_references and resolver is not None:
                    usages = usages_by_target.get(target, [])
                    if usages:
                        from nd_mind_mirror.ui.window.main.workspace_reference_controller import WorkspaceReferenceController
                        WorkspaceReferenceController._remove_usage_references(window, target, usages, resolver)

            panel.state_changed.emit()
            return True

        def context_menu(panel: FileSystemPanel, position) -> None:
            panel._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            index = panel._tree.indexAt(position)
            if not index.isValid():
                cls._original_context_menu(panel, position)
                return
            path_text = panel._path_for_view_index(index)
            path = Path(path_text).expanduser() if path_text else None
            if path is None or path.suffix.lower() not in cls._IMAGE_SUFFIXES:
                cls._original_context_menu(panel, position)
                return

            menu = QMenu(panel)
            edit = menu.addAction("Edit image in iPad…")
            more = menu.addAction("More actions…")
            chosen = menu.exec(panel._tree.viewport().mapToGlobal(position))
            if chosen == edit:
                panel.graphic_edit_requested.emit(str(path.resolve()))
            elif chosen == more:
                cls._original_context_menu(panel, position)

        FileSystemPanel._on_clicked = clicked
        FileSystemPanel._delete_selected_path = delete_selected
        FileSystemPanel._show_context_menu = context_menu

    @staticmethod
    def _top_level_paths(paths: list[Path]) -> list[Path]:
        unique = sorted(set(paths), key=lambda value: len(value.parts))
        result = []
        for path in unique:
            if any(Fix11DesktopController._is_child(path, parent) for parent in result):
                continue
            result.append(path)
        return result

    @staticmethod
    def _is_child(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return path != parent
        except ValueError:
            return False

    @classmethod
    def _install_edit_any_image(cls) -> None:
        cls._original_edit_graphic = MainWindow._edit_graphic_from_navigator

        def edit_graphic(window: MainWindow, path_text: str) -> None:
            try:
                path = Path(path_text).expanduser().resolve()
            except (OSError, ValueError):
                return
            if path.is_file() and path.suffix.lower() in cls._IMAGE_SUFFIXES:
                if not cls._ensure_image_sidecar(window, path):
                    return
            cls._original_edit_graphic(window, str(path))

        MainWindow._edit_graphic_from_navigator = edit_graphic

    @classmethod
    def _ensure_image_sidecar(cls, window, path: Path) -> bool:
        try:
            path = Path(path).expanduser().resolve()
        except (OSError, ValueError):
            return False
        if not path.is_file() or path.suffix.lower() not in cls._IMAGE_SUFFIXES:
            return False
        sidecar = path.with_suffix(".ndgraphic")
        if sidecar.is_file():
            return True
        settings = getattr(window, "_app_settings", None)
        if settings is None:
            return False
        manager = GraphicDocumentManager(
            directory_name=settings.graphic_directory_name,
            width_ratio=settings.graphic_width_ratio,
            canvas_width=settings.graphic_canvas_width,
            canvas_height=settings.graphic_canvas_height,
        )
        try:
            manager._write_sidecar(sidecar, path, None)
        except OSError as exc:
            QMessageBox.critical(window, "Edit image in iPad", str(exc))
            return False
        return True
