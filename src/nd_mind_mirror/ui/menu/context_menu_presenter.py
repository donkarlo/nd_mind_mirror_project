"""Apply compact, meaningful icons to application context menus."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle


class ContextMenuPresenter:
    """Decorate right-click menus consistently without changing their behavior."""

    _THEME_ICONS = (
        (("copy",), "edit-copy"),
        (("cut",), "edit-cut"),
        (("paste",), "edit-paste"),
        (("delete", "remove"), "edit-delete"),
        (("rename",), "edit-rename"),
        (("new folder", "create folder"), "folder-new"),
        (("new ", "create "), "document-new"),
        (("open in files", "file manager"), "system-file-manager"),
        (("open",), "document-open"),
        (("save",), "document-save"),
        (("search", "find"), "edit-find"),
        (("pin",), "emblem-favorite"),
        (("ipad", "image"), "image-x-generic"),
        (("github", "url", "share"), "document-send"),
        (("undo",), "edit-undo"),
        (("redo",), "edit-redo"),
        (("select all",), "edit-select-all"),
    )

    _FALLBACKS = {
        "edit-copy": QStyle.StandardPixmap.SP_FileIcon,
        "edit-cut": QStyle.StandardPixmap.SP_DialogDiscardButton,
        "edit-paste": QStyle.StandardPixmap.SP_DialogApplyButton,
        "edit-delete": QStyle.StandardPixmap.SP_TrashIcon,
        "edit-rename": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        "folder-new": QStyle.StandardPixmap.SP_DirIcon,
        "document-new": QStyle.StandardPixmap.SP_FileIcon,
        "system-file-manager": QStyle.StandardPixmap.SP_DirOpenIcon,
        "document-open": QStyle.StandardPixmap.SP_DialogOpenButton,
        "document-save": QStyle.StandardPixmap.SP_DialogSaveButton,
        "edit-find": QStyle.StandardPixmap.SP_FileDialogContentsView,
        "emblem-favorite": QStyle.StandardPixmap.SP_DialogYesButton,
        "image-x-generic": QStyle.StandardPixmap.SP_FileIcon,
        "document-send": QStyle.StandardPixmap.SP_ArrowForward,
        "edit-undo": QStyle.StandardPixmap.SP_ArrowBack,
        "edit-redo": QStyle.StandardPixmap.SP_ArrowForward,
        "edit-select-all": QStyle.StandardPixmap.SP_DialogYesButton,
    }

    @classmethod
    def decorate(cls, menu: QMenu) -> None:
        """Assign icons recursively to actions that do not already have one."""
        for action in menu.actions():
            submenu = action.menu()
            cls._set_icon(action)
            if submenu is not None:
                cls.decorate(submenu)

    @classmethod
    def _set_icon(cls, action) -> None:
        if action.isSeparator():
            return
        if not action.icon().isNull():
            action.setIconVisibleInMenu(True)
            return
        text = action.text().replace("&", "").split("\t", 1)[0].strip().lower()
        if not text:
            return
        icon_name = cls._icon_name(text)
        if not icon_name:
            return
        icon = QIcon.fromTheme(icon_name)
        if icon.isNull():
            fallback = cls._FALLBACKS.get(icon_name)
            app = QApplication.instance()
            if fallback is not None and app is not None:
                icon = app.style().standardIcon(fallback)
        if not icon.isNull():
            action.setIcon(icon)
            action.setIconVisibleInMenu(True)

    @classmethod
    def _icon_name(cls, text: str) -> str:
        for keywords, icon_name in cls._THEME_ICONS:
            if any(keyword in text for keyword in keywords):
                return icon_name
        return ""
