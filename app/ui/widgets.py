"""Widget dùng chung — mọi màn hình dựng UI qua các hàm này.

Mục đích: không màn hình nào tự style lẻ tẻ, toàn app giữ đúng design tokens.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)


def card() -> QFrame:
    """Thẻ panel bo góc theo mockup."""
    f = QFrame()
    f.setProperty("card", True)
    return f


def card2() -> QFrame:
    """Thẻ nổi hơn (input area, nested)."""
    f = QFrame()
    f.setProperty("card2", True)
    return f


def title_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("title", True)
    return lbl


def subtitle_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("subtitle", True)
    lbl.setWordWrap(True)
    return lbl


def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("section", True)
    return lbl


def dim_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("dim", True)
    lbl.setWordWrap(True)
    return lbl


def chip(text: str, color: str = "gray") -> QLabel:
    """Chip trạng thái pill. color: green|blue|amber|red|gray."""
    lbl = QLabel(text)
    lbl.setProperty("chip", color)
    return lbl


def primary_button(text: str) -> QPushButton:
    """Nút chính gradient tím-xanh."""
    btn = QPushButton(text)
    btn.setProperty("primary", True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def ghost_button(text: str) -> QPushButton:
    """Nút phụ."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def nav_button(text: str) -> QPushButton:
    """Nút điều hướng sidebar."""
    btn = QPushButton(text)
    btn.setProperty("nav", True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setCheckable(True)
    return btn


def stat_card(label: str, value: str, color: str) -> QFrame:
    """Thẻ thống kê dashboard: label nhỏ trên, số lớn màu dưới."""
    f = card()
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(4)
    l = QLabel(label)
    l.setProperty("statlabel", True)
    v = QLabel(value)
    v.setProperty("stat", color)
    lay.addWidget(l)
    lay.addWidget(v)
    return f


def padded(content_layout, margins: int = 24) -> QWidget:
    """Bọc layout vào widget có padding ngoài."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.addLayout(content_layout)
    return w
