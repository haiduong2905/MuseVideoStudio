"""Dialog quản lý tài khoản: mỗi nền tảng có thể có nhiều tài khoản.

VD: 2 kênh YouTube (Serene, BeastBytes), 2 Page Facebook...
Mỗi tài khoản gắn với 1 account_id; token lưu riêng trong keyring.

Lưu ý luồng: kết nối YouTube/TikTok phải chờ user xác thực trên trình duyệt
(có thể vài phút) nên CHẠY TRÊN QThread riêng (_ConnectWorker) + dialog chờ
có nút Hủy. Gọi trực tiếp trên luồng giao diện sẽ treo app "Not Responding".
Facebook chỉ nhập Page ID/token qua form nên chạy thẳng trên GUI.
"""
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QDialog, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from app.core import db
from app.platforms import PLATFORM_LABELS, PLATFORM_ORDER, get_platform


class _ConnectWorker(QThread):
    """Chạy plat.connect() trên luồng nền. Xong bắn signal về GUI."""
    done = Signal(bool, str, str)  # ok, error, remote_name

    def __init__(self, plat, plat_name: str, parent=None) -> None:
        super().__init__(parent)
        self._plat = plat
        self._plat_name = plat_name
        self.cancel_event = threading.Event()

    def run(self) -> None:
        ok, err, name = False, "", ""
        try:
            ok = self._plat.connect(cancel_event=self.cancel_event)
            err = self._plat.last_error or ""
            if ok:
                name = self._fetch_remote_name() or ""
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
        self.done.emit(ok, err, name)

    def _fetch_remote_name(self) -> str | None:
        """Lấy tên kênh thật sau khi connect (best-effort, YouTube)."""
        try:
            if self._plat_name == "youtube":
                from googleapiclient.discovery import build
                creds = self._plat._get_credentials()
                if not creds:
                    return None
                import httplib2
                try:
                    from google_auth_httplib2 import AuthorizedHttp
                    authed = AuthorizedHttp(
                        creds, http=httplib2.Http(timeout=60))
                    yt = build("youtube", "v3", http=authed)
                except ImportError:
                    yt = build("youtube", "v3", credentials=creds)
                resp = yt.channels().list(
                    part="snippet", mine=True).execute()
                items = resp.get("items") or []
                if items:
                    return items[0]["snippet"]["title"]
        except Exception:  # noqa: BLE001
            pass
        return None


class _WaitingDialog(QDialog):
    """Dialog chờ xác thực: MODELESS để app không bị 'đơ'.

    Có nút Hủy và nút mở lại trình duyệt (phòng khi browser không hiện).
    """

    def __init__(self, parent, plat_label: str,
                 cancel_event: threading.Event,
                 reopen_callback) -> None:
        super().__init__(parent)
        self.setWindowTitle("Đang kết nối…")
        # Bỏ nút X: muốn dừng thì bấm Hủy để worker dọn dẹp đúng cách
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setModal(False)
        self._event = cancel_event
        self._reopen = reopen_callback
        lay = QVBoxLayout(self)
        info = QLabel(
            f"Đã mở trình duyệt — hãy đăng nhập và bấm <b>Cho phép</b> "
            f"cho {plat_label}.<br>Xong thì quay lại đây, app sẽ tự nhận tiếp."
            f"<br><br>Trong lúc chờ, anh vẫn dùng app bình thường.")
        info.setWordWrap(True)
        lay.addWidget(info)
        row = QHBoxLayout()
        self.reopen_btn = QPushButton("🌐 Mở lại trình duyệt")
        self.reopen_btn.clicked.connect(self._on_reopen)
        row.addWidget(self.reopen_btn)
        self.cancel_btn = QPushButton("Hủy kết nối")
        self.cancel_btn.clicked.connect(self._on_cancel)
        row.addWidget(self.cancel_btn)
        lay.addLayout(row)

    def _on_reopen(self) -> None:
        try:
            self._reopen()
        except Exception:
            pass

    def _on_cancel(self) -> None:
        self._event.set()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Đang hủy…")
        self.reopen_btn.setEnabled(False)


class AccountsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tài khoản")
        self.setMinimumSize(520, 480)
        self._connecting: set[int] = set()  # account_id đang kết nối dở

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.body_lay = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        hint = QLabel("Mỗi nền tảng có thể thêm nhiều tài khoản "
                      "(VD: 2 kênh YouTube). Vào Cài đặt nhập Client ID/Secret "
                      "trước khi kết nối YouTube / TikTok.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        outer.addWidget(hint)

        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn)

        self._refresh()

    # -- dựng UI ----------------------------------------------------------
    def _clear(self) -> None:
        while self.body_lay.count():
            item = self.body_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _refresh(self) -> None:
        self._clear()
        for plat_name in PLATFORM_ORDER:
            group = QGroupBox(PLATFORM_LABELS[plat_name])
            lay = QVBoxLayout(group)
            accounts = db.list_accounts(plat_name)
            if not accounts:
                lay.addWidget(QLabel("Chưa có tài khoản nào."))
            for acc in accounts:
                lay.addWidget(self._account_row(plat_name, acc))
            add_btn = QPushButton(f"➕ Thêm tài khoản "
                                  f"{PLATFORM_LABELS[plat_name]}")
            add_btn.clicked.connect(
                lambda _=False, p=plat_name: self._add_account(p))
            lay.addWidget(add_btn)
            self.body_lay.addWidget(group)
        self.body_lay.addStretch(1)

    def _account_row(self, plat_name: str, acc: dict) -> QWidget:
        box = QWidget()
        vlay = QVBoxLayout(box)
        vlay.setContentsMargins(0, 4, 0, 4)
        vlay.setSpacing(4)
        row = QHBoxLayout()
        name_lbl = QLabel(f"<b>{acc['label']}</b>")
        name_lbl.setMinimumWidth(140)
        status_lbl = QLabel()
        plat = get_platform(plat_name, acc["id"])
        try:
            connected = plat.is_connected()
        except Exception:  # noqa: BLE001
            connected = False
        if acc["id"] in self._connecting:
            status_lbl.setText("⏳ Đang kết nối…")
            status_lbl.setStyleSheet("color: #b45309;")
            conn_btn = QPushButton("Đang kết nối…")
            conn_btn.setEnabled(False)
        elif connected:
            status_lbl.setText("✅ Đã kết nối")
            status_lbl.setStyleSheet("color: green;")
            conn_btn = QPushButton("Ngắt")
            conn_btn.clicked.connect(
                lambda _=False, p=plat_name, a=acc["id"], c=connected:
                self._toggle(p, a, c))
        elif (acc.get("status") or "active") == "disconnected":
            status_lbl.setText("⏸ Đã ngắt (giữ thông tin)")
            status_lbl.setStyleSheet("color: #b45309;")
            conn_btn = QPushButton("Kết nối")
            conn_btn.clicked.connect(
                lambda _=False, p=plat_name, a=acc["id"], c=connected:
                self._toggle(p, a, c))
        else:
            status_lbl.setText("⚪ Chưa kết nối")
            status_lbl.setStyleSheet("color: gray;")
            conn_btn = QPushButton("Kết nối")
            conn_btn.clicked.connect(
                lambda _=False, p=plat_name, a=acc["id"], c=connected:
                self._toggle(p, a, c))
        edit_btn = QPushButton("✏️")
        edit_btn.setToolTip("Sửa tên / ID / token")
        edit_btn.setMaximumWidth(36)
        edit_btn.clicked.connect(
            lambda _=False, p=plat_name, a=acc["id"], lbl=acc["label"]:
            self._edit_account(p, a, lbl))
        del_btn = QPushButton("🗑")
        del_btn.setToolTip("Xóa hẳn tài khoản khỏi máy")
        del_btn.setMaximumWidth(36)
        del_btn.clicked.connect(
            lambda _=False, p=plat_name, a=acc["id"], lbl=acc["label"]:
            self._delete(p, a, lbl))
        row.addWidget(name_lbl)
        row.addWidget(status_lbl, 1)
        row.addWidget(conn_btn)
        row.addWidget(edit_btn)
        row.addWidget(del_btn)
        vlay.addLayout(row)
        # Facebook: luôn hiện Page ID + token để đối chiếu với dev portal
        if plat_name == "facebook":
            try:
                creds = plat._get_creds()
            except Exception:  # noqa: BLE001
                creds = None
            det = QHBoxLayout()
            det.setContentsMargins(150, 0, 0, 0)
            id_lbl = QLabel("Page ID:")
            id_lbl.setStyleSheet("color: gray; font-size: 12px;")
            det.addWidget(id_lbl)
            self._ro_field(det, creds[0] if creds else "")
            tok_lbl = QLabel("Token:")
            tok_lbl.setStyleSheet("color: gray; font-size: 12px;")
            det.addWidget(tok_lbl)
            tok_field = self._ro_field(det, creds[1] if creds else "", 2)
            copy_btn = QPushButton("📋")
            copy_btn.setToolTip("Copy token")
            copy_btn.setMaximumWidth(36)
            copy_btn.clicked.connect(
                lambda _=False, f=tok_field: self._copy_token(f))
            det.addWidget(copy_btn)
            vlay.addLayout(det)
        return box

    @staticmethod
    def _ro_field(layout, text: str, stretch: int = 1):
        """Ô chỉ đọc để hiển thị ID/token (bôi đen copy được)."""
        from PySide6.QtWidgets import QLineEdit
        field = QLineEdit(text or "—")
        field.setReadOnly(True)
        field.setStyleSheet("font-size: 12px; color: #4b5563;")
        layout.addWidget(field, stretch)
        return field

    def _copy_token(self, field) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(field.text())
        QMessageBox.information(self, "Đã copy",
                                "Đã copy token vào clipboard.")

    def _edit_account(self, plat_name: str, account_id: int,
                      label: str) -> None:
        """Sửa tên / Page ID / token của tài khoản đã lưu."""
        from PySide6.QtWidgets import (QDialogButtonBox, QFormLayout,
                                       QLineEdit)
        plat = get_platform(plat_name, account_id)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sửa tài khoản {PLATFORM_LABELS[plat_name]}")
        dlg.setMinimumWidth(420)
        form = QFormLayout()
        name_edit = QLineEdit(label)
        form.addRow("Tên gợi nhớ:", name_edit)
        page_edit = tok_edit = None
        if plat_name == "facebook":
            try:
                creds = plat._get_creds()
            except Exception:  # noqa: BLE001
                creds = None
            page_edit = QLineEdit(creds[0] if creds else "")
            tok_edit = QLineEdit(creds[1] if creds else "")
            form.addRow("Page ID:", page_edit)
            form.addRow("Access token:", tok_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        btns.button(QDialogButtonBox.StandardButton.Save).setProperty(
            "primary", True)
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay = QVBoxLayout(dlg)
        lay.addLayout(form)
        lay.addWidget(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_label = name_edit.text().strip()
        if new_label and new_label != label:
            db.update_account(account_id, label=new_label)
        if plat_name == "facebook" and page_edit is not None:
            from app.core import secrets as secrets_mod
            secrets_mod.set_secret(plat._page_id_key(),
                                   page_edit.text().strip())
            secrets_mod.set_secret(plat._token_key(),
                                   tok_edit.text().strip())
            QMessageBox.information(
                self, "Đã lưu",
                "Đã lưu Page ID/token. Bấm “Kết nối” để kiểm tra lại.")
        self._refresh()

    # -- thao tác ---------------------------------------------------------
    def _connect_async(self, plat_name: str, account_id: int,
                       on_done) -> None:
        """Kết nối YouTube/TikTok trên luồng nền + dialog chờ MODELESS.

        Dialog chờ không khóa app; nút 'Mở lại trình duyệt' phòng khi
        browser không hiện. Chặn bấm kết nối trùng trong lúc đang chạy.
        """
        import webbrowser

        if account_id in self._connecting:
            return
        plat = get_platform(plat_name, account_id)
        worker = _ConnectWorker(plat, plat_name, self)

        def _reopen_browser() -> None:
            url = getattr(plat, "last_auth_url", "") or ""
            if url:
                webbrowser.open(url, new=1, autoraise=True)

        dlg = _WaitingDialog(self, PLATFORM_LABELS[plat_name],
                             worker.cancel_event, _reopen_browser)
        self._connecting.add(account_id)

        def _finished(ok: bool, err: str, name: str) -> None:
            self._connecting.discard(account_id)
            try:
                dlg.close()
            except RuntimeError:
                pass  # dialog đã bị đóng trước đó
            try:
                on_done(ok, err, name)
            finally:
                worker.deleteLater()

        worker.done.connect(_finished)
        worker.start()
        dlg.show()
        self._refresh()  # hiện trạng thái "đang kết nối" trên nút

    def _finish_connect(self, plat_name: str, account_id: int,
                        ok: bool, err: str, name: str,
                        delete_on_fail: bool) -> None:
        if ok:
            if name:
                db.update_account(account_id, label=name)
            QMessageBox.information(
                self, "Thành công",
                f"Đã kết nối tài khoản {PLATFORM_LABELS[plat_name]}.")
        else:
            if delete_on_fail:
                db.delete_account_by_id(account_id)
            QMessageBox.warning(
                self, "Chưa kết nối",
                (err or "Kết nối thất bại, thử lại sau.")
                + "\n\nTài khoản vẫn được giữ lại — bấm “Kết nối” "
                  "để thử lại mà không cần nhập lại tên.")
        self._refresh()

    def _add_account(self, plat_name: str) -> None:
        label, ok = QInputDialog.getText(
            self, "Thêm tài khoản",
            f"Tên gợi nhớ cho tài khoản {PLATFORM_LABELS[plat_name]}:\n"
            f"VD: Kênh Serene, Page BeastBytes…")
        if not ok:
            return
        label = label.strip() or PLATFORM_LABELS[plat_name]
        try:
            account_id = db.add_account(plat_name, label)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi",
                                 f"Không tạo được tài khoản: {exc}")
            return
        if plat_name == "facebook":
            # Facebook chỉ nhập Page ID/token qua form -> chạy thẳng trên GUI
            plat = get_platform(plat_name, account_id)
            try:
                ok_conn = plat.connect(self)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Lỗi",
                                    f"Kết nối thất bại: {exc}\n"
                                    f"Tài khoản vẫn được giữ lại — bấm "
                                    f"“Kết nối” để thử lại mà không cần "
                                    f"nhập lại tên.")
                self._refresh()
                return
            self._finish_connect(plat_name, account_id, ok_conn,
                                 plat.last_error or "", "",
                                 delete_on_fail=False)
            return
        self._connect_async(
            plat_name, account_id,
            lambda ok, err, name: self._finish_connect(
                plat_name, account_id, ok, err, name, delete_on_fail=False))

    def _toggle(self, plat_name: str, account_id: int,
                connected: bool) -> None:
        if connected:
            ok = QMessageBox.question(
                self, "Ngắt kết nối",
                "Ngắt kết nối tài khoản này?\n\n"
                "Tên, Page ID và token vẫn được GIỮ LẠI — bấm “Kết nối” "
                "để dùng tiếp mà không cần nhập lại.")
            if ok == QMessageBox.StandardButton.Yes:
                try:
                    get_platform(plat_name, account_id).disconnect()
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.warning(self, "Lỗi",
                                        f"Không ngắt được: {exc}")
            self._refresh()
            return
        # --- kết nối lại ---
        if plat_name == "facebook":
            plat = get_platform(plat_name, account_id)
            try:
                ok_conn = plat.connect(self)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Lỗi",
                                    f"Kết nối thất bại: {exc}")
                self._refresh()
                return
            self._finish_connect(plat_name, account_id, ok_conn,
                                 plat.last_error or "", "",
                                 delete_on_fail=False)
            return
        self._connect_async(
            plat_name, account_id,
            lambda ok, err, name: self._finish_connect(
                plat_name, account_id, ok, err, name, delete_on_fail=False))

    def _delete(self, plat_name: str, account_id: int, label: str) -> None:
        ok = QMessageBox.question(
            self, "Xóa tài khoản",
            f'Xóa HẲN tài khoản "{label}" ({PLATFORM_LABELS[plat_name]})?\n'
            "Tên, ID và token sẽ bị xóa khỏi máy. Video đã lên lịch dùng "
            "tài khoản này sẽ không đăng được nữa.")
        if ok != QMessageBox.StandardButton.Yes:
            return
        try:
            get_platform(plat_name, account_id).purge()
        except Exception:  # noqa: BLE001
            db.delete_account_by_id(account_id)
        self._refresh()
