"""Màn 7 — Cài đặt ứng dụng (chung + mailbox Plan B). Lưu vào config.json."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

from app.core import config
from app.ui.widgets import (card, dim_label, ghost_button, primary_button,
                            section_label, subtitle_label, title_label)

DEFAULT_VIDEO_DIR = "D:/MuseVideoStudio/Output"


class SettingsView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(title_label("Cài đặt ứng dụng"))
        root.addWidget(subtitle_label(
            "Cấu hình AI, thư mục, ngôn ngữ, auto post..."))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_general(), "Chung")
        self.tabs.addTab(self._tab_autopost(), "Tự động đăng")
        for name in ["Tạo video", "Nâng cao"]:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.addWidget(dim_label("Sẽ hoàn thiện ở bản tiếp theo."))
            lay.addStretch(1)
            self.tabs.addTab(w, name)
        root.addWidget(self.tabs, 1)

        save_btn = primary_button("💾 Lưu cài đặt")
        save_btn.clicked.connect(self._on_save)
        root.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh()

    # -- tab Chung --
    def _tab_general(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        box = card()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        bl.addWidget(section_label("Thư mục lưu video"))
        row = QHBoxLayout()
        self.video_dir_lbl = QLabel("")
        self.video_dir_lbl.setProperty("dim", True)
        self.video_dir_lbl.setWordWrap(True)
        row.addWidget(self.video_dir_lbl, 1)
        ch = ghost_button("Thay đổi")
        ch.clicked.connect(self._on_change_dir)
        row.addWidget(ch)
        bl.addLayout(row)
        bl.addWidget(section_label("Ngôn ngữ"))
        self.lang = QComboBox()
        self.lang.addItems(["Tiếng Việt", "English"])
        bl.addWidget(self.lang, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(box)

        box2 = card()
        b2 = QVBoxLayout(box2)
        b2.setContentsMargins(16, 16, 16, 16)
        b2.setSpacing(10)
        self.toggles = {}
        for key, text in [
            ("auto_post_after_done", "Tự động đăng video sau khi hoàn thành"),
            ("auto_title_ai", "Tự động tạo tiêu đề bằng AI"),
            ("auto_subtitle_ai", "Tạo phụ đề tự động bằng AI"),
            ("save_debug_log", "Lưu log chi tiết"),
        ]:
            c = QCheckBox(text)
            self.toggles[key] = c
            b2.addWidget(c)
        lay.addWidget(box2)
        lay.addStretch(1)
        return w

    # -- tab Tự động đăng (mailbox) --
    def _tab_autopost(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        box = card()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        bl.addWidget(section_label("Mailbox — nhận video tự động"))
        bl.addWidget(dim_label(
            "Assistant cập nhật manifest tại URL này mỗi khi có video mới; "
            "app tự tải về máy và phân loại theo dự án."))
        bl.addWidget(dim_label("Manifest URL"))
        self.manifest_url = QLineEdit()
        self.manifest_url.setPlaceholderText(
            "https://raw.githubusercontent.com/.../manifest.json")
        bl.addWidget(self.manifest_url)
        row = QHBoxLayout()
        row.addWidget(dim_label("Chu kỳ kiểm tra (phút)"))
        self.poll_minutes = QSpinBox()
        self.poll_minutes.setRange(5, 120)
        self.poll_minutes.setValue(15)
        row.addWidget(self.poll_minutes)
        row.addStretch(1)
        bl.addLayout(row)
        self.auto_insert = QCheckBox(
            "Tự động thêm video mới vào hàng đợi đăng")
        bl.addWidget(self.auto_insert)
        row2 = QHBoxLayout()
        row2.addWidget(dim_label("Đăng sau khi video về (phút)"))
        self.auto_offset = QSpinBox()
        self.auto_offset.setRange(5, 1440)
        self.auto_offset.setValue(60)
        row2.addWidget(self.auto_offset)
        row2.addStretch(1)
        bl.addLayout(row2)
        lay.addWidget(box)
        lay.addStretch(1)
        return w

    # -- load / save --
    def refresh(self) -> None:
        self._video_dir = config.get("video_dir", DEFAULT_VIDEO_DIR)
        self.video_dir_lbl.setText(self._video_dir)
        lang = config.get("language", "Tiếng Việt")
        self.lang.setCurrentText(
            lang if lang in ("Tiếng Việt", "English") else "Tiếng Việt")
        for key, chk in self.toggles.items():
            chk.setChecked(config.get(key, "1") == "1")
        self.manifest_url.setText(config.get("manifest_url", ""))
        try:
            self.poll_minutes.setValue(int(config.get("poll_minutes",
                                                       "15")))
        except ValueError:
            pass
        self.auto_insert.setChecked(
            config.get("auto_insert_queue", "1") == "1")
        try:
            self.auto_offset.setValue(int(config.get("auto_queue_offset_min",
                                                      "60")))
        except ValueError:
            pass

    def _on_change_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục lưu video", self._video_dir)
        if d:
            self._video_dir = d.replace("/", "/")
            self.video_dir_lbl.setText(self._video_dir)

    def _on_save(self) -> None:
        cfg = {
            "video_dir": self._video_dir,
            "language": self.lang.currentText(),
            "manifest_url": self.manifest_url.text().strip(),
            "poll_minutes": str(self.poll_minutes.value()),
            "auto_queue_offset_min": str(self.auto_offset.value()),
            "auto_insert_queue": "1" if self.auto_insert.isChecked()
            else "0",
        }
        for key, chk in self.toggles.items():
            cfg[key] = "1" if chk.isChecked() else "0"
        config.save(cfg)
        # đồng bộ manifest_url vào mailbox state để worker dùng ngay
        try:
            from app.core import db
            db.save_mailbox_state(
                manifest_url=self.manifest_url.text().strip())
        except Exception:
            pass
        QMessageBox.information(
            self, "Đã lưu",
            "Cài đặt đã được lưu.\n"
            "Đổi Manifest URL / chu kỳ poll có hiệu lực sau khi "
            "khởi động lại app.")
