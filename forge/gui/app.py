"""CreatorForge desktop GUI: main window.

Left sidebar nav + main content area, iOS-glass styling. Every screen
calls the existing backend modules directly (Python imports).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from forge.config import ForgeConfig
from forge.gui import screens as S
from forge.gui.style import STYLESHEET


def _icon() -> QIcon:
    for cand in (
        Path(__file__).resolve().parent.parent.parent
        / "assets" / "icons" / "icon-256.png",
        Path(__file__).resolve().parent / "static" / "icon.png",
    ):
        if cand.is_file():
            return QIcon(str(cand))
    return QIcon()


class MainWindow(QMainWindow):
    def __init__(self, config: ForgeConfig):
        super().__init__()
        self.setWindowTitle("CreatorForge")
        self.setWindowIcon(_icon())
        self.resize(1180, 760)

        # Translucent background for the glass look; if the platform
        # can't do it, the painted dark backdrop still looks fine.
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        root = QWidget()
        root.setObjectName("GlassRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14)

        backdrop = QFrame()
        backdrop.setObjectName("Backdrop")
        outer.addWidget(backdrop)
        body = QHBoxLayout(backdrop)
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)

        # -- sidebar ------------------------------------------------------
        side = QFrame()
        side.setObjectName("SideBar")
        side.setFixedWidth(190)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 12, 8, 12)
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        for label, _ in S.SCREENS:
            QListWidgetItem(label, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._switch)
        side_layout.addWidget(self.nav)
        body.addWidget(side)

        # -- content ------------------------------------------------------
        self.stack = QStackedWidget()
        self._screens = []
        for _, cls in S.SCREENS:
            try:
                screen = cls(config)
            except Exception as e:  # noqa: BLE001 - never break the shell
                from PySide6.QtWidgets import QLabel
                screen = QLabel(f"Couldn't load this screen:\n{e}")
                screen.setWordWrap(True)
            self._screens.append(screen)
            self.stack.addWidget(screen)
        body.addWidget(self.stack, 1)

    def _switch(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        screen = self._screens[row]
        refresh = getattr(screen, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass  # screens handle their own errors; stay robust


def run(config: ForgeConfig) -> int:
    """Start the GUI event loop. Returns the exit code."""
    app = QApplication([])
    app.setStyleSheet(STYLESHEET)
    win = MainWindow(config)
    win.show()
    return app.exec()
