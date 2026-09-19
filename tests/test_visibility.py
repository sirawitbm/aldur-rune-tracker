import unittest

from src.visibility import WindowVisibilityController


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


if __name__ == "__main__":
    unittest.main()