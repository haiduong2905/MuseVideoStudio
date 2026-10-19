"""Cửa sổ chính: sidebar 7 màn hình + khay hệ thống.

Giữ nguyên hành vi quan trọng của SocialUploader:
- Đóng cửa sổ -> hỏi thu nhỏ xuống khay / thoát hẳn (scheduler vẫn chạy nền).
- scheduler báo targets_changed -> refresh màn hình hiện tại.
- scheduler nhắc đăng tay TikTok -> popup + snooze 15'.
"""
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QMessageBox,
                               QStackedWidget, QStyle, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from app.core import config, db
from app.platforms import PLATFORM_LABELS
from app.ui.accounts_view import AccountsView
from app.ui.app_icon import icon_path, set_window_icon
from app.ui.brief_composer import BriefComposerView
from app.ui.dashboard import DashboardView
from app.ui.help_dialog import HelpDialog
from app.ui.library import LibraryView
from app.ui.projects import ProjectsView
from app.ui.scheduler_view import SchedulerView
from app.ui.settings_view import SettingsView
from app.ui.widgets import nav_button

APP_VERSION = "1.0.0"

NAV_ITEMS = [
    ("Dashboard", DashboardView),
    ("Soạn brief", BriefComposerView),
    ("Dự án", ProjectsView),
    ("Thư viện", LibraryView),
    ("Lịch đăng", SchedulerView),
    ("Tài khoản MXH", AccountsView),
    ("Cài đặt", SettingsView),
]


class MainWindow(QMainWindow):
    def __init__(self, scheduler) -> None:
        super().__init__()
        self.scheduler = scheduler
        self.setWindowTitle("Muse Video Studio")
        self.resize(1280, 800)
        set_window_icon(self)

        # -- layout chính: sidebar + content --
        root = QWidget()
        hl = QHBoxLayout(root)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(12, 16, 12, 16)
        sl.setSpacing(4)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo = QLabel()
        ip = icon_path()
        if ip:
            logo.setPixmap(QPixmap(ip).scaled(
                30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        logo_row.addWidget(logo)
        name = QLabel("Muse Video Studio")
        name.setObjectName("logo_text")
        logo_row.addWidget(name, 1)
        sl.addLayout(logo_row)
        sl.addSpacing(16)

        self._nav_btns: list = []
        for label, _cls in NAV_ITEMS:
            b = nav_button(label)
            b.clicked.connect(
                lambda _=False, l=label: self._goto(l))
            sl.addWidget(b)
            self._nav_btns.append(b)
        sl.addStretch(1)

        help_btn = nav_button("❓ Trợ giúp")
        help_btn.clicked.connect(self._on_help)
        sl.addWidget(help_btn)

        ver = QLabel(f"Muse Video Studio v{APP_VERSION}")
        ver.setObjectName("version_text")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(ver)

        hl.addWidget(sidebar)

        self.stack = QStackedWidget()
        self._views: dict[str, QWidget] = {}
        for label, cls in NAV_ITEMS:
            if label == "Dashboard":
                view = cls(nav=self._goto_index)
            else:
                view = cls()
            self._views[label] = view
            self.stack.addWidget(view)
        hl.addWidget(self.stack, 1)

        self.setCentralWidget(root)
        self._goto("Dashboard")

        # scheduler báo queue đổi -> refresh màn hình hiện tại
        self.scheduler.signals.targets_changed.connect(self.refresh)
        # scheduler nhắc đăng tay TikTok
        self.scheduler.signals.tiktok_reminder.connect(
            self._on_tiktok_reminder)

        # -- khay hệ thống --
        self.tray = QSystemTrayIcon(self)
        if ip:
            self.tray.setIcon(QIcon(ip))
        else:
            self.tray.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Muse Video Studio — đang chạy")
        menu = QMenu()
        show_act = menu.addAction("Mở cửa sổ")
        show_act.triggered.connect(self._show_window)
        quit_act = menu.addAction("Thoát hẳn")
        quit_act.triggered.connect(self._quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        # -- mailbox worker (Plan B): tự tải video từ manifest --
        self.mailbox_worker = None
        self._ensure_mailbox_worker()

    def _ensure_mailbox_worker(self) -> None:
        """Tạo + chạy MailboxWorker nếu đã cấu hình manifest URL."""
        try:
            from app.core.mailbox import MailboxWorker
            url = config.get("manifest_url", "").strip()
            if not url or self.mailbox_worker is not None:
                return
            try:
                poll_min = int(config.get("poll_minutes", "15"))
            except ValueError:
                poll_min = 15
            video_dir = config.get("video_dir",
                                   "D:/MuseVideoStudio/Output")
            auto_q = config.get("auto_insert_queue", "1") == "1"
            self.mailbox_worker = MailboxWorker(
                url, video_dir, poll_minutes=poll_min,
                auto_queue=auto_q, parent=self)
            lib_view = self._views.get("Thư viện")
            if lib_view and hasattr(lib_view, "set_worker"):
                lib_view.set_worker(self.mailbox_worker)
            self.mailbox_worker.start()
        except Exception:  # noqa: BLE001 - mailbox không được làm sập app
            self.mailbox_worker = None

    # -- điều hướng -------------------------------------------------------
    def _goto(self, label: str) -> None:
        for b, (l, _c) in zip(self._nav_btns, NAV_ITEMS):
            b.setProperty("active", l == label)
            b.style().unpolish(b)
            b.style().polish(b)
            b.setChecked(l == label)
        self.stack.setCurrentWidget(self._views[label])
        self.refresh()

    def _goto_index(self, index: int, tab: int = 0,
                    brief_id: int | None = None) -> None:
        label = NAV_ITEMS[index][0]
        self._goto(label)
        view = self._views[label]
        if hasattr(view, "set_tab"):
            view.set_tab(tab)
        if brief_id and hasattr(view, "load_brief"):
            view.load_brief(brief_id)

    # -- khay hệ thống ----------------------------------------------------
    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_app(self) -> None:
        self._really_quit = True
        try:
            self.tray.hide()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.mailbox_worker is not None:
                self.mailbox_worker.stop()
                self.mailbox_worker.wait(3000)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.scheduler.stop()
        except Exception:  # noqa: BLE001
            pass
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            self.close()

    def _ask_close_action(self) -> str:
        saved = config.get("close_action", "ask")
        if saved in ("minimize", "quit"):
            return saved
        box = QMessageBox(self)
        box.setWindowTitle("Đóng cửa sổ")
        box.setText("Anh muốn đóng cửa sổ theo cách nào?")
        box.setInformativeText(
            "• <b>Thu nhỏ xuống khay</b>: app vẫn chạy nền để đăng đúng giờ, "
            "tự tải video mới và nhắc lịch TikTok.<br>"
            "• <b>Thoát hẳn</b>: tắt hoàn toàn, lịch đăng và tự tải video "
            "sẽ không chạy.")
        btn_min = box.addButton("Thu nhỏ xuống khay",
                                QMessageBox.ButtonRole.AcceptRole)
        btn_quit = box.addButton("Thoát hẳn",
                                 QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
        remember = QCheckBox("Nhớ lựa chọn này (đổi lại trong Cài đặt)")
        box.setCheckBox(remember)
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_quit:
            action = "quit"
        elif clicked == btn_min:
            action = "minimize"
        else:
            return ""
        if remember.isChecked():
            config.save({"close_action": action})
        return action

    def closeEvent(self, event) -> None:
        if getattr(self, "_really_quit", False):
            event.accept()
            return
        action = self._ask_close_action()
        if action == "quit":
            self._quit_app()
            event.accept()
            return
        if action == "minimize":
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Muse Video Studio",
                "App vẫn đang chạy nền dưới khay hệ thống.\n"
                "Chuột phải vào biểu tượng để mở lại hoặc thoát hẳn.",
                QSystemTrayIcon.MessageIcon.Information, 5000)
            return
        event.ignore()

    # -- dữ liệu ----------------------------------------------------------
    def refresh(self) -> None:
        view = self.stack.currentWidget()
        if hasattr(view, "refresh"):
            try:
                view.refresh()
            except Exception:  # noqa: BLE001 - refresh không được làm sập UI
                pass

    # -- nhắc đăng tay TikTok (giữ nguyên logic SocialUploader) -----------
    def _on_tiktok_reminder(self, payload: dict) -> None:
        target_id = payload.get("target_id")
        title = payload.get("title") or "Video"
        self._show_window()
        self.tray.showMessage(
            "⏰ Đến giờ đăng TikTok!",
            f'"{title}" đã nằm trong hộp thư TikTok.\n'
            f"Mở app TikTok để đăng tay nhé!",
            QSystemTrayIcon.MessageIcon.Warning, 15000)
        box = QMessageBox(self)
        box.setWindowTitle("⏰ Đến giờ đăng TikTok!")
        box.setText(f'Video "{title}" đã nằm trong hộp thư TikTok.\n'
                    f"Anh mở app TikTok đăng tay giúp em nhé!")
        btn_done = box.addButton("✅ Đã đăng",
                                 QMessageBox.ButtonRole.AcceptRole)
        btn_snooze = box.addButton("⏰ Nhắc lại sau 15 phút",
                                   QMessageBox.ButtonRole.ActionRole)
        box.addButton("Để sau", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_done:
            db.update_target(target_id, status="published", reminded=1,
                             next_reminder_at=None, error=None)
            db.add_log(payload.get("queue_id"), "tiktok", "info",
                       f"User xác nhận đã đăng tay TikTok: {title}.")
        elif clicked == btn_snooze:
            snooze_at = (datetime.now() + timedelta(minutes=15)).strftime(
                "%Y-%m-%dT%H:%M:%S")
            db.update_target(target_id, reminded=0,
                             next_reminder_at=snooze_at)
            db.add_log(payload.get("queue_id"), "tiktok", "info",
                       "Hẹn nhắc lại đăng TikTok sau 15 phút.")
        self.refresh()

    def _on_help(self) -> None:
        HelpDialog(self).exec()
