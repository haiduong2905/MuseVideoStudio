"""Entry point Muse Video Studio.

Chạy dev:  python -m app.main   (từ thư mục project)

v1.0.2: tự chẩn đoán khi crash lúc khởi động.
Mọi mốc khởi động + traceback đều được ghi vào crash.log
(%APPDATA%/MuseVideoStudio/crash.log trên Windows) và hiện hộp thoại,
nên không cần chạy từ cmd mới thấy lỗi.
"""
import os
import sys
import traceback
from datetime import datetime

# Đảm bảo project root nằm trong sys.path (cho cả chạy dev và autostart)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _crash_log_path() -> str:
    """Đường dẫn file log chẩn đoán — luôn ghi được, kể cả khi app đóng gói."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "MuseVideoStudio")
    else:
        d = os.path.join(os.path.expanduser("~"), ".muse-video-studio")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "crash.log")


def _note(msg: str) -> None:
    """Ghi mốc khởi động vào crash.log (append). Không bao giờ làm crash thêm."""
    try:
        with open(_crash_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


def _report_crash(where: str, exc: BaseException) -> None:
    """Ghi traceback đầy đủ vào crash.log + hiện hộp thoại để user gửi log."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _note(f"CRASH tại {where}:\n{tb}")
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Muse Video Studio — lỗi khởi động",
            "App gặp lỗi khi khởi động:\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            "Chi tiết đầy đủ đã được ghi vào file:\n"
            f"{_crash_log_path()}\n\n"
            "Bạn hãy gửi file này cho trợ lý để được sửa lỗi.",
        )
        del app
    except Exception:
        pass


def _install_excepthook() -> None:
    """Mọi exception không bắt trong UI đều được ghi vào crash.log.

    App chạy console=False nên không còn cửa sổ cmd để hiện lỗi —
    hook này đảm bảo lỗi không bao giờ 'chết im'.
    """
    old_hook = sys.excepthook

    def _hook(exc_type, exc, tb):
        # Thoát bình thường (sys.exit(0) khi bấm Thoát hẳn) không phải crash
        if exc_type is SystemExit:
            try:
                old_hook(exc_type, exc, tb)
            except Exception:
                pass
            return
        try:
            _note("EXCEPTION không bắt:\n"
                  + "".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:
            pass
        try:
            old_hook(exc_type, exc, tb)
        except Exception:
            pass

    sys.excepthook = _hook


def main() -> int:
    _note(
        "=== khởi động: "
        f"python={sys.version.split()[0]} "
        f"frozen={getattr(sys, 'frozen', False)} "
        f"exe={sys.executable}"
    )
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtNetwork import QLocalServer

    _note("đã import PySide6.QtWidgets + QtNetwork OK")

    # Kiểm tra plugin platform của Qt (nghi phạm số 1 khi app tắt ngay lúc mở).
    try:
        import PySide6

        plugindir = os.path.join(
            os.path.dirname(PySide6.__file__), "plugins", "platforms"
        )
        exists = os.path.isdir(plugindir)
        _note(f"Qt platforms dir: {plugindir} | tồn tại={exists}")
        if exists:
            _note("file plugin: " + ", ".join(sorted(os.listdir(plugindir))))
    except Exception as e:  # noqa: BLE001
        _note(f"không kiểm tra được plugin Qt: {e}")

    from app.core import db
    from app.core.scheduler import SchedulerThread
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme

    _note("đã import app modules OK")

    _install_excepthook()
    _note("đã cài excepthook OK")

    app = QApplication(sys.argv)
    app.setApplicationName("MuseVideoStudio")
    app.setOrganizationName("MuseVideoStudio")
    from app.ui.app_icon import icon_path
    from PySide6.QtGui import QIcon
    _ip = icon_path()
    if _ip:
        app.setWindowIcon(QIcon(_ip))  # icon taskbar + mọi cửa sổ
        _note("đã gắn icon app OK")
    apply_theme(app)
    _note("đã apply theme OK")
    _note("đã tạo QApplication OK")

    # Single-instance: app thứ 2 mở lên sẽ thoát ngay
    _server = QLocalServer()
    if not _server.listen("MuseVideoStudio"):
        _note("single-instance: đã có app đang chạy -> thoát")
        QMessageBox.warning(None, "Muse Video Studio", "Ứng dụng đang chạy rồi.")
        return 1
    _note("single-instance OK")

    db.init_db()
    _note("db.init_db OK")

    scheduler = SchedulerThread()
    window = MainWindow(scheduler)
    window.show()
    scheduler.start()
    _note("cửa sổ chính đã hiện, vào vòng lặp sự kiện")

    code = app.exec()
    scheduler.stop()
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException as e:  # noqa: BLE001 - bắt mọi thứ để chẩn đoán
        _report_crash("main", e)
        sys.exit(1)
