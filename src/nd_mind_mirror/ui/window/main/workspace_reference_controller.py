"""Share fast workspace-reference resolution across Preview, Visual, rename, navigation, and delete."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import RecursiveInputResolver
from nd_mind_mirror.core.render.latex.latex_preview_source_builder import LatexPreviewSourceBuilder
from nd_mind_mirror.core.render.latex.latex_renderer import LatexRenderer
from nd_mind_mirror.core.workspace.path.path_reference_updater import PathReferenceUpdater
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    ReferenceOccurrence,
    WorkspaceReferenceResolver,
)
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.panel.editor.editor_panel import EditorPanel
from nd_mind_mirror.ui.panel.file_system.file_system_panel import FileSystemPanel


class _ReferenceDeleteDialog(QDialog):
    """List usages before the application's ordinary delete confirmation."""

    def __init__(self, window, target: Path, usages: list[ReferenceOccurrence], parent=None) -> None:
        super().__init__(parent)
        self._window = window
        self._usages = list(usages)
        self.setWindowTitle("Delete — file references")
        self.resize(900, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{target}\n\nThis path is used in {len(usages)} reference(s). "
                "Double-click an item or press Enter to open that source location."
            )
        )
        self._list = QListWidget(self)
        for index, usage in enumerate(self._usages):
            item = QListWidgetItem(
                f"{usage.referring_file}  —  line {usage.line}  —  "
                f"\\{usage.command}{{{usage.raw_target}}}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._activate)
        self._list.itemActivated.connect(self._activate)
        layout.addWidget(self._list, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setText("Continue to Delete…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _activate(self, item: QListWidgetItem) -> None:
        try:
            usage = self._usages[int(item.data(Qt.ItemDataRole.UserRole))]
        except (TypeError, ValueError, IndexError):
            return
        WorkspaceReferenceController.jump_to_usage(self._window, usage)


class WorkspaceReferenceController:
    """Install one shared, demand-driven reference-resolution layer."""

    _installed = False
    _original_renderer_init: Callable | None = None
    _original_renderer_apply: Callable | None = None
    _original_environment: Callable | None = None
    _original_preview_build: Callable | None = None
    _original_recursive_source: Callable | None = None
    _original_recursive_target: Callable | None = None
    _original_visual_graphic: Callable | None = None
    _original_visual_raw_text: Callable | None = None
    _original_panel_bold: Callable | None = None
    _original_key_press: Callable | None = None
    _original_delete: Callable | None = None

    @classmethod
    def install(cls) -> None:
        """Install hooks once before MainWindow creates renderer/editors."""
        if cls._installed:
            return
        cls._install_renderer()
        cls._install_recursive_input()
        cls._install_visual()
        cls._install_rename()
        cls._install_ctrl_b()
        cls._install_delete()
        cls._installed = True

    @staticmethod
    def _settings_root(owner) -> Path | None:
        settings = getattr(owner, "_app_settings", None)
        if settings is None:
            window = None
            try:
                window = owner.window()
            except (AttributeError, RuntimeError):
                pass
            if window is None:
                try:
                    window = owner.parent()
                except (AttributeError, RuntimeError):
                    pass
            settings = getattr(window, "_app_settings", None)
        value = getattr(settings, "search_default_path", None)
        if value in (None, ""):
            return None
        try:
            return Path(value).expanduser().resolve(strict=False)
        except OSError:
            return Path(value).expanduser()

    @classmethod
    def _resolver_for_renderer(cls, renderer: LatexRenderer) -> WorkspaceReferenceResolver:
        root = cls._settings_root(renderer)
        resolver = getattr(renderer, "_nd_workspace_reference_resolver", None)
        if not isinstance(resolver, WorkspaceReferenceResolver):
            resolver = WorkspaceReferenceResolver(root)
            renderer._nd_workspace_reference_resolver = resolver
        elif resolver.default_path != root:
            resolver.set_default_path(root)
        renderer._input_resolver._nd_reference_default_path = root
        renderer._preview_source_builder._nd_workspace_reference_resolver = resolver
        return resolver

    @classmethod
    def _install_renderer(cls) -> None:
        cls._original_renderer_init = LatexRenderer.__init__
        cls._original_renderer_apply = LatexRenderer.apply_settings
        cls._original_environment = LatexRenderer._build_process_environment
        cls._original_preview_build = LatexPreviewSourceBuilder.build

        def renderer_init(renderer: LatexRenderer, *args, **kwargs) -> None:
            cls._original_renderer_init(renderer, *args, **kwargs)
            cls._resolver_for_renderer(renderer)

        def renderer_apply(renderer: LatexRenderer, *args, **kwargs) -> None:
            cls._original_renderer_apply(renderer, *args, **kwargs)
            cls._resolver_for_renderer(renderer)

        def environment(renderer: LatexRenderer, working_directory: Path):
            result = cls._original_environment(renderer, working_directory)
            root = cls._resolver_for_renderer(renderer).default_path
            if root is None:
                return result
            recursive = f"{root}//"
            for name in ("TEXINPUTS", "BIBINPUTS", "BSTINPUTS"):
                existing = result.value(name, "")
                if recursive not in [part for part in existing.split(":") if part]:
                    result.insert(name, recursive + (":" + existing if existing else ":"))
            return result

        def preview_build(builder: LatexPreviewSourceBuilder, *args, **kwargs) -> str:
            prepared = cls._original_preview_build(builder, *args, **kwargs)
            resolver = getattr(builder, "_nd_workspace_reference_resolver", None)
            if not isinstance(resolver, WorkspaceReferenceResolver):
                return prepared
            source_path = kwargs.get("source_path")
            if source_path is None and len(args) >= 2:
                source_path = args[1]
            return resolver.rewrite_preview_links(prepared, source_path)

        LatexRenderer.__init__ = renderer_init
        LatexRenderer.apply_settings = renderer_apply
        LatexRenderer._build_process_environment = environment
        LatexPreviewSourceBuilder.build = preview_build

    @classmethod
    def _install_recursive_input(cls) -> None:
        cls._original_recursive_source = RecursiveInputResolver._resolve_source
        cls._original_recursive_target = RecursiveInputResolver._resolve_target

        def resolve_source(
            input_resolver: RecursiveInputResolver,
            source: str,
            containing_file: Path,
            stack: set[Path],
            context: str,
            inherited_heading: str | None,
            heading_mapping: dict[str, str],
        ):
            root = getattr(input_resolver, "_nd_reference_default_path", None)
            if root not in (None, ""):
                source = WorkspaceReferenceResolver(root).rewrite_preview_links(source, containing_file)
            return cls._original_recursive_source(
                input_resolver,
                source,
                containing_file,
                stack,
                context,
                inherited_heading,
                heading_mapping,
            )

        def resolve_target(
            input_resolver: RecursiveInputResolver,
            containing_file: Path,
            target: str,
        ) -> Path | None:
            result = cls._original_recursive_target(input_resolver, containing_file, target)
            if result is not None:
                return result
            root = getattr(input_resolver, "_nd_reference_default_path", None)
            if root in (None, ""):
                return None
            return WorkspaceReferenceResolver(root).resolve(
                target,
                containing_file,
                command="input",
                require_exists=True,
            )

        RecursiveInputResolver._resolve_source = resolve_source
        RecursiveInputResolver._resolve_target = resolve_target

    @classmethod
    def _install_visual(cls) -> None:
        cls._original_visual_graphic = LatexVisualEditor._insert_graphic_block
        cls._original_visual_raw_text = LatexVisualEditor._visual_raw_inline_text

        def raw_text(visual_class, raw: str) -> str:
            match = re.fullmatch(
                r"\\href\s*\{[^{}\n]+\}\s*\{(?P<label>[^{}\n]*)\}",
                str(raw),
            )
            if match is not None:
                return match.group("label")
            return cls._original_visual_raw_text(raw)

        def graphic(
            visual: LatexVisualEditor,
            cursor,
            raw: str,
            graphic_path: str,
            source_line: int = 0,
        ) -> None:
            display_path = graphic_path
            source_path = getattr(visual, "_source_path", None)
            if source_path is not None:
                resolved = WorkspaceReferenceResolver(cls._settings_root(visual)).resolve(
                    graphic_path,
                    source_path,
                    command="includegraphics",
                    require_exists=True,
                )
                if resolved is not None:
                    display_path = resolved.as_posix()
            cls._original_visual_graphic(
                visual,
                cursor,
                raw,
                display_path,
                source_line=source_line,
            )

        LatexVisualEditor._visual_raw_inline_text = classmethod(raw_text)
        LatexVisualEditor._insert_graphic_block = graphic

    @staticmethod
    def _install_rename() -> None:
        def match_path(
            updater_class,
            token: str,
            *,
            referring_file: Path,
            workspace_root: Path,
            old_path: Path,
        ) -> tuple[str, Path, bool] | None:
            return WorkspaceReferenceResolver(workspace_root).match_candidate(
                token,
                referring_file,
                old_path,
                suffix_hint=old_path.suffix,
            )

        PathReferenceUpdater._match_reference_path = classmethod(match_path)

    @classmethod
    def _reference_at_editor_cursor(cls, editor: LatexEditor) -> ReferenceOccurrence | None:
        source_path = getattr(editor, "source_path", None)
        if source_path is None:
            return None
        source = editor.toPlainText()
        if str(getattr(editor, "edit_mode", "source")) == "visual":
            try:
                _anchor, (line, column) = editor._visual_editor.source_selection_locations()
                offset = WorkspaceReferenceResolver.source_offset(source, line, column)
            except (AttributeError, TypeError, ValueError):
                return None
        else:
            try:
                offset = int(editor.textCursor().position())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return None
        return WorkspaceReferenceResolver(cls._settings_root(editor)).occurrence_at(
            source,
            source_path,
            offset,
        )

    @classmethod
    def _open_reference(cls, editor: LatexEditor) -> bool:
        occurrence = cls._reference_at_editor_cursor(editor)
        if occurrence is None or occurrence.target_path is None:
            return False
        try:
            editor.window()._open_path(
                str(occurrence.target_path),
                select=True,
                reveal_in_navigator=True,
            )
            return True
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    @classmethod
    def _install_ctrl_b(cls) -> None:
        cls._original_panel_bold = EditorPanel.bold_current_selection
        cls._original_key_press = LatexEditor.keyPressEvent

        def panel_bold(panel: EditorPanel) -> None:
            editor = panel.current_editor()
            if isinstance(editor, LatexEditor) and cls._open_reference(editor):
                return
            cls._original_panel_bold(panel)

        def key_press(editor: LatexEditor, event) -> None:
            ctrl_b = (
                event.key() == Qt.Key.Key_B
                and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                and not bool(
                    event.modifiers()
                    & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
                )
            )
            if ctrl_b and cls._open_reference(editor):
                event.accept()
                return
            cls._original_key_press(editor, event)

        EditorPanel.bold_current_selection = panel_bold
        LatexEditor.keyPressEvent = key_press

    @classmethod
    def _install_delete(cls) -> None:
        cls._original_delete = FileSystemPanel._delete_path

        def delete_path(panel: FileSystemPanel, path: Path) -> None:
            target = Path(path).expanduser().resolve(strict=False)
            window = panel.window()
            settings = getattr(window, "_app_settings", None)
            root = getattr(settings, "search_default_path", panel._root_path)
            resolver = WorkspaceReferenceResolver(root)
            usages = resolver.find_usages(
                root,
                target,
                ignore_file_path=getattr(settings, "search_ignore_file_path", None),
            )
            if usages:
                if _ReferenceDeleteDialog(window, target, usages, parent=panel).exec() != QDialog.DialogCode.Accepted:
                    return

            connected = False

            def after_deleted(deleted_path: str) -> None:
                nonlocal connected
                deleted = Path(deleted_path).expanduser().resolve(strict=False)
                if deleted != target:
                    return
                if connected:
                    try:
                        panel.path_deleted.disconnect(after_deleted)
                    except (RuntimeError, TypeError):
                        pass
                    connected = False
                if usages:
                    cls._remove_usage_references(window, target, usages, resolver)

            if usages:
                panel.path_deleted.connect(after_deleted)
                connected = True
            cls._original_delete(panel, path)
            if connected and target.exists():
                try:
                    panel.path_deleted.disconnect(after_deleted)
                except (RuntimeError, TypeError):
                    pass

        FileSystemPanel._delete_path = delete_path

    @staticmethod
    def jump_to_usage(window, usage: ReferenceOccurrence) -> None:
        """Open a referring file and jump to its reference line."""
        try:
            window._open_path(str(usage.referring_file), select=True, reveal_in_navigator=True)
            editor = window._editor_panel.current_editor()
            if isinstance(editor, LatexEditor):
                editor.go_to_source_location(usage.line, usage.column, align_top=True)
            elif editor is not None:
                editor.go_to_line(usage.line, align_top=True)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    @classmethod
    def _remove_usage_references(
        cls,
        window,
        target: Path,
        usages: list[ReferenceOccurrence],
        resolver: WorkspaceReferenceResolver,
    ) -> None:
        panel = getattr(window, "_editor_panel", None)
        for referring_file in sorted({usage.referring_file for usage in usages}):
            if cls._same_or_child(referring_file, target):
                continue
            editor = None
            if panel is not None:
                for candidate, candidate_path in list(getattr(panel, "_paths", {}).items()):
                    if Path(candidate_path).resolve(strict=False) == referring_file.resolve(strict=False):
                        editor = candidate
                        break
            try:
                source = editor.toPlainText() if editor is not None else referring_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError, AttributeError):
                continue
            updated = resolver.remove_references(source, referring_file, target)
            if updated == source:
                continue
            try:
                referring_file.write_text(updated, encoding="utf-8")
            except OSError:
                continue
            if editor is not None:
                try:
                    editor.set_content(updated)
                except (AttributeError, RuntimeError):
                    pass
        search = getattr(window, "_search_window", None)
        if search is not None:
            try:
                search.rebuild_index()
            except (AttributeError, RuntimeError):
                pass

    @staticmethod
    def _same_or_child(candidate: Path, root: Path) -> bool:
        candidate = candidate.resolve(strict=False)
        root = root.resolve(strict=False)
        if candidate == root:
            return True
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False
