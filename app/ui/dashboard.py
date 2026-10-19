"""Màn 1 — Dashboard tổng quan."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from app.ui.widgets import (card, card2, dim_label, ghost_button,
                            primary_button, section_label, stat_card,
                            subtitle_label, title_label)


class DashboardView(QWidget):
    def __init__(self, nav=None) -> None:
        super().__init__()
        self._nav = nav  # callback chuyển màn hình (set bởi main_window)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(title_label("Chào mừng trở lại!"))
        root.addWidget(subtitle_label("Tạo video tuyệt vời với Meta Muse AI"))

        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.stat_cards = {}
        for key, label, color in [
            ("projects", "Dự án", "pink"),
            ("total", "Tổng video", "blue"),
            ("processing", "Đang xử lý", "amber"),
            ("done", "Đã hoàn thành", "green"),
        ]:
            c = stat_card(label, "0", color)
            self.stat_cards[key] = c
            stats.addWidget(c)
        root.addLayout(stats)

        root.addWidget(section_label("Tạo nhanh"))
        quick = card()
        ql = QHBoxLayout(quick)
        ql.setContentsMargins(16, 16, 16, 16)
        ql.setSpacing(12)
        for text, tab in [("Từ văn bản", 0), ("Từ ảnh", 1),
                          ("Nhập cảnh (Storyboard)", 2),
                          ("Video từ template", 3)]:
            b = ghost_button(text)
            b.clicked.connect(lambda _=False, t=tab: self._goto_brief(t))
            ql.addWidget(b)
        root.addWidget(quick)

        banner = card()
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(20, 20, 20, 20)
        txt = QVBoxLayout()
        txt.addWidget(section_label(
            "Biến ý tưởng thành video tuyệt vời với Meta Muse AI"))
        go = primary_button("Tạo video ngay  →")
        go.clicked.connect(lambda: self._goto_brief(0))
        txt.addWidget(go, alignment=Qt.AlignmentFlag.AlignLeft)
        bl.addLayout(txt, 1)
        thumb = card2()
        thumb.setFixedSize(220, 120)
        tl = QVBoxLayout(thumb)
        tl.addWidget(dim_label("Ảnh minh họa"),
                     alignment=Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(thumb)
        root.addWidget(banner)

        head = QHBoxLayout()
        head.addWidget(section_label("Dự án gần đây"))
        head.addStretch(1)
        all_btn = ghost_button("Xem tất cả")
        all_btn.clicked.connect(lambda: self._goto(2))
        head.addWidget(all_btn)
        root.addLayout(head)

        projs = QHBoxLayout()
        projs.setSpacing(16)
        for name, meta in [("Câu chuyện mèo", "10 cảnh · Cập nhật 2 giờ trước"),
                           ("Du lịch Đà Nẵng", "8 cảnh · Cập nhật 1 ngày trước"),
                           ("Sản phẩm công nghệ",
                            "6 cảnh · Cập nhật 2 ngày trước"),
                           ("Phong cảnh thiên nhiên",
                            "12 cảnh · Cập nhật 3 ngày trước")]:
            pc = card()
            pl = QVBoxLayout(pc)
            pl.setContentsMargins(12, 12, 12, 12)
            th = card2()
            th.setFixedHeight(90)
            thl = QVBoxLayout(th)
            thl.addWidget(dim_label("Ảnh"),
                          alignment=Qt.AlignmentFlag.AlignCenter)
            pl.addWidget(th)
            pl.addWidget(QLabel(f"<b>{name}</b>"))
            pl.addWidget(dim_label(meta))
            projs.addWidget(pc)
        root.addLayout(projs)
        root.addStretch(1)
        self._proj_cards = projs
        self.refresh()

    def _set_stat(self, key: str, value: str) -> None:
        card_w = self.stat_cards[key]
        # stat_card: layout[0]=label, layout[1]=value
        val_lbl = card_w.layout().itemAt(1).widget()
        val_lbl.setText(value)

    def refresh(self) -> None:
        try:
            from app.core import db
            n_projects = len(db.list_projects())
            counts = db.count_library_by_status()
            total = sum(counts.values())
            processing = counts.get("queued", 0) + counts.get(
                "downloading", 0)
            done = counts.get("done", 0)
        except Exception:
            n_projects, total, processing, done = 0, 0, 0, 0
        self._set_stat("projects", str(n_projects))
        self._set_stat("total", str(total))
        self._set_stat("processing", str(processing))
        self._set_stat("done", str(done))

    def _goto_brief(self, tab: int) -> None:
        if self._nav:
            self._nav(1, tab)

    def _goto(self, index: int) -> None:
        if self._nav:
            self._nav(index)
