"""Shared QTextFormat properties used by persistent editor decorations."""

from PySide6.QtGui import QTextFormat


class EditorDecorationProperties:
    """Reserve stable properties so independent decoration layers can coexist."""

    PERSISTENT = int(QTextFormat.Property.UserProperty) + 4300
    SPELL_CHECK = int(QTextFormat.Property.UserProperty) + 4500
