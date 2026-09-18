from nd_mind_mirror.ui.editor.latex.latex_tab_view_state_mixin import (
    LatexTabViewStateMixin,
)


class _FakeLatexBase:
    def __init__(self):
        self.edit_mode = "visual"
        self.restored_base_state = None
        self.navigation = []

    def view_state(self):
        return {"cursor": 17, "vertical": 90, "horizontal": 4}

    def restore_view_state(self, state):
        self.restored_base_state = dict(state)

    def active_source_location(self):
        return (30, 8)

    def first_visible_source_position(self):
        return (24, 1)

    def set_edit_mode(self, mode):
        self.edit_mode = mode

    def go_to_source_location(self, line, column=1, align_top=True):
        self.navigation.append((line, column, align_top))


class _FakeLatexEditor(LatexTabViewStateMixin, _FakeLatexBase):
    pass


def test_visual_tab_state_records_cursor_and_viewport_source_locations():
    editor = _FakeLatexEditor()

    state = editor.view_state()

    assert state["edit_mode"] == "visual"
    assert state["active_source_line"] == 30
    assert state["active_source_column"] == 8
    assert state["visible_source_line"] == 24
    assert state["visible_source_column"] == 1


def test_visual_tab_state_restores_viewport_before_cursor():
    editor = _FakeLatexEditor()
    state = editor.view_state()
    editor.edit_mode = "source"

    editor.restore_view_state(state)

    assert editor.restored_base_state == state
    assert editor.edit_mode == "visual"
    assert editor.navigation == [
        (24, 1, True),
        (30, 8, False),
    ]
