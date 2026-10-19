"""Dialog Cài đặt: credentials API + tự khởi động cùng Windows."""
import json

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QLabel,
                               QLineEdit, QMessageBox, QVBoxLayout)

from app.core import autostart, db, secrets


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt")
        self.setMinimumWidth(480)

        self.yt_id = QLineEdit()
        self.yt_secret = QLineEdit()
        self.yt_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.fb_page_id = QLineEdit()
        self.fb_token = QLineEdit()
        self.fb_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.tt_key = QLineEdit()
        self.tt_secret = QLineEdit()
        self.tt_secret.setEchoMode(QLineEdit.EchoMode.Password)
        for w in (self.yt_secret, self.fb_token, self.tt_secret):
            w.setPlaceholderText("Để trống nếu không đổi")

        # nạp sẵn ID/key đã lưu (không nạp secret ra UI)
        try:
            yt = json.loads(secrets.get_secret("youtube_client") or "{}")
            self.yt_id.setText(yt.get("client_id", ""))
            tt = json.loads(secrets.get_secret("tiktok_client") or "{}")
            self.tt_key.setText(tt.get("client_key", ""))
        except (ValueError, TypeError):
            pass

        form = QFormLayout()
        form.addRow(QLabel("<b>YouTube</b> (Google Cloud Console → "
                           "OAuth client ID, loại Desktop)"))
        form.addRow("Client ID:", self.yt_id)
        form.addRow("Client secret:", self.yt_secret)
        form.addRow(QLabel("<b>Facebook</b> (Meta App → Page access token; "
                           "dùng cho tài khoản Facebook mặc định)"))
        form.addRow("Page ID:", self.fb_page_id)
        form.addRow("Page access token:", self.fb_token)
        form.addRow(QLabel("<b>TikTok</b> (TikTok Developers → Login Kit; "
                           "Redirect URI: http://localhost:8765/callback)"))
        form.addRow("Client key:", self.tt_key)
        form.addRow("Client secret:", self.tt_secret)

        from app.core import config as app_config

        self.autostart_cb = QCheckBox("Tự khởi động cùng Windows")
        self.autostart_cb.setChecked(autostart.is_autostart_enabled())
        if not autostart.is_windows():
            self.autostart_cb.setEnabled(False)
            self.autostart_cb.setText(
                "Tự khởi động cùng Windows (chỉ có trên Windows)")

        self.close_action_combo = QComboBox()
        self.close_action_combo.addItem("Hỏi mỗi lần bấm X", "ask")
        self.close_action_combo.addItem("Thu nhỏ xuống khay hệ thống",
                                        "minimize")
        self.close_action_combo.addItem("Thoát hẳn", "quit")
        cur = app_config.get("close_action", "ask")
        idx = self.close_action_combo.findData(cur)
        self.close_action_combo.setCurrentIndex(max(idx, 0))

        note = QLabel("Lưu ý: máy phải bật và app đang chạy thì video mới "
                      "đăng đúng giờ. Bật tự khởi động để không quên mở app.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.autostart_cb)
        close_row = QFormLayout()
        close_row.addRow("Khi bấm nút X:", self.close_action_combo)
        lay.addLayout(close_row)
        lay.addWidget(note)
        lay.addWidget(btns)

    def _on_save(self) -> None:
        yt_id = self.yt_id.text().strip()
        yt_secret = self.yt_secret.text().strip()
        fb_page_id = self.fb_page_id.text().strip()
        fb_token = self.fb_token.text().strip()
        tt_key = self.tt_key.text().strip()
        tt_secret = self.tt_secret.text().strip()

        try:
            if yt_id or yt_secret:
                if not (yt_id and yt_secret):
                    # cho phép chỉ đổi 1 phía nếu phía kia đã lưu
                    old = json.loads(
                        secrets.get_secret("youtube_client") or "{}")
                    yt_id = yt_id or old.get("client_id", "")
                    yt_secret = yt_secret or old.get("client_secret", "")
                if not (yt_id and yt_secret):
                    raise ValueError("Nhập đủ Client ID và Client secret "
                                     "của YouTube.")
                secrets.set_secret("youtube_client", json.dumps(
                    {"client_id": yt_id, "client_secret": yt_secret}))
            if fb_page_id or fb_token:
                if not (fb_page_id and fb_token):
                    raise ValueError("Nhập đủ Page ID và Page access token "
                                     "của Facebook.")
                # Lưu vào tài khoản Facebook đầu tiên (tạo mới nếu chưa có)
                from app.platforms import get_platform
                accs = db.list_accounts("facebook")
                account_id = accs[0]["id"] if accs else db.add_account(
                    "facebook", "Facebook")
                plat = get_platform("facebook", account_id)
                try:
                    page_name = plat.save_credentials(fb_page_id, fb_token)
                except ValueError as exc:
                    raise ValueError(f"Facebook: {exc}")
                db.update_account(account_id, label=page_name,
                                  meta={"page_id": fb_page_id})
            if tt_key or tt_secret:
                old = json.loads(secrets.get_secret("tiktok_client") or "{}")
                tt_key = tt_key or old.get("client_key", "")
                tt_secret = tt_secret or old.get("client_secret", "")
                if not (tt_key and tt_secret):
                    raise ValueError("Nhập đủ Client key và Client secret "
                                     "của TikTok.")
                secrets.set_secret("tiktok_client", json.dumps(
                    {"client_key": tt_key, "client_secret": tt_secret}))
        except ValueError as exc:
            QMessageBox.warning(self, "Thiếu thông tin", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi", f"Không lưu được: {exc}")
            return

        if self.autostart_cb.isEnabled():
            if not autostart.set_autostart(self.autostart_cb.isChecked()):
                QMessageBox.warning(
                    self, "Tự khởi động",
                    "Không ghi được registry. Hãy chạy app bằng "
                    "quyền Administrator rồi thử lại.")
                return
        from app.core import config as app_config
        app_config.save(
            {"close_action": self.close_action_combo.currentData()})
        self.accept()
