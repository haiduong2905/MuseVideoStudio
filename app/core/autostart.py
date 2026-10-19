"""Bật/tắt tự khởi động cùng Windows qua registry HKCU\\...\\Run.

Trên Linux/macOS: no-op (trả về False).
"""
import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MuseVideoStudio"


def is_windows() -> bool:
    return os.name == "nt"


def _command() -> str:
    """Lệnh chạy app khi Windows khởi động."""
    if getattr(sys, "frozen", False):
        # Bản PyInstaller: sys.executable chính là file .exe
        return f'"{sys.executable}"'
    # Chạy dev: gọi thẳng file main.py (main.py tự thêm project root vào sys.path)
    main_py = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{main_py}"'


def set_autostart(enable: bool) -> bool:
    """Bật/tắt autostart. Trả về True nếu thành công."""
    if not is_windows():
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY,
                             0, winreg.KEY_SET_VALUE)
        try:
            if enable:
                winreg.SetValueEx(key, VALUE_NAME, 0,
                                  winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    except OSError:
        return False


def is_autostart_enabled() -> bool:
    if not is_windows():
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY,
                             0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False
