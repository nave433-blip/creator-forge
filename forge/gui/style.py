"""iOS-glass styling for the CreatorForge desktop GUI.

Glassmorphism via Qt stylesheets: frosted semi-transparent panels,
rounded corners, 1px light borders, soft shadows, teal->violet accent.
The window itself uses WA_TranslucentBackground with a dark rounded
backdrop painted in code (works with or without a compositing blur --
a graceful solid fallback, never a crash).
"""

ACCENT_TEAL = "#2dd4bf"
ACCENT_VIOLET = "#7c5cff"
BG_DARK = "#14121c"
TEXT = "#f5f5f7"
DIM = "#a1a1a6"

STYLESHEET = """
* {
    font-family: "SF Pro Text", "Inter", "Segoe UI", "Ubuntu", "Cantarell", sans-serif;
    font-size: 13px;
    color: #f5f5f7;
}
QWidget#GlassRoot {
    background: transparent;
}
QFrame#Backdrop {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1a1626, stop:0.5 #14121c, stop:1 #101018);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 40);
}
QFrame#GlassCard {
    background: rgba(255, 255, 255, 18);
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 16px;
}
QFrame#SideBar {
    background: rgba(255, 255, 255, 10);
    border: 1px solid rgba(255, 255, 255, 45);
    border-radius: 16px;
}
QListWidget#Nav {
    background: transparent;
    border: none;
    outline: none;
    font-size: 14px;
}
QListWidget#Nav::item {
    padding: 10px 12px;
    border-radius: 12px;
    margin: 2px 6px;
    color: #cfcfd6;
}
QListWidget#Nav::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(45, 212, 191, 90), stop:1 rgba(124, 92, 255, 90));
    border: 1px solid rgba(255, 255, 255, 70);
    color: #ffffff;
    font-weight: 600;
}
QListWidget#Nav::item:hover:!selected {
    background: rgba(255, 255, 255, 20);
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2dd4bf, stop:1 #7c5cff);
    border: 1px solid rgba(255, 255, 255, 70);
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 600;
    color: white;
}
QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #5eead4, stop:1 #9d7bff); }
QPushButton:pressed { background: #6a5acd; }
QPushButton:disabled { background: rgba(255,255,255,25); color: #8e8e93; }
QPushButton#Ghost {
    background: rgba(255, 255, 255, 22);
}
QPushButton#Danger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff6b6b, stop:1 #c81e5b);
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: rgba(255, 255, 255, 16);
    border: 1px solid rgba(255, 255, 255, 55);
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: #7c5cff;
}
QComboBox QAbstractItemView {
    background: #1e1b2e;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 8px;
    selection-background-color: #7c5cff;
}
QTableWidget {
    background: rgba(255, 255, 255, 12);
    border: 1px solid rgba(255, 255, 255, 45);
    border-radius: 12px;
    gridline-color: rgba(255, 255, 255, 25);
    alternate-background-color: rgba(255, 255, 255, 8);
    outline: none;
}
QTableWidget::item { padding: 4px; }
QHeaderView::section {
    background: rgba(255, 255, 255, 20);
    border: none;
    padding: 8px;
    font-weight: 600;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: transparent;
    width: 10px; height: 10px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 60);
    border-radius: 5px;
    min-height: 30px; min-width: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0; width: 0;
}
QLabel#Title { font-size: 22px; font-weight: 700; }
QLabel#Section { font-size: 15px; font-weight: 600; color: #d9d9e0; }
QLabel#Dim { color: #a1a1a6; }
QTabWidget::pane { border: 1px solid rgba(255,255,255,45); border-radius: 12px; }
QTabBar::tab {
    background: rgba(255,255,255,14);
    border: 1px solid rgba(255,255,255,40);
    border-radius: 10px;
    padding: 8px 16px;
    margin-right: 6px;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(45,212,191,80), stop:1 rgba(124,92,255,80));
    font-weight: 600;
}
"""
