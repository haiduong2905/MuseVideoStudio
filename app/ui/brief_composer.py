"""Màn 2 — Soạn brief: điền form -> xuất brief chuẩn (copy clipboard + lưu DB)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox,
                               QDialog, QFileDialog, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from app.core import db
from app.core.brief import Brief, build_brief_text
from app.ui.widgets import (card, card2, dim_label, ghost_button,
                            primary_button, section_label, subtitle_label,
                            title_label)

RATIOS = ["16:9", "9:16", "1:1"]
DURATIONS = [("5 giây", 5), ("10 giây", 10), ("15 giây", 15)]
STYLES = ["Cinematic", "Tự nhiên", "Hoạt hình", "Sang trọng", "Vui nhộn"]
TAB_KEYS = ["text", "image", "video", "template"]


class BriefComposerView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.ref_images: list[str] = []
        self._project_id: int | None = None
        self._editing_brief_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(title_label("Soạn brief"))
        root.addWidget(subtitle_label(
            "Điền thông tin, xuất brief chuẩn để dán vào khung chat"))

        # -- chọn dự án / cảnh --
        proj_row = QHBoxLayout()
        proj_row.addWidget(dim_label("Dự án:"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(220)
        self.project_combo.currentIndexChanged.connect(
            self._on_project_changed)
        proj_row.addWidget(self.project_combo)
        new_proj = ghost_button("＋ Dự án mới")
        new_proj.clicked.connect(self._on_new_project)
        proj_row.addWidget(new_proj)
        proj_row.addWidget(dim_label("Tên cảnh:"))
        self.scene_name = QLineEdit()
        self.scene_name.setPlaceholderText("VD: Mèo con khám phá")
        self.scene_name.setMinimumWidth(200)
        proj_row.addWidget(self.scene_name)
        proj_row.addStretch(1)
        root.addLayout(proj_row)

        self.tabs = QTabWidget()
        for name in ["Từ văn bản", "Từ ảnh", "Từ video", "Template"]:
            w = QWidget()
            if name == "Từ văn bản":
                w.setLayout(self._build_form())
            else:
                lay = QVBoxLayout(w)
                lay.addWidget(dim_label(
                    "Tab này sẽ hoàn thiện ở bản tiếp theo."))
                lay.addStretch(1)
            self.tabs.addTab(w, name)
        root.addWidget(self.tabs, 1)
        self.refresh()

    def _build_form(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(16)
        cols = QHBoxLayout()
        cols.setSpacing(16)

        left = card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.addWidget(section_label("Mô tả video (Prompt)"))
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText(
            "A cute orange cat walking in a sunny garden, cinematic, natural "
            "movement, 16:9 aspect ratio, high quality, with natural sound.")
        self.prompt.setFixedHeight(130)
        self.prompt.textChanged.connect(self._update_count)
        ll.addWidget(self.prompt)
        self.count = QLabel("0/2000")
        self.count.setProperty("faint", True)
        self.count.setAlignment(Qt.AlignmentFlag.AlignRight)
        ll.addWidget(self.count)

        right = card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        self.ref_title = section_label("Ảnh tham chiếu (0/9)")
        rl.addWidget(self.ref_title)
        self.ref_grid = QGridLayout()
        self.ref_grid.setSpacing(8)
        rl.addLayout(self.ref_grid)
        add = ghost_button("＋  Thêm ảnh")
        add.clicked.connect(self._on_add_images)
        rl.addWidget(add)
        rl.addStretch(1)
        self._render_ref_grid()

        cols.addWidget(left, 3)
        cols.addWidget(right, 2)
        lay.addLayout(cols)

        opts = QHBoxLayout()
        opts.setSpacing(24)

        ratio_box = QVBoxLayout()
        ratio_box.addWidget(section_label("Điểm chuẩn"))
        rr = QHBoxLayout()
        self.ratio_group = QButtonGroup(self)
        for i, r in enumerate(RATIOS):
            b = QPushButton(r)
            b.setCheckable(True)
            b.setChecked(r == "9:16")
            self.ratio_group.addButton(b, i)
            rr.addWidget(b)
        ratio_box.addLayout(rr)

        dur_box = QVBoxLayout()
        dur_box.addWidget(section_label("Duration"))
        dr = QHBoxLayout()
        self.dur_group = QButtonGroup(self)
        for i, (label, _secs) in enumerate(DURATIONS):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(label == "10 giây")
            self.dur_group.addButton(b, i)
            dr.addWidget(b)
        dur_box.addLayout(dr)

        style_box = QVBoxLayout()
        style_box.addWidget(section_label("Style"))
        self.style = QComboBox()
        self.style.addItems(STYLES)
        style_box.addWidget(self.style)

        opts.addLayout(ratio_box)
        opts.addLayout(dur_box)
        opts.addLayout(style_box)
        opts.addStretch(1)
        lay.addLayout(opts)

        row = QHBoxLayout()
        clear_btn = ghost_button("Xóa trắng")
        clear_btn.clicked.connect(self._on_clear)
        row.addWidget(clear_btn)
        row.addStretch(1)
        export = primary_button("✦  Xuất brief")
        export.setFixedHeight(44)
        export.setMinimumWidth(260)
        export.clicked.connect(self._on_export)
        row.addWidget(export)
        lay.addLayout(row)
        lay.addStretch(1)
        return lay

    # -- ảnh tham chiếu --
    def _update_count(self) -> None:
        self.count.setText(f"{len(self.prompt.toPlainText())}/2000")

    def _render_ref_grid(self) -> None:
        while self.ref_grid.count():
            item = self.ref_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        import os
        for i, p in enumerate(self.ref_images[:9]):
            cell = card2()
            cell.setFixedSize(96, 96)
            cell.setToolTip(p)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(4, 4, 4, 4)
            cl.addWidget(dim_label(os.path.basename(p)[:14]),
                         alignment=Qt.AlignmentFlag.AlignCenter)
            self.ref_grid.addWidget(cell, i // 3, i % 3)
        self.ref_title.setText(f"Ảnh tham chiếu ({len(self.ref_images)}/9)")

    def _on_add_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh tham chiếu", "",
            "Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)")
        for f in files:
            if len(self.ref_images) >= 9:
                break
            if f not in self.ref_images:
                self.ref_images.append(f)
        self._render_ref_grid()

    # -- dự án --
    def _on_new_project(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Dự án mới")
        lay = QVBoxLayout(dlg)
        name_ed = QLineEdit()
        name_ed.setPlaceholderText("Tên dự án (VD: BeastBytes)")
        code_ed = QLineEdit()
        code_ed.setPlaceholderText("Mã dự án (VD: BEASTBYTES)")
        lay.addWidget(dim_label("Tên dự án:"))
        lay.addWidget(name_ed)
        lay.addWidget(dim_label("Mã dự án (viết tắt, khớp với manifest):"))
        lay.addWidget(code_ed)
        btns = QHBoxLayout()
        ok = primary_button("Tạo")
        cancel = ghost_button("Hủy")
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        if dlg.exec() and name_ed.text().strip():
            try:
                pid = db.create_project(name_ed.text().strip(),
                                        code_ed.text().strip() or
                                        name_ed.text().strip())
            except ValueError as e:
                QMessageBox.warning(self, "Không tạo được", str(e))
                return
            self.refresh_projects()
            self._select_project(pid)

    def refresh_projects(self) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self._projects = db.list_projects()
        for p in self._projects:
            self.project_combo.addItem(
                f"{p['name']} ({p['code']})", p["id"])
        self.project_combo.blockSignals(False)
        if self._projects:
            self._on_project_changed(0)

    def _select_project(self, pid: int) -> None:
        for i in range(self.project_combo.count()):
            if self.project_combo.itemData(i) == pid:
                self.project_combo.setCurrentIndex(i)
                return

    def _on_project_changed(self, index: int) -> None:
        if index < 0 or not self._projects:
            self._project_id = None
            return
        self._project_id = self.project_combo.itemData(index)

    # -- xuất brief --
    def _on_clear(self) -> None:
        self.prompt.clear()
        self.scene_name.clear()
        self.ref_images = []
        self._render_ref_grid()
        self._editing_brief_id = None

    def _collect(self) -> Brief | None:
        if self._project_id is None:
            QMessageBox.warning(self, "Chưa có dự án",
                                "Hãy tạo dự án trước khi xuất brief.")
            return None
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Thiếu mô tả",
                                "Hãy nhập mô tả video (prompt).")
            return None
        proj = db.get_project(self._project_id)
        briefs = db.list_briefs(self._project_id)
        scene_no = len(briefs) + 1
        tab = TAB_KEYS[self.tabs.currentIndex()]
        ratio = RATIOS[self.ratio_group.checkedId()]
        duration = DURATIONS[self.dur_group.checkedId()][1]
        try:
            return Brief(
                project_code=proj["code"], scene_no=scene_no,
                scene_name=self.scene_name.text().strip(), tab=tab,
                prompt=prompt, ratio=ratio, duration=duration,
                style=self.style.currentText(),
                ref_count=len(self.ref_images))
        except ValueError as e:
            QMessageBox.warning(self, "Brief chưa hợp lệ", str(e))
            return None

    def _on_export(self) -> None:
        brief = self._collect()
        if brief is None:
            return
        text = build_brief_text(brief)
        QApplication.clipboard().setText(text)
        # lưu vào DB để màn Dự án theo dõi
        try:
            if self._editing_brief_id:
                db.update_brief(
                    self._editing_brief_id, prompt=self.prompt.toPlainText(),
                    ratio=brief.ratio, duration=brief.duration,
                    style=brief.style,
                    ref_images=self.ref_images,
                    scene_name=self.scene_name.text().strip(),
                    status="sent", exported_at=db.now_iso())
            else:
                db.create_brief(
                    self._project_id, brief.scene_no,
                    self.scene_name.text().strip(), brief.tab,
                    self.prompt.toPlainText(), brief.ratio,
                    brief.duration, brief.style, self.ref_images)
                db.update_brief(
                    db.list_briefs(self._project_id)[-1]["id"],
                    status="sent", exported_at=db.now_iso())
        except Exception as e:  # noqa: BLE001 - lưu DB lỗi vẫn báo đã copy
            QMessageBox.warning(
                self, "Đã copy brief",
                f"Brief đã copy vào clipboard, nhưng lưu vào dự án lỗi:\n{e}")
            return
        QMessageBox.information(
            self, "Đã xuất brief",
            "Brief chuẩn đã copy vào clipboard.\n"
            "Anh dán vào khung chat để em dựng video nhé!")
        self._on_clear()

    def set_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)

    def load_brief(self, brief_id: int) -> None:
        """Nạp brief có sẵn vào form để sửa (từ màn Dự án)."""
        b = db.get_brief(brief_id)
        if not b:
            return
        self._editing_brief_id = brief_id
        self._select_project(b["project_id"])
        self.scene_name.setText(b.get("scene_name") or "")
        self.prompt.setPlainText(b.get("prompt") or "")
        try:
            self.ratio_group.button(RATIOS.index(b.get("ratio") or
                                                 "9:16")).setChecked(True)
        except ValueError:
            pass
        for i, (_label, secs) in enumerate(DURATIONS):
            if secs == (b.get("duration") or 10):
                self.dur_group.button(i).setChecked(True)
        self.style.setCurrentText(b.get("style") or "Cinematic")
        import json
        try:
            self.ref_images = json.loads(b.get("ref_images") or "[]")
        except (ValueError, TypeError):
            self.ref_images = []
        self._render_ref_grid()
        self.tabs.setCurrentIndex(
            TAB_KEYS.index(b.get("tab") or "text")
            if (b.get("tab") or "text") in TAB_KEYS else 0)

    def refresh(self) -> None:
        self.refresh_projects()
