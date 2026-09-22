"""Check animation scheduling and original button invocation without a display."""
import ast
import colorsys
from pathlib import Path
import unittest
from unittest.mock import Mock


class RainbowTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "rainbow_hint.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        self.canvas = Mock()
        self.canvas.winfo_width.return_value = 200
        self.canvas.winfo_height.return_value = 40
        self.canvas.after.return_value = "animation-job"
        namespace = {"tk": Mock(Canvas=Mock(return_value=self.canvas)), "colorsys": colorsys}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        self.hint = namespace["RainbowHint"]()
        self.button = Mock()
        self.button.instate.return_value = False
        self.button.cget.return_value = "开始记录(Ctrl-Q)"

    def test_gradient_moves_without_duplicate_timer(self):
        self.hint.show(self.button)
        first_color = self.canvas.create_rectangle.call_args_list[0].kwargs["fill"]
        self.assertEqual(self.canvas.create_rectangle.call_count, 48)
        self.hint.show(self.button)
        self.assertEqual(self.canvas.after.call_count, 1)
        self.hint._animate()
        next_color = self.canvas.create_rectangle.call_args_list[48].kwargs["fill"]
        self.assertNotEqual(first_color, next_color)

    def test_clear_cancels_timer_and_removes_overlay(self):
        self.hint.show(self.button)
        self.hint.clear()
        self.canvas.after_cancel.assert_called_once_with("animation-job")
        self.canvas.destroy.assert_called_once()
        self.assertIsNone(self.hint.button)
        self.hint.clear()
        self.canvas.destroy.assert_called_once()

    def test_mouse_uses_original_command_and_disabled_button_does_not_invoke(self):
        self.hint.show(self.button)
        self.hint._click(Mock())
        self.button.invoke.assert_called_once()
        self.button.instate.return_value = True
        self.hint._click(Mock())
        self.button.invoke.assert_called_once()
        self.hint._animate()
        self.assertIsNone(self.hint.canvas)


if __name__ == "__main__":
    unittest.main()
