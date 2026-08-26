"""Compatibility facade plus stable selection, tab paths, search ignore, and navigator multi-select."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMenu,
    QMessageBox,
    QStyle,
    QStyleOptionMenuItem,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QStylePainter,
    QToolButton,
)

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.input.ctrl_tab.ctrl_tab_event_filter import CtrlTabEventFilter
from nd_mind_mirror.ui.panel.file_system.file_system_panel import FileSystemPanel
from nd_mind_mirror.ui.search.thread.file_search_index_thread import FileSearchIndexThread
from nd_mind_mirror.ui.switcher.recent_file.recent_file_switcher import RecentFileSwitcher
from nd_mind_mirror.ui.window.main.pinned_tab_controller import PinnedTabController
from nd_mind_mirror.ui.window.main import visual_persian_font_core as _core

VisualPersianFontController = _core.VisualPersianFontController
PersianVisualFontHighlighter = _core.PersianVisualFontHighlighter

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_PROJECT_IGNORE_FILE = _PROJECT_ROOT / ".mindmirrorsearchignore"
_ROLE_FILE_NAME = int(Qt.ItemDataRole.UserRole) + 11
_ROLE_PATH_CONTEXT = int(Qt.ItemDataRole.UserRole) + 12


def _selection_preview_text(editor: LatexEditor) -> str:
    shared = getattr(editor, "_nd_shared_selection", None)
    if shared:
        return str(shared[2] or "")
    return ""


def _source_selection_state(editor: LatexEditor):
    cursor = editor.textCursor()
    if not cursor.hasSelection():
        return None
    anchor = editor._source_location_for_position(cursor.anchor())
    position = editor._source_location_for_position(cursor.position())
    try:
        preview_text = str(_ORIGINAL_ACTIVE_PREVIEW_TEXT(editor) or "")
    except Exception:
        preview_text = cursor.selectedText().replace("\u2029", "\n")
    return anchor, position, preview_text


def _visual_selection_state(editor: LatexEditor):
    visual = editor._visual_editor
    cursor = visual.textCursor()
    if not cursor.hasSelection():
        return None
    anchor, position = visual.source_selection_locations()
    try:
        preview_text = str(_ORIGINAL_ACTIVE_PREVIEW_TEXT(editor) or "")
    except Exception:
        preview_text = cursor.selectedText().replace("\u2029", "\n")
    return anchor, position, preview_text


def _restore_shared_selection(editor: LatexEditor, ensure_visible: bool = False) -> None:
    shared = getattr(editor, "_nd_shared_selection", None)
    if not shared:
        return
    anchor, position, _preview_text = shared
    editor._syncing_cursor_views = True
    try:
        editor._set_source_selection_from_locations(anchor, position)
        editor._visual_editor.set_selection_from_source_locations(
            anchor,
            position,
            ensure_visible=ensure_visible,
        )
    finally:
        editor._syncing_cursor_views = False


def _editor_init(editor: LatexEditor, *args, **kwargs) -> None:
    _ORIGINAL_EDITOR_INIT(editor, *args, **kwargs)
    editor._nd_shared_selection = None
    editor._nd_switching_mode = False


def _source_cursor_changed(editor: LatexEditor) -> None:
    if (
        not getattr(editor, "_nd_switching_mode", False)
        and getattr(editor, "_edit_mode", "source") == "source"
    ):
        editor._nd_shared_selection = _source_selection_state(editor)
    _ORIGINAL_SOURCE_CURSOR_CHANGED(editor)


def _visual_cursor_changed(editor: LatexEditor) -> None:
    if (
        not getattr(editor, "_nd_switching_mode", False)
        and getattr(editor, "_edit_mode", "source") == "visual"
    ):
        editor._nd_shared_selection = _visual_selection_state(editor)
    _ORIGINAL_VISUAL_CURSOR_CHANGED(editor)


def _set_edit_mode(editor: LatexEditor, mode: str) -> None:
    if getattr(editor, "_edit_mode", "source") == "visual":
        state = _visual_selection_state(editor)
    else:
        state = _source_selection_state(editor)
    if state is not None:
        editor._nd_shared_selection = state

    editor._nd_switching_mode = True
    try:
        _ORIGINAL_SET_EDIT_MODE(editor, mode)
    finally:
        editor._nd_switching_mode = False

    if getattr(editor, "_nd_shared_selection", None):
        _restore_shared_selection(editor, ensure_visible=True)
        editor.active_cursor_changed.emit()


def _qt_pdf_selection_item(view):
    cached = getattr(view, "_nd_pdf_selection_item", None)
    if cached is not None:
        try:
            if cached.metaObject().indexOfProperty("selectedText") >= 0:
                return cached
        except RuntimeError:
            pass

    root = view.rootObject()
    if root is None:
        return None

    candidates = [root]
    try:
        candidates.extend(root.findChildren(QObject))
    except (AttributeError, RuntimeError):
        pass

    first = None
    for item in candidates:
        try:
            meta = item.metaObject()
            if meta.indexOfProperty("selectedText") < 0:
                continue
            if first is None:
                first = item
            value = str(item.property("selectedText") or "").strip()
            if value:
                view._nd_pdf_selection_item = item
                return item
        except (AttributeError, RuntimeError, TypeError):
            continue

    if first is not None:
        view._nd_pdf_selection_item = first
    return first


def _read_pdf_selection(view) -> str:
    item = _qt_pdf_selection_item(view)
    if item is None:
        return ""
    try:
        value = item.property("selectedText")
    except (AttributeError, RuntimeError):
        return ""
    return str(value or "").replace("\u2029", "\n").strip()


def _set_editor_selection_from_preview(editor: LatexEditor, selected_text: str) -> bool:
    applied = _ORIGINAL_SET_SELECTION_FROM_PREVIEW(editor, selected_text)
    if not applied:
        return False
    cursor = editor.textCursor()
    if cursor.hasSelection():
        anchor = editor._source_location_for_position(cursor.anchor())
        position = editor._source_location_for_position(cursor.position())
        editor._nd_shared_selection = (
            anchor,
            position,
            str(selected_text or "").strip(),
        )
        _restore_shared_selection(editor, ensure_visible=False)
    return True


def _path_context(path: str | Path) -> str:
    candidate = Path(path)
    parts = list(candidate.parent.parts)
    try:
        repo_index = parts.index("repo")
        parent_parts = parts[repo_index + 1 :]
    except ValueError:
        parent_parts = [part for part in parts if part not in {"/", ""}]
    if not parent_parts:
        return ""
    if len(parent_parts) == 1:
        return parent_parts[0]
    if len(parent_parts) == 2:
        return f"{parent_parts[0]}/{parent_parts[-1]}"
    return f"{parent_parts[0]}/…/{parent_parts[-1]}"


def _small_path_font(base_font: QFont) -> QFont:
    result = QFont(base_font)
    point_size = base_font.pointSizeF()
    if point_size <= 0:
        point_size = float(base_font.pointSize())
    if point_size <= 0:
        point_size = 10.0
    result.setPointSizeF(max(point_size - 1.5, 7.0))
    return result


class _PathMenu(QMenu):
    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        for action in self.actions():
            rect = self.actionGeometry(action)
            if not rect.intersects(event.rect()):
                continue
            option = QStyleOptionMenuItem()
            self.initStyleOption(option, action)
            data = action.data()
            if not isinstance(data, dict):
                painter.drawControl(QStyle.ControlElement.CE_MenuItem, option)
                continue
            option.text = ""
            painter.drawControl(QStyle.ControlElement.CE_MenuItem, option)
            name = str(data.get("name", ""))
            context = str(data.get("context", ""))
            name_font = QFont(self.font())
            path_font = _small_path_font(name_font)
            name_metrics = QFontMetrics(name_font)
            path_metrics = QFontMetrics(path_font)
            left = rect.left() + 12
            right = rect.right() - 10
            baseline = rect.center().y() + name_metrics.ascent() // 2 - 1
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            if selected:
                name_color = option.palette.color(QPalette.ColorRole.HighlightedText)
                path_color = name_color
            else:
                name_color = option.palette.color(QPalette.ColorRole.Text)
                path_color = QColor(128, 128, 128)
            painter.setFont(name_font)
            painter.setPen(name_color)
            painter.drawText(left, baseline, name)
            path_left = left + name_metrics.horizontalAdvance(name) + 12
            if context and path_left < right:
                rendered = path_metrics.elidedText(
                    context,
                    Qt.TextElideMode.ElideMiddle,
                    max(right - path_left, 0),
                )
                painter.setFont(path_font)
                painter.setPen(path_color)
                painter.drawText(path_left, baseline, rendered)


class _RecentPathDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        widget = option.widget
        style = widget.style() if widget is not None else QApplication.style()
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, widget)
        name = str(index.data(_ROLE_FILE_NAME) or index.data(Qt.ItemDataRole.DisplayRole) or "")
        context = str(index.data(_ROLE_PATH_CONTEXT) or "")
        name_font = QFont(option.font)
        path_font = _small_path_font(name_font)
        name_metrics = QFontMetrics(name_font)
        path_metrics = QFontMetrics(path_font)
        rect = option.rect.adjusted(8, 0, -8, 0)
        baseline = rect.center().y() + name_metrics.ascent() // 2 - 1
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            name_color = option.palette.color(QPalette.ColorRole.HighlightedText)
            path_color = name_color
        else:
            name_color = option.palette.color(QPalette.ColorRole.Text)
            path_color = QColor(128, 128, 128)
        painter.save()
        painter.setFont(name_font)
        painter.setPen(name_color)
        painter.drawText(rect.left(), baseline, name)
        path_left = rect.left() + name_metrics.horizontalAdvance(name) + 12
        if context and path_left < rect.right():
            rendered = path_metrics.elidedText(
                context,
                Qt.TextElideMode.ElideMiddle,
                rect.right() - path_left,
            )
            painter.setFont(path_font)
            painter.setPen(path_color)
            painter.drawText(path_left, baseline, rendered)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(base.height(), 30))


def _show_tab_row_menu(controller: PinnedTabController, button: QToolButton, paths) -> None:
    current_paths = list(paths)
    menu = _PathMenu(button)
    for path in current_paths:
        candidate = Path(path)
        name = candidate.name
        context = _path_context(candidate)
        action = menu.addAction(f"{name}    {context}")
        action.setData({"name": name, "context": context, "path": str(candidate)})
        action.setToolTip(str(candidate))
        action.triggered.connect(
            lambda _checked=False, selected_path=path: controller._activate_path(selected_path)
        )
    if not current_paths:
        empty = menu.addAction("(empty)")
        empty.setEnabled(False)
    menu.exec(button.mapToGlobal(QPoint(0, button.height())))


def _make_triangle_button(controller, row, paths_getter, tooltip: str) -> QToolButton:
    button = QToolButton(row)
    button.setText("▾")
    button.setAutoRaise(True)
    button.setFixedWidth(22)
    button.setToolTip(tooltip)
    button.clicked.connect(
        lambda _checked=False: _show_tab_row_menu(controller, button, paths_getter())
    )
    layout = row.layout()
    if layout is not None:
        layout.addWidget(button)
    return button


def _pinned_controller_init(controller: PinnedTabController, *args, **kwargs) -> None:
    _ORIGINAL_PINNED_INIT(controller, *args, **kwargs)
    controller._nd_pin_menu_button = _make_triangle_button(
        controller,
        controller._pin_row,
        lambda: controller._pin_bar_paths,
        "Show all pinned tabs",
    )
    controller._nd_open_menu_button = _make_triangle_button(
        controller,
        controller._open_row,
        lambda: controller._open_bar_paths,
        "Show all open tabs",
    )


def _recent_begin(switcher: RecentFileSwitcher, paths, direction: int) -> None:
    _ORIGINAL_RECENT_BEGIN(switcher, paths, direction)
    for index, path in enumerate(switcher._paths):
        item = switcher._list.item(index)
        if item is None:
            continue
        candidate = Path(path)
        item.setText(candidate.name)
        item.setData(_ROLE_FILE_NAME, candidate.name)
        item.setData(_ROLE_PATH_CONTEXT, _path_context(candidate))


def _recent_init(switcher: RecentFileSwitcher, *args, **kwargs) -> None:
    _ORIGINAL_RECENT_INIT(switcher, *args, **kwargs)
    switcher._nd_path_delegate = _RecentPathDelegate(switcher._list)
    switcher._list.setItemDelegate(switcher._nd_path_delegate)
    def commit_clicked(_item) -> None:
        parent = switcher.parentWidget()
        commit = getattr(parent, "_commit_recent_file_switcher", None)
        if callable(commit):
            commit()
    switcher._list.itemClicked.connect(commit_clicked)


def _ctrl_tab_event_filter(filter_object: CtrlTabEventFilter, watched, event) -> bool:
    if (
        filter_object.active
        and event.type() == QEvent.Type.KeyPress
        and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
    ):
        filter_object._active = False
        filter_object.commit_requested.emit()
        event.accept()
        return True
    return _ORIGINAL_CTRL_TAB_EVENT_FILTER(filter_object, watched, event)


def _plain_ignore_from_file(cls, path):
    if path is not None and Path(path).name == ".mindmirrorsearchignore":
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError:
            return cls()
        return cls(
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        )
    return _ORIGINAL_IGNORE_FROM_FILE(path)


def _index_thread_init(thread: FileSearchIndexThread, *args, **kwargs) -> None:
    _ORIGINAL_INDEX_THREAD_INIT(thread, *args, **kwargs)
    if _PROJECT_IGNORE_FILE.is_file():
        thread._ignore_file_path = _PROJECT_IGNORE_FILE.resolve()


def _file_system_init(panel: FileSystemPanel, *args, **kwargs) -> None:
    _ORIGINAL_FILE_SYSTEM_INIT(panel, *args, **kwargs)
    panel._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    panel._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)


def _selected_navigator_paths(panel: FileSystemPanel) -> list[Path]:
    selection_model = panel._tree.selectionModel()
    if selection_model is None:
        return []
    candidates: list[Path] = []
    seen: set[str] = set()
    for index in selection_model.selectedRows(0):
        raw_path = panel._path_for_view_index(index)
        if not raw_path:
            continue
        try:
            candidate = Path(raw_path).expanduser().resolve()
        except OSError:
            continue
        if candidate == panel._root_path or not candidate.exists():
            continue
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)
    candidates.sort(key=lambda value: (len(value.parts), str(value)))
    roots: list[Path] = []
    for candidate in candidates:
        if any(_is_path_inside(candidate, parent) for parent in roots):
            continue
        roots.append(candidate)
    return roots


def _is_path_inside(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def _drag_source_path(panel: FileSystemPanel):
    paths = _selected_navigator_paths(panel)
    return paths[0] if paths else None


def _multi_move_by_drop(panel: FileSystemPanel, sources: list[Path], destination: Path) -> bool:
    try:
        destination = destination.expanduser().resolve()
    except OSError:
        return False
    if not destination.is_dir():
        return False
    movable: list[Path] = []
    for source in sources:
        if source.parent == destination:
            continue
        if source.is_dir() and panel._is_same_or_child(destination, source):
            QMessageBox.warning(
                panel,
                "Move",
                f"Cannot move {source.name} into itself or one of its children.",
            )
            return False
        target = destination / source.name
        if target.exists():
            QMessageBox.warning(
                panel,
                "Move",
                f"{target.name} already exists in {destination}.",
            )
            return False
        movable.append(source)
    if not movable:
        return False
    moved_any = False
    for source in movable:
        if panel._move_path_by_drop(source, destination):
            moved_any = True
    return moved_any


def _file_system_event_filter(panel: FileSystemPanel, watched, event) -> bool:
    if watched is panel._tree.viewport():
        if event.type() in {QEvent.Type.DragEnter, QEvent.Type.DragMove}:
            if _selected_navigator_paths(panel):
                event.acceptProposedAction()
                return True
        if event.type() == QEvent.Type.Drop:
            sources = _selected_navigator_paths(panel)
            if not sources:
                return False
            target_index = panel._tree.indexAt(event.position().toPoint())
            target = (
                Path(panel._path_for_view_index(target_index))
                if target_index.isValid()
                else panel._root_path
            )
            destination = target if target.is_dir() else target.parent
            if _multi_move_by_drop(panel, sources, destination):
                event.acceptProposedAction()
            else:
                event.ignore()
            return True
    return _ORIGINAL_FILE_SYSTEM_EVENT_FILTER(panel, watched, event)


def _delete_selected_paths(panel: FileSystemPanel) -> bool:
    paths = _selected_navigator_paths(panel)
    if not paths:
        return False
    if len(paths) == 1:
        return _ORIGINAL_DELETE_SELECTED_PATH(panel)
    names = [path.name for path in paths]
    preview = "\n".join(f"• {name}" for name in names[:12])
    if len(names) > 12:
        preview += f"\n• … and {len(names) - 12} more"
    decision = QMessageBox.question(
        panel,
        "Delete selected items",
        f"Delete {len(paths)} selected items permanently?\n\n{preview}",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if decision != QMessageBox.StandardButton.Yes:
        return False
    deleted_any = False
    errors: list[str] = []
    for path in paths:
        resolved = path.resolve()
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        deleted_any = True
        panel._expanded_paths = {
            value
            for value in panel._expanded_paths
            if not panel._is_same_or_child(Path(value), resolved)
        }
        panel.path_deleted.emit(str(resolved))
    if deleted_any:
        panel._proxy_model.invalidateFilter()
        panel.state_changed.emit()
    if errors:
        QMessageBox.critical(panel, "Delete", "\n\n".join(errors))
    return deleted_any


def _sync_readme_capabilities() -> None:
    readme = _PROJECT_ROOT / "README.md"
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError:
        return
    changed = False
    nav_anchor = "- File/folder creation, rename, delete, clipboard-image paste, path copying, and file-manager reveal are supported."
    nav_bullet = "- Navigator supports extended multi-selection with Ctrl/Shift; selected files/folders can be deleted together with one confirmation or dragged together to a destination folder."
    if nav_bullet not in text and nav_anchor in text:
        text = text.replace(nav_anchor, nav_anchor + "\n" + nav_bullet, 1)
        changed = True
    tab_anchor = "- `Ctrl+Tab` switches recent tabs."
    tab_bullet = "- `Ctrl+Tab` and the Pinned/Open row dropdowns show the filename first, followed by smaller gray compact path context from the first folder under `repo` to the file's direct parent."
    if tab_bullet not in text and tab_anchor in text:
        text = text.replace(tab_anchor, tab_anchor + "\n" + tab_bullet, 1)
        changed = True
    if changed:
        try:
            readme.write_text(text, encoding="utf-8")
        except OSError:
            pass


_ORIGINAL_EDITOR_INIT = LatexEditor.__init__
_ORIGINAL_SOURCE_CURSOR_CHANGED = LatexEditor._on_source_cursor_changed
_ORIGINAL_VISUAL_CURSOR_CHANGED = LatexEditor._on_visual_cursor_changed
_ORIGINAL_SET_EDIT_MODE = LatexEditor.set_edit_mode
_ORIGINAL_ACTIVE_PREVIEW_TEXT = LatexEditor.active_preview_highlight_text
_ORIGINAL_SET_SELECTION_FROM_PREVIEW = _core._set_editor_selection_from_preview
_ORIGINAL_PINNED_INIT = PinnedTabController.__init__
_ORIGINAL_RECENT_INIT = RecentFileSwitcher.__init__
_ORIGINAL_RECENT_BEGIN = RecentFileSwitcher.begin
_ORIGINAL_CTRL_TAB_EVENT_FILTER = CtrlTabEventFilter.eventFilter
_ORIGINAL_IGNORE_FROM_FILE = SearchIgnoreMatcher.from_file
_ORIGINAL_INDEX_THREAD_INIT = FileSearchIndexThread.__init__
_ORIGINAL_FILE_SYSTEM_INIT = FileSystemPanel.__init__
_ORIGINAL_FILE_SYSTEM_EVENT_FILTER = FileSystemPanel.eventFilter
_ORIGINAL_DELETE_SELECTED_PATH = FileSystemPanel._delete_selected_path

if not getattr(LatexEditor, "_nd_three_way_selection_v2", False):
    LatexEditor._nd_three_way_selection_v2 = True
    LatexEditor.__init__ = _editor_init
    LatexEditor._on_source_cursor_changed = _source_cursor_changed
    LatexEditor._on_visual_cursor_changed = _visual_cursor_changed
    LatexEditor.set_edit_mode = _set_edit_mode
    LatexEditor.active_preview_highlight_text = _selection_preview_text
    _core._pdf_selection_item = _qt_pdf_selection_item
    _core._read_pdf_selection = _read_pdf_selection
    _core._set_editor_selection_from_preview = _set_editor_selection_from_preview

if not getattr(PinnedTabController, "_nd_row_menu_v2", False):
    PinnedTabController._nd_row_menu_v2 = True
    PinnedTabController.__init__ = _pinned_controller_init

if not getattr(RecentFileSwitcher, "_nd_path_labels_v2", False):
    RecentFileSwitcher._nd_path_labels_v2 = True
    RecentFileSwitcher.__init__ = _recent_init
    RecentFileSwitcher.begin = _recent_begin

if not getattr(CtrlTabEventFilter, "_nd_enter_commit_v1", False):
    CtrlTabEventFilter._nd_enter_commit_v1 = True
    CtrlTabEventFilter.eventFilter = _ctrl_tab_event_filter

if not getattr(FileSearchIndexThread, "_nd_root_ignore_v1", False):
    FileSearchIndexThread._nd_root_ignore_v1 = True
    FileSearchIndexThread.__init__ = _index_thread_init
    SearchIgnoreMatcher.from_file = classmethod(_plain_ignore_from_file)

if not getattr(FileSystemPanel, "_nd_multi_selection_v1", False):
    FileSystemPanel._nd_multi_selection_v1 = True
    FileSystemPanel.__init__ = _file_system_init
    FileSystemPanel.eventFilter = _file_system_event_filter
    FileSystemPanel._drag_source_path = _drag_source_path
    FileSystemPanel._delete_selected_path = _delete_selected_paths

_sync_readme_capabilities()
