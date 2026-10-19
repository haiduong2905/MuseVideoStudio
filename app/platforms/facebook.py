"""Facebook Graph API: đăng Reels lên Page, 3-phase upload.

start (lấy upload_url + video_id) -> PUT binary -> finish
(video_state=SCHEDULED + scheduled_publish_time) -> Facebook tự đăng đúng giờ.

Giới hạn Reels: lịch hẹn từ 10 phút đến 29 ngày, tối đa 30 reels/24h.
"""
import os
import time
from datetime import datetime
from typing import Callable, Optional

import requests

from .base import BasePlatform, UploadResult
from app.core import db, secrets

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN_KEY = "facebook_token_json"
PAGE_ID_KEY = "facebook_page_id"


def to_unix(local_iso: str) -> int:
    dt = datetime.fromisoformat(local_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return int(dt.timestamp())


def build_finish_params(video_id: str, description: str,
                        scheduled_unix: int,
                        video_state: str = "SCHEDULED") -> dict:
    """Params cho phase finish. Tách riêng để dễ unit test.

    video_state="PUBLISHED": đăng luôn (khi giờ hẹn đã qua hoặc quá gần —
    Facebook yêu cầu lịch hẹn cách hiện tại ít nhất 10 phút).
    """
    params = {
        "upload_phase": "finish",
        "video_id": video_id,
        "description": description,
        "video_state": video_state,
    }
    if video_state == "SCHEDULED":
        params["scheduled_publish_time"] = int(scheduled_unix)
    return params


def _graph_error(resp: requests.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error") or {}
        return str(err.get("message") or resp.text)[:300]
    except ValueError:
        return resp.text[:300]


class _ProgressReader:
    """File-like wrapper báo tiến độ khi requests stream PUT binary.

    Có __len__ để requests tự set Content-Length (không dùng chunked).
    """

    def __init__(self, path: str,
                 progress_cb: Callable[[int], None]) -> None:
        self._fh = open(path, "rb")
        self._size = os.path.getsize(path)
        self._sent = 0
        self._cb = progress_cb

    def __len__(self) -> int:
        return self._size

    def read(self, n: int = -1) -> bytes:
        chunk = self._fh.read(n)
        if chunk:
            self._sent += len(chunk)
            self._cb(min(99, int(self._sent * 100 / self._size)))
        return chunk

    def close(self) -> None:
        self._fh.close()


class FacebookPlatform(BasePlatform):
    name = "facebook"
    display_name = "Facebook"
    # Reels có lịch hẹn native (video_state=SCHEDULED): upload ngay khi thêm
    # vào hàng đợi, Facebook tự đăng đúng giờ — tắt máy sau đó vẫn được.
    native_scheduling = True

    # -- credentials ------------------------------------------------------
    def _token_key(self) -> str:
        base = TOKEN_KEY
        return f"{base}_{self.account_id}" if self.account_id else base

    def _page_id_key(self) -> str:
        return f"{PAGE_ID_KEY}_{self.account_id}" if self.account_id \
            else PAGE_ID_KEY

    def _get_creds(self) -> Optional[tuple[str, str]]:
        token = secrets.get_secret(self._token_key())
        page_id = secrets.get_secret(self._page_id_key())
        if token and page_id:
            return page_id, token
        return None

    # -- connect ----------------------------------------------------------
    def save_credentials(self, page_id: str, token: str) -> str:
        """Kiểm tra và lưu Page ID + token cho account hiện tại.

        Trả về tên Page (để đặt label). Raise ValueError nếu không hợp lệ.
        """
        page_id = (page_id or "").strip()
        token = (token or "").strip()
        if not page_id or not token:
            raise ValueError("Vui lòng nhập đủ Page ID và access token.")
        try:
            resp = requests.get(f"{GRAPH}/{page_id}",
                                params={"fields": "name",
                                        "access_token": token},
                                timeout=20)
        except requests.RequestException as exc:
            raise ValueError(f"Không gọi được Facebook: {exc}")
        if resp.status_code != 200:
            raise ValueError(
                f"Token/Page ID không đúng: {_graph_error(resp)}")
        page_name = resp.json().get("name", page_id)
        secrets.set_secret(self._token_key(), token)
        secrets.set_secret(self._page_id_key(), page_id)
        return page_name

    def connect(self, parent_widget=None,
                cancel_event=None) -> bool:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, \
            QLineEdit, QVBoxLayout

        class _Dlg(QDialog):
            def __init__(self, parent, page_id="", token=""):
                super().__init__(parent)
                self.setWindowTitle("Kết nối Facebook")
                self.page_edit = QLineEdit()
                self.page_edit.setPlaceholderText("VD: 123456789012345")
                self.page_edit.setText(page_id)
                self.token_edit = QLineEdit()
                self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
                self.token_edit.setPlaceholderText("Dán Page access token")
                self.token_edit.setText(token)
                form = QFormLayout()
                form.addRow("Page ID:", self.page_edit)
                form.addRow("Page access token:", self.token_edit)
                btns = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok |
                    QDialogButtonBox.StandardButton.Cancel)
                btns.accepted.connect(self.accept)
                btns.rejected.connect(self.reject)
                lay = QVBoxLayout(self)
                lay.addLayout(form)
                lay.addWidget(btns)

        # Điền sẵn giá trị đã lưu (nếu có) để đối chiếu/sửa rồi kết nối lại
        _saved = self._get_creds()
        _page, _tok = _saved if _saved else ("", "")
        dlg = _Dlg(parent_widget, _page, _tok)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.last_error = "Đã hủy kết nối."
            return False
        try:
            page_name = self.save_credentials(
                dlg.page_edit.text(), dlg.token_edit.text())
        except ValueError as exc:
            self.last_error = str(exc)
            return False
        # account row do caller (AccountsDialog) tạo trước
        if self.account_id:
            db.update_account(self.account_id, label=page_name,
                              meta={"page_id":
                                    dlg.page_edit.text().strip()})
        else:
            db.upsert_account(self.name, page_name,
                              {"page_id": dlg.page_edit.text().strip()})
        self._mark_connected()
        return True

    def disconnect(self) -> None:
        # Ngắt kết nối: GIỮ LẠI tài khoản (tên/Page ID/token) để kết nối
        # lại sau, chỉ đánh dấu disconnected. Xóa hẳn: nút 🗑 trong dialog.
        if self.account_id:
            db.set_account_status(self.account_id, "disconnected")
        else:
            secrets.delete_secret(self._token_key())
            secrets.delete_secret(self._page_id_key())
            db.delete_account(self.name)

    def is_connected(self) -> bool:
        return self._is_active() and self._get_creds() is not None

    def _secret_keys(self) -> list[str]:
        return [self._token_key(), self._page_id_key()]

    # -- upload -----------------------------------------------------------
    def _put_binary(self, upload_url: str, token: str, file_path: str,
                    progress_cb: Callable[[int], None]) -> None:
        size = os.path.getsize(file_path)
        reader = _ProgressReader(file_path, progress_cb)
        try:
            # Meta yêu cầu POST (không phải PUT) lên upload_url
            resp = requests.post(
                upload_url,
                headers={"Authorization": f"OAuth {token}",
                         "offset": "0",
                         "file_size": str(size)},
                data=reader,
                timeout=600,
            )
        finally:
            reader.close()
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Upload binary thất bại (HTTP {resp.status_code}): "
                f"{_graph_error(resp)}")

    def upload(self, item: dict,
               progress_cb: Callable[[int], None]) -> UploadResult:
        creds = self._get_creds()
        if not creds:
            return UploadResult(ok=False,
                                error="Chưa kết nối Facebook.")
        page_id, token = creds
        try:
            size = os.path.getsize(item["file_path"])
        except OSError:
            return UploadResult(ok=False, error="Không tìm thấy file video.")
        try:
            # Phase 1: start
            r = requests.post(
                f"{GRAPH}/{page_id}/video_reels",
                data={"upload_phase": "start", "file_size": size,
                      "access_token": token},
                timeout=30)
            if r.status_code != 200:
                return UploadResult(
                    ok=False, error=f"Facebook từ chối: {_graph_error(r)}")
            data = r.json()
            upload_url, video_id = data["upload_url"], data["video_id"]

            # Phase 2: PUT binary
            self._put_binary(upload_url, token, item["file_path"],
                             progress_cb)

            # Phase 3: finish + lên lịch (hoặc đăng luôn nếu giờ hẹn
            # đã qua / cách hiện tại dưới 10 phút — Facebook bắt lịch hẹn
            # tối thiểu 10 phút trong tương lai)
            hashtags = (item.get("hashtags") or "").strip()
            desc_parts = [p for p in [item.get("title", "").strip(),
                                      (item.get("description") or "").strip(),
                                      hashtags] if p]
            sched_unix = to_unix(item["scheduled_at"])
            immediate = sched_unix <= time.time() + 600
            params = build_finish_params(
                video_id, "\n\n".join(desc_parts), sched_unix,
                video_state="PUBLISHED" if immediate else "SCHEDULED")
            params["access_token"] = token
            # Ảnh bìa: tham số `thumb` (dữ liệu ảnh thô, multipart)
            thumb = (item.get("thumbnail_path") or "").strip()
            files = None
            fh = None
            warning = None
            if thumb:
                if os.path.isfile(thumb):
                    fh = open(thumb, "rb")
                    files = {"thumb": ("thumbnail.jpg", fh, "image/jpeg")}
                else:
                    warning = "Không tìm thấy file ảnh bìa, bỏ qua."
            try:
                r = requests.post(f"{GRAPH}/{page_id}/video_reels",
                                  data=params, files=files, timeout=60)
            finally:
                if fh:
                    fh.close()
            if r.status_code != 200:
                return UploadResult(
                    ok=False, error=f"Facebook từ chối: {_graph_error(r)}")

            # Poll trạng thái (tối đa ~2 phút), không fail nếu API không trả
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    s = requests.get(
                        f"{GRAPH}/{video_id}",
                        params={"fields": "status",
                                "access_token": token},
                        timeout=15).json()
                    if isinstance(s, dict) and s.get("status"):
                        break
                except requests.RequestException:
                    pass
                time.sleep(10)

            progress_cb(100)
            return UploadResult(ok=True, remote_id=str(video_id),
                                status="published" if immediate
                                else "scheduled", warning=warning)
        except requests.RequestException as exc:
            return UploadResult(ok=False, error=f"Lỗi mạng Facebook: {exc}")
        except Exception as exc:  # noqa: BLE001
            return UploadResult(ok=False, error=f"Lỗi Facebook: {exc}")

    # -- bài viết (chữ / ảnh) ---------------------------------------------
    def upload_post(self, item: dict,
                    progress_cb: Callable[[int], None]) -> UploadResult:
        """Đăng bài viết lên Page: chỉ chữ, hoặc kèm 1..n ảnh.

        item: text, image_paths (list), scheduled_at.
        Có lên lịch native (published=false + scheduled_publish_time).
        """
        import json as json_lib

        creds = self._get_creds()
        if not creds:
            return UploadResult(ok=False,
                                error="Chưa kết nối Facebook.")
        page_id, token = creds
        text = (item.get("text") or "").strip()
        try:
            images = json_lib.loads(item.get("image_paths") or "[]")
        except (ValueError, TypeError):
            images = []
        images = [p for p in images if p and os.path.isfile(p)]
        if not text and not images:
            return UploadResult(ok=False,
                                error="Bài viết trống (cần chữ hoặc ảnh).")
        try:
            sched_unix = to_unix(item["scheduled_at"])
            # Facebook: lịch hẹn tối thiểu 10 phút sau hiện tại
            scheduled = sched_unix > time.time() + 600

            photo_ids: list[str] = []
            for i, img_path in enumerate(images):
                progress_cb(int(i * 80 / max(len(images), 1)))
                with open(img_path, "rb") as fh:
                    r = requests.post(
                        f"{GRAPH}/{page_id}/photos",
                        data={"published": "false",
                              "access_token": token},
                        files={"source": (
                            os.path.basename(img_path), fh, "image/jpeg")},
                        timeout=120)
                if r.status_code != 200:
                    return UploadResult(
                        ok=False,
                        error=f"Facebook từ chối ảnh {i + 1}: "
                              f"{_graph_error(r)}")
                pid = r.json().get("id")
                if not pid:
                    return UploadResult(
                        ok=False,
                        error=f"Facebook không trả về ID cho ảnh {i + 1}.")
                photo_ids.append(str(pid))

            data: dict = {"access_token": token}
            if text:
                data["message"] = text
            if photo_ids:
                data["attached_media"] = json_lib.dumps(
                    [{"media_fbid": pid} for pid in photo_ids])
            if scheduled:
                data["published"] = "false"
                data["scheduled_publish_time"] = int(sched_unix)
            r = requests.post(f"{GRAPH}/{page_id}/feed", data=data,
                              timeout=60)
            if r.status_code != 200:
                return UploadResult(
                    ok=False, error=f"Facebook từ chối: {_graph_error(r)}")
            post_id = str(r.json().get("id") or "")
            progress_cb(100)
            return UploadResult(ok=True, remote_id=post_id,
                                status="scheduled" if scheduled
                                else "published")
        except requests.RequestException as exc:
            return UploadResult(ok=False, error=f"Lỗi mạng Facebook: {exc}")
        except Exception as exc:  # noqa: BLE001
            return UploadResult(ok=False, error=f"Lỗi Facebook: {exc}")
