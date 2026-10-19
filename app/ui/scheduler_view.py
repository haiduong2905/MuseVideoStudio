"""Màn 5 — Lịch đăng tự động (dùng core/scheduler.py + QueueModel kế thừa)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCalendarWidget, QComboBox,
                               QHBoxLayout, QLabel, QMenu, QMessageBox,
                               QStackedWidget, QTabBar, QTableView, QVBoxLayout,
                               QWidget)

from app.core import db
from app.ui.add_dialog import AddDialog
from app.ui.batch_dialog import BatchDialog
from app.ui.detail_dialog import DetailDialog
from app.ui.queue_model import QueueModel
from app.ui.widgets import (card, card2, chip, dim_label, ghost_button,
                            primary_button, section_label, subtitle_label,
                            title_label)


class SchedulerView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(title_label("Lịch đăng tự động"))
        root.addWidget(subtitle_label(
            "Lên lịch, quản lý nội dung và trạng thái đăng"))

        bar = QHBoxLayout()
        self.tabbar = QTabBar()
        self.pages = QStackedWidget()
        self.tabbar.addTab("Lịch đăng")
        self.pages.addWidget(self._page_calendar())
        self.tabbar.addTab("Hàng đợi đăng")
        self.pages.addWidget(self._page_queue(done_only=False))
        self.tabbar.addTab("Lịch sử đăng")
        self.pages.addWidget(self._page_queue(done_only=True))
        self.tabbar.currentChanged.connect(self.pages.setCurrentIndex)
        bar.addWidget(self.tabbar)
        bar.addStretch(1)
        new_btn = primary_button("＋ Tạo lịch đăng")
        new_btn.clicked.connect(self._on_batch)
        bar.addWidget(new_btn)
        root.addLayout(bar)
        root.addWidget(self.pages, 1)

    # -- tab Lịch đăng: calendar + chi tiết --
    def _page_calendar(self) -> QWidget:
        w = QWidget()
        cols = QHBoxLayout(w)
        cols.setContentsMargins(0, 8, 0, 0)
        cols.setSpacing(16)

        cal_card = card()
        cl = QVBoxLayout(cal_card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.addWidget(section_label("Tháng 10, 2026"))
        self.cal = QCalendarWidget()
        cl.addWidget(self.cal)
        cols.addWidget(cal_card, 3)

        detail = card()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(16, 16, 16, 16)
        dl.setSpacing(10)
        dl.addWidget(section_label("Chi tiết bài đăng"))
        th = card2()
        th.setFixedHeight(120)
        thl = QVBoxLayout(th)
        thl.addWidget(dim_label("Ảnh"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(th)
        dl.addWidget(QLabel("<b>Câu chuyện mèo – Cảnh 1</b>"))
        dl.addWidget(dim_label("05/10/2026 10:00"))
        dl.addWidget(section_label("Nội dung mô tả"))
        dl.addWidget(dim_label("Chú mèo nhỏ khám phá thế giới xung quanh"))
        dl.addWidget(dim_label("#fun #cat #cute #viralvideo"))
        dl.addWidget(section_label("Nền tảng đăng"))
        for plat, st, color in [("TikTok", "Đã lên lịch", "blue"),
                                ("Facebook", "Đã lên lịch", "blue"),
                                ("YouTube", "Đã lên lịch", "blue")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(plat))
            row.addStretch(1)
            row.addWidget(chip(st, color))
            dl.addLayout(row)
        dl.addWidget(primary_button("Sửa lịch đăng"))
        dl.addStretch(1)
        cols.addWidget(detail, 2)
        return w

    # -- tab Hàng đợi / Lịch sử: bảng QueueModel --
    def _page_queue(self, done_only: bool) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Lọc:"))
        combo = QComboBox()
        model = QueueModel()
        for key, label in QueueModel.FILTERS:
            combo.addItem(label, key)
        if done_only:
            combo.setCurrentIndex(
                combo.findData("done"))
            combo.setEnabled(False)
            model.status_filter = "done"
        combo.currentIndexChanged.connect(
            lambda i, m=model, c=combo: self._on_filter(m, c, i))
        bar.addWidget(combo)
        count_lbl = QLabel("")
        count_lbl.setProperty("faint", True)
        bar.addWidget(count_lbl)
        bar.addStretch(1)
        if not done_only:
            add_btn = ghost_button("➕ Thêm video")
            add_btn.clicked.connect(self._on_add)
            bar.addWidget(add_btn)
        lay.addLayout(bar)

        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.doubleClicked.connect(
            lambda _i, m=model, t=table: self._on_detail(m, t))
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, m=model, t=table: self._on_menu(pos, m, t))
        lay.addWidget(table, 1)

        if done_only:
            self._hist_model = model
            self._hist_table = table
        else:
            self._queue_model = model
            self._queue_table = table
        model.refresh()
        return w

    def _on_filter(self, model, combo, index) -> None:
        model.status_filter = combo.itemData(index)
        model.refresh()

    def refresh(self) -> None:
        for m in (getattr(self, "_queue_model", None),
                  getattr(self, "_hist_model", None)):
            if m is not None:
                try:
                    m.refresh()
                except Exception:
                    pass

    # -- thao tác (kế thừa logic SocialUploader) --
    def _selected_id(self, model, table) -> int | None:
        idx = table.currentIndex()
        if not idx.isValid():
            return None
        return model.items[idx.row()]["id"]

    def _on_add(self) -> None:
        if AddDialog(self).exec():
            self.refresh()

    def _on_batch(self) -> None:
        if BatchDialog(self).exec():
            self.refresh()

    def _on_detail(self, model, table) -> None:
        qid = self._selected_id(model, table)
        if qid is None:
            QMessageBox.information(self, "Chưa chọn",
                                    "Hãy chọn 1 video trong bảng trước.")
            return
        DetailDialog(self, qid).exec()
        self.refresh()

    def _on_menu(self, pos, model, table) -> None:
        has_sel = bool(table.selectionModel().selectedRows())
        menu = QMenu(self)
        act_detail = menu.addAction("🔍 Chi tiết")
        act_detail.setEnabled(has_sel)
        act_detail.triggered.connect(lambda: self._on_detail(model, table))
        act_edit = menu.addAction("✏️ Sửa")
        act_edit.setEnabled(has_sel)
        act_edit.triggered.connect(lambda: self._on_edit(model, table))
        act_del = menu.addAction("🗑 Xóa")
        act_del.setEnabled(has_sel)
        act_del.triggered.connect(lambda: self._on_delete(model, table))
        menu.addSeparator()
        act_post = menu.addAction("🚀 Đăng ngay")
        act_post.setEnabled(has_sel)
        act_post.triggered.connect(lambda: self._on_post_now(model, table))
        menu.exec(table.viewport().mapToGlobal(pos))

    def _on_edit(self, model, table) -> None:
        qid = self._selected_id(model, table)
        if qid is None:
            return
        item = db.get_queue(qid) or {}
        if (item.get("content_type") or "video") == "post":
            QMessageBox.information(
                self, "Bài viết",
                "Chưa hỗ trợ sửa bài viết — hãy xóa và tạo lại bài mới.")
            return
        if AddDialog(self, queue_id=qid).exec():
            self.refresh()

    def _on_delete(self, model, table) -> None:
        rows = sorted({i.row() for i in
                       table.selectionModel().selectedRows()},
                      reverse=True)
        if not rows:
            QMessageBox.information(self, "Chưa chọn",
                                    "Hãy chọn ít nhất 1 video trong bảng.")
            return
        n = len(rows)
        ok = QMessageBox.question(
            self, "Xóa video",
            f"Xóa {n} video khỏi hàng đợi?\n"
            "(Video đã đăng/lên lịch trên nền tảng không bị ảnh hưởng.)")
        if ok != QMessageBox.StandardButton.Yes:
            return
        for r in rows:
            qid = model.items[r]["id"]
            try:
                db.delete_queue(qid)
                db.add_log(qid, "", "info", "Đã xóa khỏi hàng đợi.")
            except Exception:  # noqa: BLE001
                pass
        self.refresh()

    def _on_post_now(self, model, table) -> None:
        qid = self._selected_id(model, table)
        if qid is None:
            return
        ok = QMessageBox.question(
            self, "Đăng ngay",
            "Bỏ qua lịch hẹn và đăng video này ngay bây giờ?")
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            db.update_queue(qid, scheduled_at=db.now_iso())
            db.reset_targets_for_repost(qid)
            db.add_log(qid, "", "info",
                       "Người dùng bấm Đăng ngay, sẽ đăng trong ~30 giây.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi", f"Không thực hiện được: {exc}")
            return
        self.refresh()
        QMessageBox.information(self, "Đã nhận lệnh",
                                "Video sẽ được đăng trong khoảng 30 giây tới.\n"
                                "Hãy để app tiếp tục chạy.")
