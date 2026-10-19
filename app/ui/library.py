"""Màn 4 — Hàng đợi xử lý và thư viện video (mailbox Plan B).

Render từ bảng library. MailboxWorker (tạo ở main_window) phát signal
khi video bắt đầu/xong/lỗi -> view refresh.
"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QScrollArea, QStackedWidget, QTabBar,
                               QVBoxLayout, QWidget)

from app.core import db
from app.ui.widgets import (card, card2, chip, dim_label, ghost_button,
                            subtitle_label, title_label)

STATUS_META = {
    "queued": ("Đang chờ", "amber"),
    "downloading": ("Đang xử lý", "blue"),
    "done": ("Đã hoàn thành", "green"),
    "failed": ("Đã thất bại", "red"),
    "paused": ("Tạm dừng", "gray"),
}
# tab -> các status gom vào
TAB_FILTERS = [
    ("Hàng đợi", ["queued", "downloading", "paused"]),
    ("Đã hoàn thành", ["done"]),
    ("Đã thất bại", ["failed"]),
]


class LibraryView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._worker = None
        self._rows: dict[str, QWidget] = {}  # manifest_id -> card

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(title_label("Hàng đợi xử lý và thư viện video"))
        root.addWidget(subtitle_label(
            "Theo dõi tiến độ, xem trước, tải video, quản lý file"))

        bar = QHBoxLayout()
        self.tabbar = QTabBar()
        self.pages = QStackedWidget()
        self._page_layouts: list = []
        for name, _statuses in TAB_FILTERS:
            self.tabbar.addTab(name)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(0, 8, 0, 0)
            lay.setSpacing(12)
            lay.addStretch(1)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
            self._page_layouts.append(lay)
        self.tabbar.currentChanged.connect(self.pages.setCurrentIndex)
        bar.addWidget(self.tabbar)
        bar.addStretch(1)
        check_btn = ghost_button("🔄 Kiểm tra ngay")
        check_btn.clicked.connect(self._on_check_now)
        bar.addWidget(check_btn)
        pause_btn = ghost_button("⏸ Tạm dừng tất cả")
        pause_btn.clicked.connect(self._on_pause_all)
        bar.addWidget(pause_btn)
        clear_btn = ghost_button("🗑 Xóa hoàn thành")
        clear_btn.clicked.connect(self._on_clear_done)
        bar.addWidget(clear_btn)
        root.addLayout(bar)
        root.addWidget(self.pages, 1)
        self.refresh()

    # -- worker --
    def set_worker(self, worker) -> None:
        self._worker = worker
        worker.video_started.connect(lambda _mid: self.refresh())
        worker.video_progress.connect(self._on_progress)
        worker.video_done.connect(lambda _m, _p: self.refresh())
        worker.video_failed.connect(lambda _m, _e: self.refresh())
        worker.poll_finished.connect(lambda _n: self.refresh())

    def _on_check_now(self) -> None:
        if self._worker:
            self._worker.request_poll()
            QMessageBox.information(self, "Đang kiểm tra",
                                    "Đang kiểm tra manifest mailbox...")
        else:
            QMessageBox.information(
                self, "Chưa cấu hình",
                "Hãy nhập Manifest URL ở Cài đặt > Tự động đăng trước.")

    def _on_pause_all(self) -> None:
        for row in db.list_library("downloading"):
            db.update_library(row["id"], status="paused")
        if self._worker:
            self._worker.stop()
        self.refresh()

    def _on_clear_done(self) -> None:
        ok = QMessageBox.question(
            self, "Xóa hoàn thành",
            "Xóa các bản ghi đã hoàn thành khỏi thư viện?\n"
            "(File video trên máy không bị xóa.)")
        if ok != QMessageBox.StandardButton.Yes:
            return
        # chỉ ẩn khỏi tab hoàn thành (giữ file trên máy)
        for row in db.list_library("done"):
            db.update_library(row["id"], status="paused")
        self.refresh()

    # -- render --
    def refresh(self) -> None:
        counts = db.count_library_by_status()
        for i, (name, statuses) in enumerate(TAB_FILTERS):
            n = sum(counts.get(s, 0) for s in statuses)
            self.tabbar.setTabText(i, f"{name} ({n})")
        self._rows = {}
        for i, (_name, statuses) in enumerate(TAB_FILTERS):
            lay = self._page_layouts[i]
            # xóa card cũ
            while lay.count() > 1:
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            rows = []
            for s in statuses:
                rows.extend(db.list_library(s))
            if not rows:
                lay.insertWidget(0, dim_label("Chưa có video nào."))
            for r in rows:
                w = self._item(r)
                lay.insertWidget(lay.count() - 1, w)
                self._rows[r["manifest_id"]] = w

    def _on_progress(self, manifest_id: str, pct: int) -> None:
        w = self._rows.get(manifest_id)
        if w is None:
            return
        bar = w.findChild(QProgressBar)
        if bar:
            bar.setValue(pct)

    def _item(self, r: dict) -> QWidget:
        f = card()
        lay = QHBoxLayout(f)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        th = card2()
        th.setFixedSize(120, 68)
        thl = QVBoxLayout(th)
        thl.setContentsMargins(2, 2, 2, 2)
        thl.addWidget(dim_label("Ảnh"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(th)
        mid = QVBoxLayout()
        name = r.get("title") or r.get("manifest_id")
        proj = r.get("project_code")
        mid.addWidget(QLabel(
            f"<b>{name}</b>" + (f" <i>({proj})</i>" if proj else "")))
        row = QHBoxLayout()
        label, color = STATUS_META.get(r.get("status") or "queued",
                                       ("—", "gray"))
        row.addWidget(chip(label, color))
        row.addWidget(dim_label(
            f"{r.get('duration') or 10} giây · {r.get('ratio') or '9:16'}"))
        if r.get("error"):
            row.addWidget(dim_label(f"Lỗi: {r['error'][:80]}"))
        row.addStretch(1)
        mid.addLayout(row)
        if r.get("status") == "downloading":
            pb = QProgressBar()
            pb.setValue(r.get("progress") or 0)
            pb.setFormat(f"{r.get('progress') or 0}%")
            mid.addWidget(pb)
        lay.addLayout(mid, 1)
        view_btn = ghost_button("👁 Xem")
        view_btn.clicked.connect(
            lambda _=False, p=r.get("file_path"): self._on_view(p))
        lay.addWidget(view_btn)
        folder_btn = ghost_button("📁 Mở thư mục")
        folder_btn.clicked.connect(
            lambda _=False, p=r.get("file_path"): self._on_folder(p))
        lay.addWidget(folder_btn)
        return f

    def _on_view(self, path: str | None) -> None:
        if path and os.path.isfile(path):
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(self, "Chưa có file",
                                    "Video chưa được tải về máy.")

    def _on_folder(self, path: str | None) -> None:
        folder = os.path.dirname(path) if path else ""
        if folder and os.path.isdir(folder):
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.information(self, "Chưa có thư mục",
                                    "Thư mục chưa tồn tại.")
