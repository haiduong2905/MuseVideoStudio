"""Dialog thêm NHIỀU video một lúc + ⚡ xếp lịch nhanh.

- Chọn nhiều file (hoặc kéo-thả), mỗi video nhập: tiêu đề / mô tả / hashtag /
  giờ đăng / ảnh bìa.
- Xếp lịch nhanh: nhập các khung giờ cố định trong ngày (VD 5 khung giờ =
  5 video/ngày), chọn ngày bắt đầu -> app tự chia đều video vào các khung giờ.
"""
import os
import re
from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit,
                               QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QMessageBox, QPushButton,
                               QScrollArea, QSplitter, QTextEdit, QVBoxLayout)

from app.core import config, db
from app.core.md_titles import fill_video, parse_md
from app.core.thumbnails import (ACCEPT_EXTS, describe_rules, discard_persisted,
                                 persist_candidate, prepare_thumbnail)
from app.ui.datetime_picker import (DateTimePicker, fix_calendar_popup,
                                     time_slots)
from app.ui.thumb_candidates import ThumbCandidates

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
MIN_LEAD_MINUTES = 10


# ---------------------------------------------------------------- pure logic
def parse_slots(text: str) -> list[str]:
    """'07:00, 11:30' -> ['07:00', '11:30'] (sort + unique).

    Raise ValueError khi format sai.
    """
    parts = [p.strip() for p in text.replace(";", ",").split(",")
             if p.strip()]
    out: list[str] = []
    for p in parts:
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", p)
        if not m:
            raise ValueError(f"Khung giờ '{p}' không hợp lệ (đúng: HH:MM).")
        h, mi = int(m.group(1)), int(m.group(2))
        if not (0 <= h <= 23 and 0 <= mi <= 59):
            raise ValueError(f"Khung giờ '{p}' không hợp lệ.")
        out.append(f"{h:02d}:{mi:02d}")
    if not out:
        raise ValueError("Nhập ít nhất 1 khung giờ (VD: 07:00, 12:00).")
    return sorted(set(out))


def build_quick_plan(slots: list[str], start: date, now: datetime,
                     n: int, lead_minutes: int = MIN_LEAD_MINUTES) -> list[str]:
    """Xếp n video vào các khung giờ từ ngày `start`.

    Bỏ qua các khung đã qua (so với now + lead_minutes). Trả về list ISO
    'YYYY-MM-DDTHH:MM:SS' đủ n phần tử (sang ngày hôm sau nếu hết khung).
    """
    plan: list[str] = []
    day = start
    guard = 0
    while len(plan) < n and guard < 400 + n:
        for s in slots:
            cand = datetime(day.year, day.month, day.day,
                            int(s[:2]), int(s[3:5]))
            if cand > now + timedelta(minutes=lead_minutes):
                plan.append(cand.strftime("%Y-%m-%dT%H:%M:%S"))
                if len(plan) >= n:
                    break
        day += timedelta(days=1)
        guard += 1
    return plan


def title_from_filename(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace("_", " ").replace("-", " ").strip()


# ---------------------------------------------------------------- dialog
class BatchDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thêm nhiều video")
        self.resize(1220, 820)  # mặc định rộng để danh sách + form dễ nhìn
        self.setMinimumSize(1020, 700)  # vẫn cho phóng to/thu nhỏ tùy ý
        # Cho phép bấm nút maximize (mặc định QDialog không có)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setAcceptDrops(True)
        self.videos: list[dict] = []  # file_path,title,description,hashtags,
        #                              # scheduled_at,thumbnail_path
        self._current = -1

        # -- nền tảng (chung cho cả đợt) --
        self.combo_box = QComboBox()
        self.combo_box.addItem("— Không dùng combo (chọn tay từng nền tảng) —",
                               None)
        for c in db.list_combos():
            self.combo_box.addItem(f"📺 {c['name']}", c["id"])
        self.combo_box.currentIndexChanged.connect(self._on_combo_changed)
        self._combo_accounts: dict = {}
        combo_row = QHBoxLayout()
        combo_row.addWidget(QLabel("Combo kênh:"))
        combo_row.addWidget(self.combo_box, 1)
        self.cb_yt = QCheckBox("YouTube")
        self.cb_fb = QCheckBox("Facebook")
        self.cb_tt = QCheckBox("TikTok (vào hộp nháp)")
        # Mặc định luôn tick hết cả 3 nền tảng
        for cb in (self.cb_yt, self.cb_fb, self.cb_tt):
            cb.setChecked(True)
        plat_row = QHBoxLayout()
        plat_row.addWidget(QLabel("Đăng lên:"))
        plat_row.addWidget(self.cb_yt)
        plat_row.addWidget(self.cb_fb)
        plat_row.addWidget(self.cb_tt)
        plat_row.addStretch(1)

        # -- trái: danh sách file --
        self.list_w = QListWidget()
        self.list_w.currentRowChanged.connect(self._on_select)
        add_btn = QPushButton("➕ Thêm file…")
        add_btn.clicked.connect(self._pick_files)
        del_btn = QPushButton("➖ Xóa mục")
        del_btn.clicked.connect(self._del_current)
        left_btns = QHBoxLayout()
        left_btns.addWidget(add_btn)
        left_btns.addWidget(del_btn)
        left = QVBoxLayout()
        left.addWidget(QLabel("Danh sách video:"))
        left.addWidget(self.list_w, 1)
        left.addLayout(left_btns)
        left_w = _wrap(left)

        # -- phải: form từng video --
        self.file_lbl = QLabel("Chưa chọn video nào")
        self.file_lbl.setStyleSheet("color: gray;")
        self.file_lbl.setWordWrap(True)
        self.title_edit = QLineEdit()
        self.title_edit.setMaxLength(100)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(120)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("VD: #beastbytes #animalfacts")
        self.dt_edit = DateTimePicker()
        # Không cho lên lịch quá khứ; có Facebook -> tối thiểu +10 phút
        self._update_min_time()
        self.cb_fb.toggled.connect(lambda _c: self._update_min_time())
        # ảnh bìa
        self.thumb_edit = QLineEdit()
        self.thumb_edit.setReadOnly(True)
        self.thumb_edit.setPlaceholderText("Chưa có ảnh bìa (không bắt buộc)")
        thumb_btn = QPushButton("Chọn…")
        thumb_btn.clicked.connect(self._pick_thumb)
        thumb_gen_btn = QPushButton("🎬 Tạo từ video")
        thumb_gen_btn.setToolTip("Tự tách 8 frame từ video để chọn làm ảnh bìa")
        thumb_gen_btn.clicked.connect(self._gen_thumbs)
        thumb_clear = QPushButton("Xóa")
        thumb_clear.clicked.connect(self._clear_thumb)
        thumb_row = QHBoxLayout()
        thumb_row.addWidget(self.thumb_edit, 1)
        thumb_row.addWidget(thumb_btn)
        thumb_row.addWidget(thumb_gen_btn)
        thumb_row.addWidget(thumb_clear)
        self.thumb_cands = ThumbCandidates()
        self.thumb_cands.picked.connect(self._on_candidate_picked)

        form = QFormLayout()
        form.addRow("File:", self.file_lbl)
        form.addRow("Tiêu đề:", self.title_edit)
        form.addRow("Mô tả:", self.desc_edit)
        form.addRow("Hashtag:", self.tags_edit)
        form.addRow("Lịch đăng:", self.dt_edit)
        form.addRow("Ảnh bìa:", thumb_row)
        form.addRow("", self.thumb_cands)
        rules = QLabel(describe_rules())
        rules.setWordWrap(True)
        rules.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", rules)

        for w in (self.title_edit, self.desc_edit, self.tags_edit,
                  self.thumb_edit):
            w.textChanged.connect(self._form_edited)
        self.dt_edit.dateTimeChanged.connect(self._form_edited)

        right = QVBoxLayout()
        right.addWidget(QLabel("Thông tin video đang chọn:"))
        right.addLayout(form)
        right.addStretch(1)
        right_w = _wrap(right)
        # Bọc trong scroll để dải ảnh bìa hiện ra không che mất phần dưới
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right_w)
        right_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_w)
        splitter.addWidget(right_scroll)
        splitter.setSizes([430, 720])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        # -- ⚡ xếp lịch nhanh --
        quick = QGroupBox("⚡ Xếp lịch nhanh")
        self.slots_edit = QLineEdit(config.get("quick_slots"))
        self.slots_edit.setPlaceholderText("VD: 07:00, 11:30, 15:30, 19:00")
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.start_date.setCalendarPopup(True)
        fix_calendar_popup(self.start_date)
        quick_btn = QPushButton("Áp dụng xếp lịch")
        quick_btn.clicked.connect(self._apply_quick)
        self.quick_hint = QLabel()
        self.quick_hint.setStyleSheet("color: gray;")
        self._update_quick_hint()
        self.slots_edit.textChanged.connect(self._update_quick_hint)
        qlay = QHBoxLayout()
        qlay.addWidget(QLabel("Khung giờ mỗi ngày:"))
        qlay.addWidget(self.slots_edit, 1)
        # Bộ chọn giờ + nút Thêm (khỏi gõ tay từng khung)
        self.slot_combo = QComboBox()
        self.slot_combo.addItems(time_slots())
        self.slot_combo.setMinimumWidth(100)
        self.slot_combo.setToolTip("Chọn giờ rồi bấm Thêm")
        qlay.addWidget(self.slot_combo)
        add_slot_btn = QPushButton("➕ Thêm")
        add_slot_btn.setToolTip("Thêm khung giờ đã chọn vào danh sách")
        add_slot_btn.clicked.connect(self._add_slot)
        qlay.addWidget(add_slot_btn)
        qlay.addWidget(QLabel("Bắt đầu từ:"))
        qlay.addWidget(self.start_date)
        qlay.addWidget(quick_btn)
        qv = QVBoxLayout(quick)
        qv.addLayout(qlay)
        qv.addWidget(self.quick_hint)
        qv.addWidget(QLabel("Số khung giờ = số video mỗi ngày. App xếp lần lượt "
                            "video 1, 2, 3… vào các khung giờ từ ngày bắt đầu; "
                            "khung giờ đã qua trong hôm nay sẽ tự bỏ qua."))

        # -- dùng chung --
        shared = QGroupBox("Dùng chung cho tất cả video")
        self.shared_desc = QTextEdit()
        self.shared_desc.setMaximumHeight(60)
        self.shared_desc.setPlaceholderText("Mô tả chung…")
        self.shared_tags = QLineEdit()
        self.shared_tags.setPlaceholderText("Hashtag chung…")
        shared_btn = QPushButton("Áp dụng cho tất cả")
        shared_btn.clicked.connect(self._apply_shared)
        auto_title_btn = QPushButton("Tự điền tiêu đề từ tên file")
        auto_title_btn.clicked.connect(self._auto_titles)
        md_btn = QPushButton("📄 Điền từ file md…")
        md_btn.setToolTip(
            "Đọc file md tiêu đề/caption (VD titles-captions.md) và tự điền\n"
            "tiêu đề, mô tả, hashtag cho từng video theo tên file.")
        md_btn.clicked.connect(self._fill_from_md)
        slay = QHBoxLayout()
        slay.addWidget(QLabel("Mô tả:"))
        slay.addWidget(self.shared_desc, 1)
        slay.addWidget(QLabel("Hashtag:"))
        slay.addWidget(self.shared_tags, 1)
        slay.addWidget(shared_btn)
        slay.addWidget(auto_title_btn)
        slay.addWidget(md_btn)
        shared.setLayout(slay)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        btns.button(QDialogButtonBox.StandardButton.Save).setText(
            "Lưu tất cả")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(combo_row)
        lay.addLayout(plat_row)
        lay.addWidget(splitter, 1)
        lay.addWidget(quick)
        lay.addWidget(shared)
        lay.addWidget(btns)

        # Nhớ combo lần trước; chỉ có 1 combo thì tự chọn luôn
        self._restore_combo()

    # -- helpers ----------------------------------------------------------
    def _restore_combo(self) -> None:
        """Khôi phục combo đã dùng lần trước.

        Chỉ có đúng 1 combo -> tự chọn luôn (khỏi bấm).
        """
        if self.combo_box.count() == 2:  # "không dùng" + 1 combo duy nhất
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
    def _update_quick_hint(self) -> None:
        try:
            slots = parse_slots(self.slots_edit.text())
            self.quick_hint.setText(
                f"{len(slots)} khung giờ = {len(slots)} video/ngày.")
        except ValueError as exc:
            self.quick_hint.setText(str(exc))

    def _update_min_time(self) -> None:
        """Giới hạn giờ hẹn tối thiểu: có Facebook -> +10p, không -> +1p."""
        lead = (MIN_LEAD_MINUTES if self.cb_fb.isChecked() else 1)
        self.dt_edit.setMinimumDateTime(
            QDateTime.currentDateTime().addSecs(lead * 60))

    def _on_combo_changed(self, idx: int) -> None:
        """Chọn combo -> tự tick các nền tảng có trong combo."""
        combo_id = self.combo_box.currentData()
        self._combo_accounts = {}
        if not combo_id:
            return
        combo = db.get_combo(combo_id)
        if not combo:
            return
        members = combo["members"]
        self.cb_yt.setChecked("youtube" in members)
        self.cb_fb.setChecked("facebook" in members)
        self.cb_tt.setChecked("tiktok" in members)
        self._combo_accounts = {plat: members[plat]["id"]
                                for plat in members}

    def _default_dt(self) -> QDateTime:
        return QDateTime.currentDateTime().addSecs(3600)

    def _refresh_list(self) -> None:
        self.list_w.blockSignals(True)
        self.list_w.clear()
        for i, v in enumerate(self.videos):
            try:
                dt = datetime.fromisoformat(v["scheduled_at"])
                when = dt.strftime("%d/%m %H:%M")
            except ValueError:
                when = "?"
            self.list_w.addItem(
                f"{i + 1}. {os.path.basename(v['file_path'])} — {when}")
        self.list_w.blockSignals(False)

    def _on_select(self, row: int) -> None:
        self._current = row
        if row < 0 or row >= len(self.videos):
            return
        v = self.videos[row]
        for w in (self.title_edit, self.desc_edit, self.tags_edit):
            w.blockSignals(True)
        self.dt_edit.blockSignals(True)
        try:
            self.file_lbl.setText(v["file_path"])
            self.file_lbl.setToolTip(v["file_path"])
            self.title_edit.setText(v["title"])
            self.desc_edit.setPlainText(v["description"])
            self.tags_edit.setText(v["hashtags"])
            try:
                dt = datetime.fromisoformat(v["scheduled_at"])
                self.dt_edit.setDateTime(
                    QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                              0))
            except ValueError:
                self.dt_edit.setDateTime(self._default_dt())
            self.thumb_edit.setText(v["thumbnail_path"])
            self.thumb_cands.clear()  # đổi video -> xóa dải frame cũ
        finally:
            for w in (self.title_edit, self.desc_edit, self.tags_edit):
                w.blockSignals(False)
            self.dt_edit.blockSignals(False)

    def _form_edited(self, *args) -> None:
        if self._current < 0 or self._current >= len(self.videos):
            return
        v = self.videos[self._current]
        v["title"] = self.title_edit.text()
        v["description"] = self.desc_edit.toPlainText()
        v["hashtags"] = self.tags_edit.text()
        v["scheduled_at"] = self.dt_edit.dateTime().toPython().strftime(
            "%Y-%m-%dT%H:%M:%S")
        self._refresh_list()
        # giữ nguyên lựa chọn
        self.list_w.blockSignals(True)
        self.list_w.setCurrentRow(self._current)
        self.list_w.blockSignals(False)

    # -- thêm/xóa file ----------------------------------------------------
    def _add_files(self, paths: list[str]) -> None:
        added = 0
        for p in paths:
            if not os.path.isfile(p):
                continue
            if not p.lower().endswith(VIDEO_EXTS):
                continue
            if any(v["file_path"] == p for v in self.videos):
                continue
            self.videos.append({
                "file_path": p,
                "title": title_from_filename(p),
                "description": "",
                "hashtags": "",
                "scheduled_at": self._default_dt().toPython().strftime(
                    "%Y-%m-%dT%H:%M:%S"),
                "thumbnail_path": "",
            })
            added += 1
        if added:
            self._refresh_list()
            self.list_w.setCurrentRow(len(self.videos) - 1)

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn video (được chọn nhiều)",
            config.get("last_video_dir") or os.path.expanduser("~"),
            "Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)")
        if paths:
            config.save({"last_video_dir": os.path.dirname(paths[0])})
        self._add_files(paths)

    def _del_current(self) -> None:
        row = self.list_w.currentRow()
        if 0 <= row < len(self.videos):
            del self.videos[row]
            self._current = -1
            self._refresh_list()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.toLocalFile()]
        self._add_files(paths)

    # -- ảnh bìa ----------------------------------------------------------
    def _pick_thumb(self) -> None:
        if self._current < 0:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh bìa",
            config.get("last_image_dir") or os.path.expanduser("~"),
            "Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)")
        if path:
            config.save({"last_image_dir": os.path.dirname(path)})
            discard_persisted(self.videos[self._current]["thumbnail_path"])
            self.videos[self._current]["thumbnail_path"] = path
            self.thumb_edit.setText(path)

    def _gen_thumbs(self) -> None:
        if self._current < 0:
            return
        video = self.videos[self._current].get("file_path") or ""
        if not video or not os.path.isfile(video):
            QMessageBox.warning(self, "Chưa có video",
                                "Hãy chọn video trước khi tách frame.")
            return
        self.thumb_cands.extract(video)

    def _on_candidate_picked(self, path: str) -> None:
        if self._current < 0:
            return
        # Copy ra chỗ bền vững: file tạm sẽ bị xóa khi tách frame video khác
        kept = persist_candidate(path)
        self.thumb_cands.keep(path)
        self.videos[self._current]["thumbnail_path"] = kept
        self.thumb_edit.setText(os.path.basename(kept))

    def _clear_thumb(self) -> None:
        if self._current < 0:
            return
        discard_persisted(self.videos[self._current]["thumbnail_path"])
        self.videos[self._current]["thumbnail_path"] = ""
        self.thumb_edit.setText("")
        self.thumb_cands.clear()

    # -- xếp lịch nhanh / dùng chung --------------------------------------
    def _add_slot(self) -> None:
        """Thêm khung giờ đã chọn vào ô khung giờ (loại trùng, sắp xếp)."""
        try:
            slots = (parse_slots(self.slots_edit.text())
                     if self.slots_edit.text().strip() else [])
        except ValueError:
            slots = []
        new = self.slot_combo.currentText()
        if new not in slots:
            slots.append(new)
            slots.sort()
        self.slots_edit.setText(", ".join(slots))

    def _apply_quick(self) -> None:
        if not self.videos:
            QMessageBox.information(self, "Chưa có video",
                                    "Hãy thêm video vào danh sách trước.")
            return
        try:
            slots = parse_slots(self.slots_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Khung giờ sai", str(exc))
            return
        start = self.start_date.date().toPython()
        plan = build_quick_plan(slots, start, datetime.now(),
                                len(self.videos))
        for v, when in zip(self.videos, plan):
            v["scheduled_at"] = when
        config.save({"quick_slots": self.slots_edit.text().strip()})
        self._refresh_list()
        self._on_select(self.list_w.currentRow())
        QMessageBox.information(
            self, "Đã xếp lịch",
            f"Đã xếp {len(plan)} video vào {len(slots)} khung giờ/ngày "
            f"({', '.join(slots)}), từ {start.strftime('%d/%m/%Y')}.")

    def _apply_shared(self) -> None:
        desc = self.shared_desc.toPlainText().strip()
        tags = self.shared_tags.text().strip()
        if not desc and not tags:
            return
        for v in self.videos:
            if desc:
                v["description"] = desc
            if tags:
                v["hashtags"] = tags
        self._on_select(self.list_w.currentRow())

    def _auto_titles(self) -> None:
        for v in self.videos:
            v["title"] = title_from_filename(v["file_path"])
        self._on_select(self.list_w.currentRow())

    def _fill_from_md(self) -> None:
        """Đọc file md tiêu đề/caption, tự điền theo tên file từng video."""
        if not self.videos:
            QMessageBox.information(self, "Chưa có video",
                                    "Hãy thêm video vào danh sách trước.")
            return
        start_dir = config.get("last_md_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file md tiêu đề/caption",
            start_dir, "Markdown (*.md)")
        if not path:
            return
        config.save({"last_md_dir": os.path.dirname(path)})
        try:
            entries = parse_md(path)
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.critical(self, "Không đọc được file",
                                 f"Lỗi đọc {os.path.basename(path)}:\n{exc}")
            return
        if not entries:
            QMessageBox.warning(
                self, "Không có dữ liệu",
                "Không tìm thấy mục nào có tên file trong md này.\n"
                "File cần có dòng '- File: `ten-video.mp4`' hoặc tên file "
                "trong tiêu đề mục.")
            return
        matched = 0
        for v in self.videos:
            v["__overwrite__"] = True  # dữ liệu trong md luôn ưu tiên
            if fill_video(v, entries):
                matched += 1
        missed = len(self.videos) - matched
        self._on_select(self.list_w.currentRow())
        msg = f"Đã điền {matched}/{len(self.videos)} video từ file md."
        if missed:
            msg += (f"\n{missed} video không khớp tên file trong md — "
                    f"kiểm tra lại tên file.")
        QMessageBox.information(self, "Điền từ file md", msg)

    # -- lưu --------------------------------------------------------------
    def _on_save(self) -> None:
        if not self.videos:
            QMessageBox.warning(self, "Chưa có video",
                                "Hãy thêm ít nhất 1 video.")
            return
        platforms = {"youtube": self.cb_yt.isChecked(),
                     "facebook": self.cb_fb.isChecked(),
                     "tiktok": self.cb_tt.isChecked()}
        if not any(platforms.values()):
            QMessageBox.warning(self, "Thiếu thông tin",
                                "Vui lòng tick ít nhất 1 nền tảng.")
            return
        combo_id = self.combo_box.currentData()
        # Nhớ combo đã dùng cho lần mở dialog sau
        config.save({"default_combo_id": str(combo_id or "")})
        combo_accounts = getattr(self, "_combo_accounts", {}) or {}
        if combo_id:
            # refresh từ DB
            combo = db.get_combo(combo_id)
            if combo:
                combo_accounts = {plat: combo["members"][plat]["id"]
                                  for plat in combo["members"]}
        platforms = {
            plat: (enabled, combo_accounts.get(plat))
            for plat, enabled in platforms.items()
        }
        for i, v in enumerate(self.videos, 1):
            if not v["title"].strip():
                QMessageBox.warning(
                    self, "Thiếu tiêu đề",
                    f"Video {i} ({os.path.basename(v['file_path'])}) "
                    f"chưa có tiêu đề.")
                self.list_w.setCurrentRow(i - 1)
                return
        config.save({"quick_slots": self.slots_edit.text().strip()})
        ok, failed = 0, []
        for v in self.videos:
            thumb = ""
            if v["thumbnail_path"]:
                try:
                    thumb = prepare_thumbnail(v["thumbnail_path"])
                except ValueError as exc:
                    failed.append(f"{os.path.basename(v['file_path'])}: "
                                  f"ảnh bìa lỗi ({exc})")
            try:
                qid = db.add_queue(
                    v["file_path"], v["title"].strip(),
                    description=v["description"].strip(),
                    hashtags=v["hashtags"].strip(),
                    scheduled_at=v["scheduled_at"],
                    thumbnail_path=thumb, combo_id=combo_id)
                db.set_targets(qid, platforms)
                db.add_log(qid, "", "info",
                           f"Đã thêm vào hàng đợi, lịch đăng "
                           f"{v['scheduled_at']}.")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{os.path.basename(v['file_path'])}: {exc}")
        msg = f"Đã thêm {ok}/{len(self.videos)} video vào hàng đợi."
        if failed:
            msg += "\n\nLỗi:\n" + "\n".join(failed)
            QMessageBox.warning(self, "Hoàn tất (có lỗi)", msg)
        else:
            QMessageBox.information(self, "Hoàn tất", msg)
        self.accept()


def _wrap(layout) -> "QWidget":
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    w.setLayout(layout)
    return w
