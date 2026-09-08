"""Resolve canonical bookmark locations into safe visible QTextDocument positions."""


class SourceBookmarkPositionResolver:
    """Map bookmark locations into the currently materialized Source document."""

    def resolve(self, editor, location: tuple[int, int]) -> int | None:
        """Return a safe visible position, or None when the bookmark is off-window."""
        source_is_windowed = bool(
            getattr(editor, "source_is_windowed", False)
        )

        if source_is_windowed:
            local_resolver = getattr(
                editor,
                "_local_position_for_location",
                None,
            )
            if not callable(local_resolver):
                return None
            value = local_resolver(location)
        else:
            value = editor._source_position_for_location(location)

        if value is None:
            return None

        try:
            position = int(value)
        except (TypeError, ValueError):
            return None

        document = editor.document()
        maximum = max(int(document.characterCount()) - 1, 0)
        if position < 0 or position > maximum:
            return None

        return position
