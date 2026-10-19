"""Icon của app: 1 chỗ duy nhất để lấy đường dẫn icon.

Chạy dev: app/assets/icon.png. Chạy exe đóng gói (PyInstaller):
sys._MEIPASS/app/assets/icon.png (khai báo trong spec datas).
"""
import os
import sys


def icon_path() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "app", "assets", "icon.png")
    else:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "assets", "icon.png")
        p = os.path.normpath(p)
    return p if os.path.isfile(p) else ""


def set_window_icon(widget) -> None:
    """Gắn icon cho cửa sổ/dialog nếu tìm thấy file."""
    try:
        from PySide6.QtGui import QIcon
        p = icon_path()
        if p:
            widget.setWindowIcon(QIcon(p))
    except Exception:
        pass
