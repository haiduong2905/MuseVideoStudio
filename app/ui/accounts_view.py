"""Màn 6 — Quản lý tài khoản mạng xã hội (dùng platforms/ kế thừa)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from app.core import db
from app.platforms import get_platform
from app.ui.accounts_dialog import AccountsDialog
from app.ui.widgets import (card, chip, dim_label, ghost_button,
                            primary_button, section_label, subtitle_label,
                            title_label)

PLATFORM_NAMES = {
    "tiktok": "TikTok",
    "facebook": "Facebook Page",
    "youtube": "YouTube Channel",
}


class AccountsView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(title_label("Quản lý tài khoản mạng xã hội"))
        root.addWidget(subtitle_label(
            "Kết nối và quản lý tài khoản TikTok, Facebook, YouTube"))

        self.box = card()
        self.box_lay = QVBoxLayout(self.box)
        self.box_lay.setContentsMargins(16, 16, 16, 16)
        self.box_lay.setSpacing(4)
        self.box_lay.addWidget(section_label("Danh sách tài khoản liên kết"))
        self.list_lay = QVBoxLayout()
        self.list_lay.setSpacing(0)
        self.box_lay.addLayout(self.list_lay)
        add_btn = primary_button("＋ Kết nối tài khoản khác")
        add_btn.clicked.connect(self._on_add)
        self.box_lay.addWidget(add_btn,
                               alignment=Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.box)
        root.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        accs = db.list_accounts()
        if not accs:
            self.list_lay.addWidget(dim_label(
                "Chưa có tài khoản nào được kết nối."))
            return
        for acc in accs:
            self.list_lay.addWidget(self._row(acc))

    def _row(self, acc: dict) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(4, 10, 4, 10)
        name = QVBoxLayout()
        plat = PLATFORM_NAMES.get(acc.get("platform") or "",
                                  acc.get("platform") or "")
        name.addWidget(QLabel(f"<b>{plat}</b>"))
        name.addWidget(dim_label(acc.get("label") or ""))
        row.addLayout(name)
        row.addStretch(1)
        active = (acc.get("status") or "active") == "active"
        row.addWidget(chip("Đã kết nối" if active else "Đã ngắt",
                           "green" if active else "gray"))
        dis = ghost_button("Ngắt kết nối")
        dis.clicked.connect(lambda _=False, a=acc: self._on_disconnect(a))
        row.addWidget(dis)
        return w

    def _on_add(self) -> None:
        AccountsDialog(self).exec()
        self.refresh()

    def _on_disconnect(self, acc: dict) -> None:
        plat = acc.get("platform") or ""
        ok = QMessageBox.question(
            self, "Ngắt kết nối",
            f"Ngắt kết nối tài khoản "
            f"'{acc.get('label') or plat}'?\n\n"
            "Video đã lên lịch của tài khoản này sẽ không đăng được "
            "cho tới khi kết nối lại.")
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            get_platform(plat, acc.get("id")).disconnect()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Lưu ý",
                                f"Ngắt phía nền tảng lỗi: {exc}\n"
                                "Vẫn xóa thông tin kết nối trong app.")
        db.delete_account_by_id(acc.get("id"))
        self.refresh()
