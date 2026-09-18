from pathlib import Path
import ast
import unittest


class EditorPanelViewStateRestoreSourceTest(unittest.TestCase):
    def test_tab_activation_consumes_persisted_state_before_restoring(self) -> None:
        path = Path(__file__).resolve().parents[1] / "src" / "nd_mind_mirror" / "ui" / "panel" / "editor" / "editor_panel.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        panel = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "EditorPanel")
        method = next(node for node in panel.body if isinstance(node, ast.FunctionDef) and node.name == "_restore_persisted_view_state_once")
        text = ast.get_source_segment(source, method) or ""

        self.assertIn("_pending_view_state_restore_paths", text)
        self.assertIn("discard(key)", text)
        self.assertIn("_remembered_view_states.get(key)", text)

    def test_current_changed_does_not_restore_every_switch_directly(self) -> None:
        path = Path(__file__).resolve().parents[1] / "src" / "nd_mind_mirror" / "ui" / "panel" / "editor" / "editor_panel.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        panel = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "EditorPanel")
        method = next(node for node in panel.body if isinstance(node, ast.FunctionDef) and node.name == "_on_current_changed")
        text = ast.get_source_segment(source, method) or ""

        self.assertIn("_restore_persisted_view_state_once", text)
        self.assertNotIn("_remembered_view_states.get", text)


if __name__ == "__main__":
    unittest.main()
