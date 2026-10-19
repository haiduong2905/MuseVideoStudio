"""Dialog quản lý combo kênh.

Mỗi combo là 1 "kênh" gồm tài khoản của từng nền tảng, VD:
- Combo "Serene": YouTube=Kênh Serene, Facebook=Page Serene, ...
- Combo "BeastBytes": YouTube=Kênh BeastBytes, ...

Khi thêm video, chọn combo -> video được đăng lên đúng các tài khoản
trong combo đó.
"""
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QListWidget,
                               QMessageBox, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from app.core import db
from app.platforms import PLATFORM_LABELS, PLATFORM_ORDER


class CombosDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Combo kênh")
        self.setMinimumSize(560, 420)
        self._current_id: int | None = None
        self._boxes: dict[str, QComboBox] = {}

        splitter = QSplitter()

        # -- trái: danh sách combo --
        left = QWidget()
        left_lay = QVBoxLayout(left)
        self.list_w = QListWidget()
        self.list_w.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self.list_w)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Thêm")
        add_btn.clicked.connect(self._add)
        rename_btn = QPushButton("✏️ Đổi tên")
        rename_btn.clicked.connect(self._rename)
        del_btn = QPushButton("🗑 Xóa")
        del_btn.clicked.connect(self._delete)
        for b in (add_btn, rename_btn, del_btn):
            btn_row.addWidget(b)
        left_lay.addLayout(btn_row)
        splitter.addWidget(left)

        # -- phải: chọn tài khoản từng nền tảng --
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.addWidget(QLabel("<b>Tài khoản trong combo:</b>"))
        form = QFormLayout()
        for plat in PLATFORM_ORDER:
            box = QComboBox()
            box.setMinimumWidth(220)
            self._boxes[plat] = box
            form.addRow(PLATFORM_LABELS[plat] + ":", box)
        right_lay.addLayout(form)
        right_lay.addStretch(1)
        hint = QLabel("Chọn tài khoản cho từng nền tảng.\n"
                      "Để '— Không dùng —' nếu combo này không đăng "
                      "lên nền tảng đó.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        right_lay.addWidget(hint)
        save_btn = QPushButton("💾 Lưu combo")
        save_btn.clicked.connect(self._save)
        right_lay.addWidget(save_btn)
        splitter.addWidget(right)
        splitter.setSizes([180, 380])

        outer = QVBoxLayout(self)
        outer.addWidget(splitter)
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn)

        self._reload_list()

    # -- danh sách combo --------------------------------------------------
    def _reload_list(self) -> None:
        self.list_w.clear()
        self._combos = db.list_combos()
        for c in self._combos:
            self.list_w.addItem(c["name"])
        if self._combos:
            self.list_w.setCurrentRow(0)

    def _selected(self) -> dict | None:
        row = self.list_w.currentRow()
        if 0 <= row < len(self._combos):
            return self._combos[row]
        return None

    def _on_select(self, row: int) -> None:
        combo = self._selected()
        self._current_id = combo["id"] if combo else None
        members = combo["members"] if combo else {}
        for plat in PLATFORM_ORDER:
            box = self._boxes[plat]
            box.clear()
            box.addItem("— Không dùng —", None)
            for acc in db.list_accounts(plat):
                box.addItem(acc["label"], acc["id"])
            cur = members.get(plat)
            if cur:
                idx = box.findData(cur["id"])
                if idx >= 0:
                    box.setCurrentIndex(idx)

    # -- CRUD -------------------------------------------------------------
    def _add(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Thêm combo",
            "Tên combo (VD: Serene, BeastBytes):")
        if not ok or not name.strip():
            return
        try:
            db.create_combo(name.strip())
        except ValueError as exc:
            QMessageBox.warning(self, "Lỗi", str(exc))
            return
        self._reload_list()
        # chọn combo vừa tạo
        for i, c in enumerate(self._combos):
            if c["name"] == name.strip():
                self.list_w.setCurrentRow(i)
                break

    def _rename(self) -> None:
        combo = self._selected()
        if not combo:
            return
        name, ok = QInputDialog.getText(
            self, "Đổi tên combo", "Tên mới:", text=combo["name"])
        if not ok or not name.strip():
            return
        try:
            db.rename_combo(combo["id"], name.strip())
        except ValueError as exc:
            QMessageBox.warning(self, "Lỗi", str(exc))
            return
        self._reload_list()

    def _delete(self) -> None:
        combo = self._selected()
        if not combo:
            return
        ok = QMessageBox.question(
            self, "Xóa combo",
            f'Xóa combo "{combo["name"]}"?\n'
            "Video đã gán combo này vẫn giữ nguyên, "
            "chỉ không còn gán combo nữa.")
        if ok != QMessageBox.StandardButton.Yes:
            return
        db.delete_combo(combo["id"])
        self._reload_list()

    def _save(self) -> None:
        if not self._current_id:
            QMessageBox.information(self, "Chưa chọn",
                                    "Hãy chọn 1 combo bên trái trước.")
            return
        members = {plat: self._boxes[plat].currentData()
                   for plat in PLATFORM_ORDER}
        if not any(members.values()):
            QMessageBox.warning(self, "Trống",
                                "Combo phải có ít nhất 1 tài khoản.")
            return
        db.set_combo_members(self._current_id, members)
        self._reload_list()
        QMessageBox.information(self, "Đã lưu",
                                "Đã lưu tài khoản cho combo.")
