"""QueueModel: model lọc/hiển thị hàng đợi đăng (tách từ main_window cũ).

Dùng ở màn "Lịch đăng" (tab Hàng đợi đăng). Không phụ thuộc theme.
"""
import os
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from app.core import db
from app.platforms import PLATFORM_LABELS, PLATFORM_ORDER

STATUS_TEXT = {
    "pending": "Chờ",
    "uploading": "Đang đăng…",
    "scheduled": "Đã lên lịch",
    "published": "Đã đăng",
    "draft": "Nháp",
    "failed": "Lỗi",
}
COLUMNS = ["File", "Tiêu đề", "Lịch đăng",
           "YouTube", "Facebook", "TikTok", "Combo", "Lỗi / Ghi chú"]


def _fmt_dt(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return iso or ""


class QueueModel(QAbstractTableModel):
    # Bộ lọc trạng thái: key -> label hiển thị
    FILTERS = [
        ("all", "Tất cả"),
        ("failed", "Có lỗi"),
        ("pending", "Đang chờ"),
        ("uploading", "Đang đăng"),
        ("done", "Đã xong"),
    ]
    DONE_STATUSES = {"scheduled", "published", "draft"}

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict] = []
        self.status_filter = "all"

    def refresh(self) -> None:
        self.beginResetModel()
        try:
            items = db.list_queue()
            if self.status_filter != "all":
                items = [i for i in items
                         if self._match_filter(i, self.status_filter)]
            self.items = items
        finally:
            self.endResetModel()

    @classmethod
    def _target_statuses(cls, item: dict) -> set:
        return {t.get("status")
                for t in (item.get("targets") or {}).values()
                if t.get("enabled")}

    @classmethod
    def _match_filter(cls, item: dict, key: str) -> bool:
        st = cls._target_statuses(item)
        if key == "failed":
            return "failed" in st
        if key == "pending":
            return "pending" in st
        if key == "uploading":
            return "uploading" in st
        if key == "done":
            return bool(st) and st <= cls.DONE_STATUSES
        return True

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == \
                Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def _cell(self, item: dict, col: int) -> str:
        is_post = (item.get("content_type") or "video") == "post"
        if col == 0:
            if is_post:
                try:
                    import json as json_lib
                    n = len(json_lib.loads(item.get("image_paths")
                                           or "[]"))
                except (ValueError, TypeError):
                    n = 0
                return f"Bài viết ({n} ảnh)" if n else "Bài viết"
            return os.path.basename(item.get("file_path") or "")
        if col == 1:
            return item.get("title") or ""
        if col == 2:
            return _fmt_dt(item.get("scheduled_at") or "")
        if col in (3, 4, 5):
            platform = PLATFORM_ORDER[col - 3]
            target = (item.get("targets") or {}).get(platform)
            if not target or not target.get("enabled"):
                return "—"
            return STATUS_TEXT.get(target.get("status"), "?")
        if col == 6:
            return item.get("combo_name") or "—"
        errs = []
        for p in PLATFORM_ORDER:
            target = (item.get("targets") or {}).get(p)
            if not target or not target.get("enabled"):
                continue
            if target.get("error"):
                errs.append(f"{PLATFORM_LABELS[p]}: {target['error']}")
            elif target.get("status") == "pending" and not \
                    db.account_is_active(target.get("account_id")):
                errs.append(f"{PLATFORM_LABELS[p]}: "
                            "tài khoản đã ngắt kết nối")
        if errs:
            return " | ".join(errs)
        return item.get("note") or ""

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return self._cell(self.items[index.row()], index.column())
