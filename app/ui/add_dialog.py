"""Dialog thêm/sửa video trong hàng đợi (hỗ trợ kéo-thả file)."""
import os
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTextEdit, QVBoxLayout)

from app.core import config, db
from app.core.md_titles import fill_video, parse_md
from app.core.thumbnails import (describe_rules, discard_persisted,
                                 persist_candidate, prepare_thumbnail)
from app.ui.datetime_picker import DateTimePicker
from app.ui.thumb_candidates import ThumbCandidates

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
MIN_LEAD_MINUTES = 10  # Facebook Reels yêu cầu lịch hẹn tối thiểu 10 phút
QUICK_LEAD_MINUTES = 1  # không tick Facebook: cho hẹn sát giờ để test


class AddDialog(QDialog):
    def __init__(self, parent=None, queue_id: int | None = None) -> None:
        super().__init__(parent)
        self.queue_id = queue_id
        self._thumb_src = ""     # ảnh bìa đã lưu trong DB (đã chuẩn hóa)
        self._thumb_picked = ""  # ảnh user vừa chọn trong lần mở này
        self.setWindowTitle("Sửa video" if queue_id else "Thêm video")
        self.setMinimumWidth(560)
        self.setAcceptDrops(True)

        # -- combo kênh --
        self.combo_box = QComboBox()
        self.combo_box.addItem("— Không dùng combo (chọn tay từng nền tảng) —",
                               None)
        self._combos = db.list_combos()
        for c in self._combos:
            self.combo_box.addItem(f"📺 {c['name']}", c["id"])
        self.combo_box.currentIndexChanged.connect(self._on_combo_changed)

        # -- file --
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Chưa chọn file…")
        pick_btn = QPushButton("Chọn file…")
        pick_btn.clicked.connect(self._pick_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(pick_btn)

        # -- các trường --
        self.title_edit = QLineEdit()
        self.title_edit.setMaxLength(100)
        self.title_edit.setPlaceholderText("Tiêu đề video (tối đa 100 ký tự)")
        md_btn = QPushButton("📄 Từ file md")
        md_btn.setToolTip(
            "Đọc file md tiêu đề/caption và tự điền theo tên file video")
        md_btn.clicked.connect(self._fill_from_md)
        title_row = QHBoxLayout()
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(md_btn)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(90)
        self.desc_edit.setPlaceholderText("Mô tả (không bắt buộc)")
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("VD: #beastbytes #animalfacts #wildlife")

        self.dt_edit = DateTimePicker()
        now = QDateTime.currentDateTime()
        self.dt_edit.setDateTime(now.addSecs(3600))          # mặc định +1 giờ

        self.cb_yt = QCheckBox("YouTube")
        self.cb_fb = QCheckBox("Facebook")
        self.cb_tt = QCheckBox("TikTok (vào hộp nháp)")
        # Mặc định luôn tick hết cả 3 nền tảng
        for cb in (self.cb_yt, self.cb_fb, self.cb_tt):
            cb.setChecked(True)
        # Facebook bắt lịch hẹn tối thiểu 10 phút; không có FB thì cho hẹn
        # sát giờ (test vài phút tới) -> cập nhật giới hạn khi tick đổi
        self.cb_fb.toggled.connect(lambda _c: self._update_min_time())
        self._update_min_time()
        plat_row = QHBoxLayout()
        plat_row.addWidget(self.cb_yt)
        plat_row.addWidget(self.cb_fb)
        plat_row.addWidget(self.cb_tt)
        plat_row.addStretch(1)

        # -- ảnh bìa --
        self.thumb_edit = QLineEdit()
        self.thumb_edit.setReadOnly(True)
        self.thumb_edit.setPlaceholderText("Chưa có ảnh bìa (không bắt buộc)")
        thumb_btn = QPushButton("Chọn…")
        thumb_btn.clicked.connect(self._pick_thumb)
        thumb_gen_btn = QPushButton("🎬 Tạo từ video")
        thumb_gen_btn.setToolTip("Tự tách 8 frame từ video để chọn làm ảnh bìa")
        thumb_gen_btn.clicked.connect(self._gen_thumbs)
        thumb_row = QHBoxLayout()
        thumb_row.addWidget(self.thumb_edit, 1)
        thumb_row.addWidget(thumb_btn)
        thumb_row.addWidget(thumb_gen_btn)
        self.thumb_cands = ThumbCandidates()
        self.thumb_cands.picked.connect(self._on_candidate_picked)

        form = QFormLayout()
        form.addRow("Combo kênh:", self.combo_box)
        form.addRow("Video:", file_row)
        form.addRow("Tiêu đề:", title_row)
        form.addRow("Mô tả:", self.desc_edit)
        form.addRow("Hashtag:", self.tags_edit)
        form.addRow("Lịch đăng:", self.dt_edit)
        form.addRow("Ảnh bìa:", thumb_row)
        form.addRow("", self.thumb_cands)
        rules = QLabel(describe_rules())
        rules.setWordWrap(True)
        rules.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", rules)
        form.addRow("Đăng lên:", plat_row)

        hint = QLabel("Mẹo: kéo-thả file video vào cửa sổ này để chọn nhanh.")
        hint.setStyleSheet("color: gray;")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(btns)

        # Nhớ combo lần trước; chỉ có 1 combo thì tự chọn luôn
        self._restore_combo()

    def _restore_combo(self) -> None:
        """Khôi phục combo đã dùng lần trước.

        Chỉ có đúng 1 combo -> tự chọn luôn (khỏi bấm).
        """
        combos = db.list_combos()
        if len(combos) == 1:
            self.combo_box.setCurrentIndex(1)
            return
        try:
            saved = int(config.get("default_combo_id", "") or 0)
        except ValueError:
            saved = 0
        if saved:
            idx = self.combo_box.findData(saved)
            if idx > 0:
                self.combo_box.setCurrentIndex(idx)

        if queue_id:
            self._load(queue_id)

    def _on_combo_changed(self, idx: int) -> None:
        """Chọn combo -> tự tick các nền tảng có trong combo."""
        combo_id = self.combo_box.currentData()
        if not combo_id:
            return
        combo = db.get_combo(combo_id)
        if not combo:
            return
        members = combo["members"]
        self.cb_yt.setChecked("youtube" in members)
        self.cb_fb.setChecked("facebook" in members)
        self.cb_tt.setChecked("tiktok" in members)
        # lưu account_id để lúc save gán đúng tài khoản
        self._combo_accounts = {
            plat: members[plat]["id"] for plat in members}

    def _update_min_time(self) -> None:
        """Giới hạn giờ hẹn tối thiểu theo nền tảng đã tick.

        Có Facebook -> sau hiện tại 10 phút (quy định của Facebook);
        không có Facebook -> sau hiện tại 1 phút (để test nhanh).
        """
        lead = (MIN_LEAD_MINUTES if self.cb_fb.isChecked()
                else QUICK_LEAD_MINUTES)
        self.dt_edit.setMinimumDateTime(
            QDateTime.currentDateTime().addSecs(lead * 60))

    def _current_combo(self) -> tuple[int | None, dict]:
        combo_id = self.combo_box.currentData()
        if not combo_id:
            return None, {}
        accounts = getattr(self, "_combo_accounts", {})
        # refresh từ DB để chắc chắn
        combo = db.get_combo(combo_id)
        if combo:
            accounts = {plat: combo["members"][plat]["id"]
                        for plat in combo["members"]}
        return combo_id, accounts

    # -- kéo-thả ----------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.file_edit.setText(path)

    # -- ảnh bìa --
    def _pick_thumb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh bìa",
            config.get("last_image_dir") or os.path.expanduser("~"),
            "Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)")
        if path:
            config.save({"last_image_dir": os.path.dirname(path)})
            discard_persisted(self._thumb_picked)
            self._thumb_picked = path
            self.thumb_edit.setText(path)

    def _gen_thumbs(self) -> None:
        video = self.file_edit.text().strip()
        if not video or not os.path.isfile(video):
            QMessageBox.warning(self, "Chưa có video",
                                "Hãy chọn file video trước khi tách frame.")
            return
        self.thumb_cands.extract(video)

    def _on_candidate_picked(self, path: str) -> None:
        # Copy ra chỗ bền vững: file tạm sẽ bị xóa khi đóng dialog
        kept = persist_candidate(path)
        self.thumb_cands.keep(path)
        discard_persisted(self._thumb_picked)
        self._thumb_picked = kept
        self.thumb_edit.setText(os.path.basename(kept))

    # -- file --
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video",
            config.get("last_video_dir") or os.path.expanduser("~"),
            "Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)")
        if path:
            config.save({"last_video_dir": os.path.dirname(path)})
            self.file_edit.setText(path)

    def _fill_from_md(self) -> None:
        """Đọc file md tiêu đề/caption, tự điền theo tên file video."""
        video_path = self.file_edit.text().strip()
        if not video_path:
            QMessageBox.information(self, "Chưa chọn video",
                                    "Hãy chọn file video trước.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file md tiêu đề/caption",
            config.get("last_md_dir") or os.path.expanduser("~"),
            "Markdown (*.md)")
        if not path:
            return
        config.save({"last_md_dir": os.path.dirname(path)})
        try:
            entries = parse_md(path)
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.critical(self, "Không đọc được file",
                                 f"Lỗi đọc {os.path.basename(path)}:\n{exc}")
            return
        video = {"file_path": video_path, "__overwrite__": True,
                 "title": "", "description": "", "hashtags": ""}
        if not fill_video(video, entries):
            QMessageBox.warning(
                self, "Không khớp",
                f"Không tìm thấy '{os.path.basename(video_path)}' "
                f"trong file md.\nKiểm tra lại tên file.")
            return
        self.title_edit.setText(video["title"])
        self.desc_edit.setPlainText(video["description"])
        self.tags_edit.setText(video["hashtags"])
        QMessageBox.information(self, "Xong",
                                "Đã điền tiêu đề, mô tả, hashtag từ file md.")

    def _load(self, queue_id: int) -> None:
        item = db.get_queue(queue_id)
        if not item:
            return
        # chọn combo đã lưu (nếu còn tồn tại)
        combo_id = item.get("combo_id")
        if combo_id:
            idx = self.combo_box.findData(combo_id)
            if idx >= 0:
                self.combo_box.setCurrentIndex(idx)
        self.file_edit.setText(item["file_path"])
        self.title_edit.setText(item["title"])
        self.desc_edit.setPlainText(item["description"])
        self.tags_edit.setText(item["hashtags"])
        self._thumb_src = item.get("thumbnail_path") or ""
        if self._thumb_src:
            self.thumb_edit.setText(self._thumb_src)
        try:
            dt = datetime.fromisoformat(item["scheduled_at"])
            self.dt_edit.setDateTime(
                QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                          0))
        except ValueError:
            pass
        # nạp tick nền tảng từ DB
        for it in db.list_queue():
            if it["id"] == queue_id:
                tg = it["targets"]
                self.cb_yt.setChecked(
                    tg.get("youtube", {}).get("enabled", 1) == 1)
                self.cb_fb.setChecked(
                    tg.get("facebook", {}).get("enabled", 1) == 1)
                self.cb_tt.setChecked(
                    tg.get("tiktok", {}).get("enabled", 1) == 1)
                break

    # -- lưu --
    def _warn(self, msg: str) -> None:
        QMessageBox.warning(self, "Thiếu thông tin", msg)

    def _on_save(self) -> None:
        file_path = self.file_edit.text().strip()
        title = self.title_edit.text().strip()
        if not file_path or not os.path.isfile(file_path):
            self._warn("Vui lòng chọn file video tồn tại trên máy.")
            return
        if not file_path.lower().endswith(VIDEO_EXTS):
            self._warn("File không phải video (chấp nhận: "
                       + ", ".join(VIDEO_EXTS) + ").")
            return
        if not title:
            self._warn("Vui lòng nhập tiêu đề video.")
            return
        scheduled = self.dt_edit.dateTime().toPython()
        lead = (MIN_LEAD_MINUTES if self.cb_fb.isChecked()
                else QUICK_LEAD_MINUTES)
        if scheduled <= datetime.now() + timedelta(minutes=lead):
            rule = (f"quy định của Facebook ({MIN_LEAD_MINUTES} phút)"
                    if self.cb_fb.isChecked() else "giờ hiện tại")
            self._warn(f"Lịch đăng phải sau {rule}.")
            return
        platforms = {"youtube": self.cb_yt.isChecked(),
                     "facebook": self.cb_fb.isChecked(),
                     "tiktok": self.cb_tt.isChecked()}
        if not any(platforms.values()):
            self._warn("Vui lòng tick ít nhất 1 nền tảng để đăng.")
            return
        combo_id, combo_accounts = self._current_combo()
        # Nhớ combo đã dùng cho lần mở dialog sau
        config.save({"default_combo_id": str(combo_id or "")})
        # gán account theo combo (nếu tick tay mà không dùng combo,
        # set_targets tự lấy account đầu tiên)
        platforms = {
            plat: (enabled, combo_accounts.get(plat))
            for plat, enabled in platforms.items()
        }

        scheduled_at = scheduled.strftime("%Y-%m-%dT%H:%M:%S")
        # Chuẩn hóa ảnh bìa (nếu user vừa chọn ảnh mới) về đúng quy định
        if self._thumb_picked:
            try:
                thumb = prepare_thumbnail(self._thumb_picked)
            except ValueError as exc:
                self._warn(f"Ảnh bìa không hợp lệ ({exc}). "
                           f"Video sẽ được lưu mà không có ảnh bìa.")
                thumb = ""
        else:
            thumb = self._thumb_src  # giữ ảnh bìa cũ (đã chuẩn hóa)
        try:
            if self.queue_id:
                db.update_queue(
                    self.queue_id, file_path=file_path, title=title,
                    description=self.desc_edit.toPlainText().strip(),
                    hashtags=self.tags_edit.text().strip(),
                    scheduled_at=scheduled_at,
                    thumbnail_path=thumb, combo_id=combo_id)
                db.set_targets(self.queue_id, platforms)
            else:
                qid = db.add_queue(
                    file_path, title,
                    description=self.desc_edit.toPlainText().strip(),
                    hashtags=self.tags_edit.text().strip(),
                    scheduled_at=scheduled_at,
                    thumbnail_path=thumb, combo_id=combo_id)
                db.set_targets(qid, platforms)
                db.add_log(qid, "", "info",
                           f"Đã thêm vào hàng đợi, lịch đăng {scheduled_at}.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi",
                                 f"Không lưu được: {exc}")
            return
        self.accept()
