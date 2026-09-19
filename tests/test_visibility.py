import unittest

from src.visibility import WindowVisibilityController, toggle_widget


class _FakeWidget:
    def __init__(self, visible):
        self.visible = visible
        self.raise_count = 0

    def isVisible(self):
        return self.visible

    def hide(self):
        self.visible = False

    def show(self):
        self.visible = True

    def raise_(self):
        self.raise_count += 1


class WindowVisibilityControllerTests(unittest.TestCase):
    def test_toggle_restores_only_windows_that_were_visible(self):
        visible = _FakeWidget(True)
        already_hidden = _FakeWidget(False)
        controller = WindowVisibilityController(lambda: [visible, already_hidden])

        controller.toggle()
        self.assertTrue(controller.hidden)
        self.assertFalse(visible.visible)
        self.assertFalse(already_hidden.visible)

        controller.toggle()
        self.assertFalse(controller.hidden)
        self.assertTrue(visible.visible)
        self.assertFalse(already_hidden.visible)
        self.assertEqual(visible.raise_count, 1)

    def test_toggle_widget_hides_then_restores_one_widget(self):
        widget = _FakeWidget(True)

        self.assertFalse(toggle_widget(widget))
        self.assertFalse(widget.visible)
        self.assertTrue(toggle_widget(widget))
        self.assertTrue(widget.visible)
        self.assertEqual(widget.raise_count, 1)

    def test_global_toggle_preserves_panel_only_hidden_state(self):
        panel = _FakeWidget(True)
        overlay = _FakeWidget(True)
        controller = WindowVisibilityController(lambda: [panel, overlay])

        toggle_widget(panel)
        controller.toggle()
        controller.toggle()

        self.assertFalse(panel.visible)
        self.assertTrue(overlay.visible)


if __name__ == "__main__":
    unittest.main()