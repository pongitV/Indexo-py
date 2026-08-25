from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QFrame, QTreeWidget, QTableWidget, QAbstractItemView

class SmoothScrollArea(QScrollArea):
    """Universal smooth scroll area with linear pixel precision and synchronized viewport."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        if self.verticalScrollBar():
            self.verticalScrollBar().setSingleStep(30)
        if self.horizontalScrollBar():
            self.horizontalScrollBar().setSingleStep(30)

    def showEvent(self, event):
        super().showEvent(event)
        if self.verticalScrollBar():
            self.verticalScrollBar().setValue(0)


class SmoothTreeWidget(QTreeWidget):
    """Universal tree widget with per-pixel smooth scrolling."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        if self.verticalScrollBar():
            self.verticalScrollBar().setSingleStep(25)
        if self.horizontalScrollBar():
            self.horizontalScrollBar().setSingleStep(25)


class SmoothTableWidget(QTableWidget):
    """Universal table widget with per-pixel smooth scrolling."""
    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__(rows, cols, parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().setDefaultSectionSize(46)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        if self.verticalScrollBar():
            self.verticalScrollBar().setSingleStep(25)
        if self.horizontalScrollBar():
            self.horizontalScrollBar().setSingleStep(25)
