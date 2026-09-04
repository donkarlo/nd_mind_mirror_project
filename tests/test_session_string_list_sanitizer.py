from nd_mind_mirror.core.settings.storage.session_string_list_sanitizer import (
    SessionStringListSanitizer,
)


class FakeSettings:
    def __init__(self, values=None) -> None:
        self.values = dict(values or {})

    def value(self, key: str, default=None):
        return self.values.get(key, default)

    def setValue(self, key: str, value) -> None:
        self.values[key] = value


def test_none_from_qsettings_invalid_value_becomes_safe_empty_string() -> None:
    settings = FakeSettings({"filesystem/expanded_paths": None})
    sanitizer = SessionStringListSanitizer(settings)

    sanitizer.normalize("filesystem/expanded_paths")

    assert settings.values["filesystem/expanded_paths"] == ""


def test_empty_python_list_becomes_safe_empty_string() -> None:
    settings = FakeSettings({"filesystem/expanded_paths": []})
    sanitizer = SessionStringListSanitizer(settings)

    sanitizer.normalize("filesystem/expanded_paths")

    assert settings.values["filesystem/expanded_paths"] == ""


def test_nonempty_string_list_is_preserved() -> None:
    paths = ["/repo/a", "/repo/b"]
    settings = FakeSettings({"filesystem/expanded_paths": list(paths)})
    sanitizer = SessionStringListSanitizer(settings)

    sanitizer.normalize("filesystem/expanded_paths")

    assert settings.values["filesystem/expanded_paths"] == paths
