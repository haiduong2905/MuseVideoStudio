"""Màn 3 — Quản lý dự án và cảnh (brief)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox,
                               QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QVBoxLayout,
                               QWidget)

from app.core import db
from app.core.brief import Brief, brief_from_db_row, build_brief_text
from app.ui.widgets import (card, card2, chip, dim_label, ghost_button,
                            primary_button, section_label, title_label)

BRIEF_STATUS_LABEL = {
    "draft": ("nháp", "gray"),
    "sent": ("đã gửi", "blue"),
    "rendering": ("đang dựng", "amber"),
    "done": ("đã về kho", "green"),
}


class ProjectsView(QWidget):
    def __init__(self, nav=None) -> None:
        super().__init__()
        self._nav = nav
        self._project_id: int | None = None
        self._briefs: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # -- chọn dự án --
        top = QHBoxLayout()
        top.addWidget(dim_label("Dự án:"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(240)
        self.project_combo.currentIndexChanged.connect(
            self._on_project_changed)
        top.addWidget(self.project_combo)
        top.addStretch(1)
        root.addLayout(top)

        self.crumb = dim_label("Dự án")
        root.addWidget(self.crumb)

        head = QHBoxLayout()
        self.title = title_label("—")
        head.addWidget(self.title)
        head.addStretch(1)
        add_btn = primary_button("＋ Thêm cảnh")
        add_btn.clicked.connect(self._on_add_scene)
        head.addWidget(add_btn)
        prev_btn = ghost_button("Xem trước")
        prev_btn.clicked.connect(self._on_preview)
        head.addWidget(prev_btn)
        exp_btn = ghost_button("⤓ Xuất brief")
        exp_btn.clicked.connect(self._on_export_all)
        head.addWidget(exp_btn)
        root.addLayout(head)
        self.meta = dim_label("")
        root.addWidget(self.meta)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        left = card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.addWidget(section_label("Danh sách cảnh"))
        self.scene_list = QListWidget()
        self.scene_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.scene_list.currentRowChanged.connect(self._on_scene_selected)
        # lưu thứ tự kéo-thả
        self.scene_list.model().rowsMoved.connect(self._on_reordered)
        ll.addWidget(self.scene_list)
        row = QHBoxLayout()
        del_btn = ghost_button("🗑 Xóa cảnh")
        del_btn.clicked.connect(self._on_delete_scene)
        row.addWidget(del_btn)
        row.addStretch(1)
        ll.addLayout(row)
        cols.addWidget(left, 2)

        right = card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(12)
        rl.addWidget(section_label("Chi tiết cảnh"))
        self.thumb = card2()
        self.thumb.setFixedHeight(160)
        thl = QVBoxLayout(self.thumb)
        thl.addWidget(dim_label("Ảnh cảnh"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(self.thumb)
        rl.addWidget(section_label("Prompt"))
        self.prompt_lbl = dim_label("—")
        rl.addWidget(self.prompt_lbl)
        self.status_chip = chip("nháp", "gray")
        rl.addWidget(self.status_chip, alignment=Qt.AlignmentFlag.AlignLeft)
        self.scene_meta = dim_label("")
        rl.addWidget(self.scene_meta)
        edit_btn = ghost_button("✏️ Sửa trong Soạn brief")
        edit_btn.clicked.connect(self._on_edit_scene)
        rl.addWidget(edit_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        rl.addStretch(1)
        cols.addWidget(right, 3)

        root.addLayout(cols, 1)
        self.refresh()

    # -- dữ liệu --
    def refresh(self) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self._projects = db.list_projects()
        for p in self._projects:
            self.project_combo.addItem(
                f"{p['name']} ({p['code']})", p["id"])
        self.project_combo.blockSignals(False)
        if self._projects:
            idx = 0
            if self._project_id:
                for i, p in enumerate(self._projects):
                    if p["id"] == self._project_id:
                        idx = i
                        break
            self.project_combo.setCurrentIndex(idx)
            self._on_project_changed(idx)
        else:
            self._project_id = None
            self._briefs = []
            self._render_scenes()

    def _on_project_changed(self, index: int) -> None:
        if index < 0 or not self._projects:
            return
        p = self._projects[index]
        self._project_id = p["id"]
        self.crumb.setText(f"Dự án  >  {p['name']}")
        self.title.setText(p["name"])
        self._briefs = db.list_briefs(p["id"])
        total_dur = sum(b.get("duration") or 0 for b in self._briefs)
        self.meta.setText(
            f"{len(self._briefs)} cảnh · Tổng thời lượng ~{total_dur} giây · "
            f"Cập nhật: {p.get('created_at') or ''}")
        self._render_scenes()

    def _render_scenes(self) -> None:
        self.scene_list.blockSignals(True)
        self.scene_list.clear()
        for b in self._briefs:
            label = f"{b['scene_no']}. {b['scene_name'] or 'Cảnh'} — " \
                    f"{b['duration']} giây"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, b["id"])
            self.scene_list.addItem(item)
        self.scene_list.blockSignals(False)
        if self._briefs:
            self.scene_list.setCurrentRow(0)
        else:
            self._on_scene_selected(-1)

    def _current_brief(self) -> dict | None:
        row = self.scene_list.currentRow()
        if 0 <= row < len(self._briefs):
            return self._briefs[row]
        return None

    def _on_scene_selected(self, row: int) -> None:
        b = self._current_brief()
        if not b:
            self.prompt_lbl.setText("—")
            self.scene_meta.setText("")
            return
        p = (b.get("prompt") or "")
        self.prompt_lbl.setText(p[:220] + ("..." if len(p) > 220 else ""))
        label, color = BRIEF_STATUS_LABEL.get(b.get("status") or "draft",
                                              ("nháp", "gray"))
        self.status_chip.setText(label)
        self.status_chip.setProperty("chip", color)
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        self.scene_meta.setText(
            f"Thời lượng: {b.get('duration')} giây · "
            f"Tỉ lệ: {b.get('ratio')} · Style: {b.get('style')}")

    def _on_reordered(self, *args) -> None:
        """Lưu thứ tự cảnh sau kéo-thả."""
        for row in range(self.scene_list.count()):
            bid = self.scene_list.item(row).data(Qt.ItemDataRole.UserRole)
            try:
                db.update_brief(bid, scene_no=row + 1)
            except Exception:
                pass
        if self._project_id:
            self._briefs = db.list_briefs(self._project_id)
            self._render_scenes()

    # -- thao tác --
    def _on_add_scene(self) -> None:
        if self._nav:
            self._nav(1)  # sang màn Soạn brief

    def _on_edit_scene(self) -> None:
        b = self._current_brief()
        if not b:
            QMessageBox.information(self, "Chưa chọn",
                                    "Hãy chọn 1 cảnh trước.")
            return
        if self._nav:
            self._nav(1, 0, b["id"])

    def _on_delete_scene(self) -> None:
        b = self._current_brief()
        if not b:
            return
        ok = QMessageBox.question(
            self, "Xóa cảnh",
            f"Xóa cảnh {b['scene_no']} khỏi dự án?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        db.delete_brief(b["id"])
        self._on_project_changed(self.project_combo.currentIndex())

    def _on_preview(self) -> None:
        b = self._current_brief()
        if not b:
            QMessageBox.information(self, "Chưa chọn",
                                    "Hãy chọn 1 cảnh trước.")
            return
        proj = db.get_project(self._project_id or 0) or {}
        text = build_brief_text(brief_from_db_row(
            b, proj.get("code", "")))
        box = QMessageBox(self)
        box.setWindowTitle("Xem trước brief")
        box.setText(f"Cảnh {b['scene_no']} — {b['scene_name'] or ''}\n\n"
                    f"{text}")
        box.exec()

    def _on_export_all(self) -> None:
        if not self._briefs:
            QMessageBox.information(self, "Trống",
                                    "Dự án chưa có cảnh nào.")
            return
        proj = db.get_project(self._project_id or 0) or {}
        parts = [build_brief_text(brief_from_db_row(b, proj.get("code", "")))
                 for b in self._briefs]
        QApplication.clipboard().setText("\n\n".join(parts))
        QMessageBox.information(
            self, "Đã xuất",
            f"Đã copy {len(parts)} brief vào clipboard.\n"
            "Anh dán vào khung chat để em dựng nhé!")
