"""Dialog chi tiết 1 video: trạng thái trên từng nền tảng.

- Bảng: nền tảng | trạng thái | ID bài đăng (+ nút Mở link) | lỗi | cập nhật.
- TikTok đang ở nháp: nút "Đánh dấu đã đăng" sau khi đăng tay trong app.
"""
import os
from datetime import datetime

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QHBoxLayout)

from app.core import db

PLATFORM_LABELS = {"youtube": "YouTube", "facebook": "Facebook",
                   "tiktok": "TikTok"}
STATUS_TEXT = {
    "pending": "⏳ Chờ",
    "uploading": "⬆️ Đang đăng…",
    "scheduled": "🗓 Đã lên lịch",
    "published": "✅ Đã đăng",
    "draft": "📝 Nháp (chờ đăng tay)",
    "failed": "❌ Lỗi",
}
STATUS_COLORS = {
    "pending": "#8a8a8a",
    "uploading": "#1a73e8",
    "scheduled": "#e8710a",
    "published": "#188038",
    "draft": "#b06000",
    "failed": "#d93025",
}


def platform_url(platform: str, remote_id: str, status: str) -> str:
    if not remote_id:
        return ""
    if platform == "youtube":
        if status == "published":
            return f"https://www.youtube.com/watch?v={remote_id}"
        return f"https://studio.youtube.com/video/{remote_id}/edit"
    if platform == "facebook":
        return f"https://www.facebook.com/reel/{remote_id}"
    return ""  # tiktok draft: mở app TikTok -> Hộp thư


class DetailDialog(QDialog):
    def __init__(self, parent, queue_id: int) -> None:
        super().__init__(parent)
        self.queue_id = queue_id
        self.setWindowTitle("Chi tiết video")
        self.resize(640, 420)

        item = db.get_queue(queue_id) or {}
        is_post = (item.get("content_type") or "video") == "post"
        self.setWindowTitle("Chi tiết bài viết" if is_post
                            else "Chi tiết video")
        title = QLabel(f"<b>{item.get('title') or ''}</b>")
        title.setWordWrap(True)
        if not is_post:
            file_lbl = QLabel(os.path.basename(item.get("file_path") or ""))
            file_lbl.setStyleSheet("color: gray;")
        try:
            dt = datetime.fromisoformat(item.get("scheduled_at") or "")
            sched = dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            sched = item.get("scheduled_at") or ""

        info = QFormLayout()
        info.addRow("Lịch đăng:", QLabel(sched))
        if is_post:
            body = QLabel((item.get("description") or "")[:500])
            body.setWordWrap(True)
            info.addRow("Nội dung:", body)
            try:
                import json as json_lib
                imgs = json_lib.loads(item.get("image_paths") or "[]")
            except (ValueError, TypeError):
                imgs = []
            if imgs:
                info.addRow("Số ảnh:", QLabel(str(len(imgs))))
        else:
            info.addRow("File:", file_lbl)
        thumb_path = item.get("thumbnail_path") or ""
        if thumb_path and os.path.isfile(thumb_path):
            pm = QPixmap(thumb_path).scaled(
                160, 90, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            thumb_lbl = QLabel()
            thumb_lbl.setPixmap(pm)
            info.addRow("Ảnh bìa:", thumb_lbl)

        # -- bảng trạng thái từng nền tảng --
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Nền tảng", "Tài khoản", "Trạng thái", "ID bài đăng", "",
             "Cập nhật lúc"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            self.table.EditTrigger.NoEditTriggers)
        self._refresh_table()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Close).setText("Đóng")
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(title)
        lay.addLayout(info)
        lay.addWidget(QLabel("<b>Trạng thái từng nền tảng:</b>"))
        lay.addWidget(self.table, 1)
        lay.addWidget(btns)

    def _refresh_table(self) -> None:
        targets = []
        for it in db.list_queue():
            if it["id"] == self.queue_id:
                targets = list((it.get("targets") or {}).values())
                break
        self.table.setRowCount(len(targets))
        for r, t in enumerate(targets):
            plat = t["platform"]
            status = t.get("status") or "pending"
            self.table.setItem(r, 0, QTableWidgetItem(
                PLATFORM_LABELS.get(plat, plat)))
            self.table.setItem(r, 1, QTableWidgetItem(
                t.get("account_label") or "—"))
            st_item = QTableWidgetItem(STATUS_TEXT.get(status, status))
            color = STATUS_COLORS.get(status)
            if color:
                st_item.setForeground(QColor(color))
            self.table.setItem(r, 2, st_item)
            self.table.setItem(r, 3, QTableWidgetItem(
                t.get("remote_id") or "—"))
            # nút Mở / Đánh dấu đã đăng
            cell_w = _cell_widget()
            url = platform_url(plat, t.get("remote_id") or "", status)
            if url:
                open_btn = QPushButton("🔗 Mở")
                open_btn.clicked.connect(
                    lambda _=None, u=url: QDesktopServices.openUrl(QUrl(u)))
                cell_w.layout().addWidget(open_btn)
            if plat == "tiktok" and status == "draft":
                done_btn = QPushButton("✅ Đã đăng")
                done_btn.setToolTip("Bấm sau khi anh đã đăng tay trong "
                                    "app TikTok")
                done_btn.clicked.connect(
                    lambda _=None, tid=t["id"]: self._mark_posted(tid))
                cell_w.layout().addWidget(done_btn)
            if not cell_w.layout().count():
                cell_w.layout().addWidget(QLabel("—"))
            self.table.setCellWidget(r, 4, cell_w)
            try:
                dt = datetime.fromisoformat(t.get("updated_at") or "")
                upd = dt.strftime("%d/%m %H:%M")
            except ValueError:
                upd = t.get("updated_at") or ""
            self.table.setItem(r, 5, QTableWidgetItem(upd))
            if t.get("error"):
                self.table.setItem(r, 3, QTableWidgetItem(
                    f"Lỗi: {t['error'][:80]}"))
        self.table.resizeColumnsToContents()

    def _mark_posted(self, target_id: int) -> None:
        db.update_target(target_id, status="published", reminded=1,
                         next_reminder_at=None, error=None)
        item = db.get_queue(self.queue_id) or {}
        db.add_log(self.queue_id, "tiktok", "info",
                   f"User xác nhận đã đăng tay TikTok: "
                   f"{item.get('title') or ''}.")
        self._refresh_table()


def _cell_widget():
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    w.setLayout(QHBoxLayout())
    w.layout().setContentsMargins(2, 2, 2, 2)
    return w
