"""Theme dark cho Muse Video Studio — 1 chỗ duy nhất định nghĩa stylesheet.

Mọi màu sắc lấy từ docs/design-tokens.md. Không mã màu lẻ tẻ ở file khác.
Áp dụng 1 lần trong main(): apply_theme(app)
"""
from PySide6.QtWidgets import QApplication

# -- Design tokens (đồng bộ với docs/design-tokens.md) --
BG_APP = "#0A0D16"
BG_SIDEBAR = "#0D1120"
BG_PANEL = "#12172A"
BG_PANEL_2 = "#161C33"
BG_HOVER = "#1B2340"
BORDER = "#232B4D"
ACCENT = "#5B5BD6"
ACCENT_2 = "#7C6CF5"
TEXT = "#F1F3FA"
TEXT_DIM = "#9AA3C0"
TEXT_FAINT = "#5D6685"
GREEN = "#34D399"
BLUE = "#60A5FA"
AMBER = "#FBBF24"
PINK = "#F472B6"
RED = "#F87171"

QSS = f"""
/* ================= nền chung ================= */
QMainWindow, QDialog {{
    background: {BG_APP};
}}
QWidget {{
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QToolTip {{
    background: {BG_PANEL_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
}}

/* ================= sidebar ================= */
QWidget#sidebar {{
    background: {BG_SIDEBAR};
}}
QLabel#logo_text {{
    font-size: 14px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#version_text {{
    font-size: 11px;
    color: {TEXT_FAINT};
}}
QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 12px;
    text-align: left;
    font-size: 13px;
    color: {TEXT_DIM};
}}
QPushButton[nav="true"]:hover {{
    background: {BG_HOVER};
    color: {TEXT};
}}
QPushButton[nav="true"][active="true"] {{
    background: {BG_HOVER};
    color: {TEXT};
    font-weight: 600;
}}

/* ================= card / panel ================= */
QFrame[card="true"] {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame[card2="true"] {{
    background: {BG_PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

/* ================= chữ ================= */
QLabel[title="true"] {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel[subtitle="true"] {{
    font-size: 12px;
    color: {TEXT_DIM};
}}
QLabel[section="true"] {{
    font-size: 15px;
    font-weight: 600;
}}
QLabel[dim="true"] {{
    color: {TEXT_DIM};
}}
QLabel[faint="true"] {{
    color: {TEXT_FAINT};
    font-size: 12px;
}}
QLabel[stat="pink"] {{ font-size: 22px; font-weight: 700; color: {PINK}; }}
QLabel[stat="blue"] {{ font-size: 22px; font-weight: 700; color: {BLUE}; }}
QLabel[stat="amber"] {{ font-size: 22px; font-weight: 700; color: {AMBER}; }}
QLabel[stat="green"] {{ font-size: 22px; font-weight: 700; color: {GREEN}; }}
QLabel[statlabel="true"] {{ font-size: 12px; color: {TEXT_DIM}; }}

/* ================= chip trạng thái ================= */
QLabel[chip="green"] {{
    color: {GREEN}; background: rgba(52, 211, 153, 36);
    border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
QLabel[chip="blue"] {{
    color: {BLUE}; background: rgba(96, 165, 250, 36);
    border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
QLabel[chip="amber"] {{
    color: {AMBER}; background: rgba(251, 191, 36, 36);
    border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
QLabel[chip="red"] {{
    color: {RED}; background: rgba(248, 113, 113, 36);
    border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600;
}}
QLabel[chip="gray"] {{
    color: {TEXT_DIM}; background: {BG_HOVER};
    border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600;
}}

/* ================= nút ================= */
QPushButton {{
    background: {BG_PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 16px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    background: {BG_PANEL};
}}
QPushButton:checked {{
    background: {BG_HOVER};
    border-color: {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton[primary="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_2});
    border: none;
    color: white;
    font-weight: 600;
    padding: 10px 18px;
}}
QPushButton[primary="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_2}, stop:1 {ACCENT});
}}

/* ================= tab ================= */
QTabWidget::pane {{
    border: none;
    background: {BG_APP};
}}
QTabWidget QStackedWidget {{
    background: {BG_APP};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 8px 16px;
    border-radius: 8px;
    margin-right: 4px;
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabBar::tab:selected {{
    background: {BG_HOVER};
    color: {TEXT};
    font-weight: 600;
}}

/* ================= input ================= */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit {{
    background: {BG_PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {BG_PANEL_2};
    border: 1px solid {BORDER};
    selection-background-color: {BG_HOVER};
    color: {TEXT};
}}

/* ================= checkbox / toggle ================= */
QCheckBox {{
    spacing: 8px;
    color: {TEXT};
}}
QCheckBox::indicator {{
    width: 38px;
    height: 22px;
    border-radius: 11px;
    background: {BORDER};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
}}

/* ================= progress ================= */
QProgressBar {{
    background: {BG_PANEL_2};
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: {TEXT_DIM};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_2});
    border-radius: 6px;
}}

/* ================= list ================= */
QListWidget {{
    background: {BG_APP};
    border: none;
    color: {TEXT};
    outline: none;
}}
QListWidget::item {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 6px;
    color: {TEXT};
}}
QListWidget::item:selected {{
    background: {BG_HOVER};
    border-color: {ACCENT};
    color: white;
}}
QListWidget::item:hover {{
    border-color: {ACCENT};
}}

/* ================= bảng ================= */
QTableView {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    alternate-background-color: {BG_PANEL_2};
    gridline-color: {BORDER};
    selection-background-color: {BG_HOVER};
}}
QHeaderView::section {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    padding: 8px;
    font-weight: 600;
}}

/* ================= scrollbar ================= */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ================= menu / dialog ================= */
QMenu {{
    background: {BG_PANEL_2};
    border: 1px solid {BORDER};
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {BG_HOVER};
}}
QMessageBox {{
    background: {BG_PANEL};
}}
QSplitter::handle {{
    background: {BORDER};
}}

/* ================= lịch ================= */
QCalendarWidget {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QCalendarWidget QWidget {{
    alternate-background-color: {BG_PANEL};
}}
QCalendarWidget QToolButton {{
    color: {TEXT};
    background: transparent;
    border: none;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {BG_PANEL};
}}
QCalendarWidget QAbstractItemView:enabled {{
    color: {TEXT};
    background: {BG_PANEL};
    selection-background-color: {ACCENT};
    selection-color: white;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Áp dụng theme dark toàn app."""
    app.setStyleSheet(QSS)
