"""Dialog soạn bài viết (chữ + ảnh) để đăng lên Facebook Page.

YouTube/TikTok không hỗ trợ đăng bài viết qua API nên dialog này
chỉ đăng lên Facebook.
"""
import os
from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QTextEdit, QVBoxLayout, QWidget)

from app.core import config, db
from app.ui.datetime_picker import DateTimePicker

MIN_LEAD_MINUTES = 10  # Facebook yêu cầu lịch hẹn tối thiểu 10 phút
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


class PostDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Soạn bài viết (Facebook)")
        self.setMinimumSize(560, 520)
        self.images: list[str] = []

        # -- combo --
        self.combo_box = QComboBox()
        self.combo_box.addItem("— Không dùng combo —", None)
        for c in db.list_combos():
            members = c.get("members") or {}
            if "facebook" in members:
                self.combo_box.addItem(f"📺 {c['name']}", c["id"])

        # -- nội dung --
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Viết nội dung bài đăng… (có thể kèm hashtag)")
        self.text_edit.setMinimumHeight(140)

        # -- ảnh --
        self.strip_inner = QWidget()
        self.strip_lay = QHBoxLayout(self.strip_inner)
        self.strip_lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.strip_inner)
        scroll.setFixedHeight(110)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        img_btn_row = QHBoxLayout()
        add_img_btn = QPushButton("🖼️ Thêm ảnh…")
        add_img_btn.clicked.connect(self._pick_images)
        clear_img_btn = QPushButton("Xóa hết ảnh")
        clear_img_btn.clicked.connect(self._clear_images)
        img_btn_row.addWidget(add_img_btn)
        img_btn_row.addWidget(clear_img_btn)
        img_btn_row.addStretch(1)

        # -- lịch --
        self.dt_edit = DateTimePicker()
        now = QDateTime.currentDateTime()
        self.dt_edit.setDateTime(now.addSecs(3600))
        self.dt_edit.setMinimumDateTime(
            now.addSecs(MIN_LEAD_MINUTES * 60))

        form = QFormLayout()
        form.addRow("Combo kênh:", self.combo_box)
        form.addRow("Nội dung:", self.text_edit)
        form.addRow("Ảnh:", img_btn_row)
        form.addRow("", scroll)
        form.addRow("Lịch đăng:", self.dt_edit)
        note = QLabel("Chỉ đăng lên <b>Facebook</b> — YouTube và TikTok "
                      "không hỗ trợ đăng bài viết qua API.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(note)
        lay.addWidget(btns)

    # -- ảnh -----------------------------------------------------------------
    def _pick_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh cho bài viết",
            config.get("last_image_dir") or os.path.expanduser("~"),
            "Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)")
        if paths:
            config.save({"last_image_dir": os.path.dirname(paths[0])})
        for p in paths:
            if p not in self.images:
                self.images.append(p)
        self._refresh_strip()

    def _clear_images(self) -> None:
        self.images = []
        self._refresh_strip()

    def _refresh_strip(self) -> None:
        while self.strip_lay.count():
            item = self.strip_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for p in self.images:
            cell = QWidget()
            cell_lay = QVBoxLayout(cell)
            cell_lay.setContentsMargins(2, 2, 2, 2)
            thumb = QLabel()
            thumb.setFixedSize(96, 72)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pm = QPixmap(p)
            if not pm.isNull():
                thumb.setPixmap(pm.scaled(
                    96, 72, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                thumb.setText("?")
            rm = QPushButton("✕")
            rm.setFixedSize(96, 24)
            rm.clicked.connect(
                lambda _=False, path=p: self._remove_image(path))
            cell_lay.addWidget(thumb)
            cell_lay.addWidget(rm)
            self.strip_lay.addWidget(cell)
        self.strip_lay.addStretch(1)

    def _remove_image(self, path: str) -> None:
        if path in self.images:
            self.images.remove(path)
        self._refresh_strip()

    # -- lưu ------------------------------------------------------------------
    def _on_save(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text and not self.images:
            QMessageBox.warning(self, "Bài viết trống",
                                "Hãy nhập nội dung hoặc thêm ít nhất 1 ảnh.")
            return
        scheduled = self.dt_edit.dateTime().toPython()
        if scheduled <= datetime.now() + timedelta(
                minutes=MIN_LEAD_MINUTES):
            QMessageBox.warning(
                self, "Lịch đăng",
                f"Lịch đăng phải sau hiện tại ít nhất {MIN_LEAD_MINUTES} "
                f"phút (quy định của Facebook).")
            return
        # title = dòng đầu (hiển thị trong bảng)
        title = (text.split("\n")[0] if text else
                 f"Bài viết {len(self.images)} ảnh").strip()[:80]
        combo_id = self.combo_box.currentData()
        account_id = None
        if combo_id:
            combo = db.get_combo(combo_id)
            fb = (combo.get("members") or {}).get("facebook") \
                if combo else None
            account_id = fb["id"] if fb else None
        scheduled_at = scheduled.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            qid = db.add_queue(
                "", title, description=text,
                scheduled_at=scheduled_at, content_type="post",
                image_paths=list(self.images), combo_id=combo_id)
            db.set_targets(qid, {"facebook": (True, account_id)})
            db.add_log(qid, "facebook", "info",
                       f"Đã thêm bài viết vào hàng đợi, "
                       f"lịch đăng {scheduled_at}.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi", f"Không lưu được: {exc}")
            return
        self.accept()
