class WindowVisibilityController:
    def __init__(self, widgets_provider):
        self._widgets_provider = widgets_provider
        self._restore_widgets = []
        self.hidden = False

    def toggle(self):
        if self.hidden:
            self.hidden = False
            restore_widgets = self._restore_widgets
            self._restore_widgets = []
            for widget in restore_widgets:
                try:
                    widget.show()
                    widget.raise_()
                except RuntimeError:
                    pass
            return

        self._restore_widgets = []
        for widget in self._widgets_provider():
            try:
                if widget.isVisible():
                    self._restore_widgets.append(widget)
                    widget.hide()
            except RuntimeError:
                pass
        self.hidden = True