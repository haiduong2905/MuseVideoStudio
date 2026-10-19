"""YouTube Data API v3: OAuth desktop flow + videos.insert resumable.

Video được upload ở chế độ private kèm `publishAt` -> YouTube tự public
đúng giờ đã hẹn (native scheduling).
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from .base import BasePlatform, UploadResult
from app.core import secrets

TOKEN_KEY = "youtube_token_json"
CLIENT_KEY = "youtube_client"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


def to_utc_iso(local_iso: str) -> str:
    """'2026-10-17T10:00:00' (giờ máy, hoặc có offset) -> '...Z' UTC."""
    dt = datetime.fromisoformat(local_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def is_immediate_publish(scheduled_at: str) -> bool:
    """True nếu giờ hẹn đã qua (hoặc quá gần) -> đăng public luôn thay vì
    hẹn giờ (YouTube bắt publishAt phải ở tương lai)."""
    try:
        dt = datetime.fromisoformat(scheduled_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return dt <= datetime.now(timezone.utc) + timedelta(minutes=2)
    except (ValueError, TypeError):
        return True


def build_video_body(item: dict) -> dict:
    """Dựng body cho videos.insert. Tách riêng để dễ unit test."""
    title = (item.get("title") or "").strip()[:100]
    hashtags = (item.get("hashtags") or "").strip()
    description = (item.get("description") or "").strip()
    if hashtags:
        description = f"{description}\n\n{hashtags}".strip()
    tags = [t.lstrip("#").strip() for t in hashtags.split()
            if t.lstrip("#").strip()][:30]
    if is_immediate_publish(item.get("scheduled_at") or ""):
        status = {"privacyStatus": "public"}
    else:
        status = {
            "privacyStatus": "private",
            "publishAt": to_utc_iso(item["scheduled_at"]),
        }
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",  # Education
        },
        "status": status,
    }


def parse_client_config() -> Optional[dict]:
    raw = secrets.get_secret(CLIENT_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if data.get("client_id") and data.get("client_secret"):
            return data
    except (ValueError, TypeError):
        pass
    return None


class YouTubePlatform(BasePlatform):
    name = "youtube"
    display_name = "YouTube"
    # YouTube có lịch hẹn native (publishAt): upload ngay khi thêm vào hàng
    # đợi, YouTube tự public đúng giờ — tắt máy sau khi upload xong vẫn được.
    native_scheduling = True

    def _token_key(self) -> str:
        if self.account_id:
            return f"{TOKEN_KEY}_{self.account_id}"
        return TOKEN_KEY

    # -- credentials ------------------------------------------------------
    def _get_credentials(self):
        """Lazy import google libs để test payload không cần cài google libs."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError:
            return None

        raw = secrets.get_secret(self._token_key())
        if not raw:
            return None
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(raw), SCOPES)
        except (ValueError, TypeError):
            return None
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                secrets.set_secret(self._token_key(), creds.to_json())
            except Exception:
                return None
        return creds if creds.valid else None

    # -- connect ----------------------------------------------------------
    def connect(self, parent_widget=None,
                cancel_event=None) -> bool:
        """OAuth YouTube qua browser hệ thống.

        CHẠY TRÊN LUỒNG NỀN (accounts_dialog dùng QThread) — không bao giờ
        gọi trực tiếp trên luồng giao diện vì phải chờ user xác thực.
        Hủy giữa chừng qua cancel_event (threading.Event).
        """
        import webbrowser

        from google_auth_oauthlib.flow import InstalledAppFlow

        from .oauth_callback import (OAuthCodeServer, wait_for_code)

        cfg = parse_client_config()
        if not cfg:
            self.last_error = ("Chưa nhập Client ID/Secret của YouTube.\n"
                               "Vào Cài đặt để nhập trước khi kết nối.")
            return False
        server = OAuthCodeServer()
        try:
            server.start()
        except OSError as exc:
            self.last_error = (f"Không mở được cổng localhost: {exc}\n"
                               "Kiểm tra firewall/antivirus có chặn không.")
            return False
        try:
            flow = InstalledAppFlow.from_client_config(
                {"installed": {
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uris": ["http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }},
                scopes=SCOPES,
            )
            flow.redirect_uri = server.redirect_uri
            auth_url, _ = flow.authorization_url(prompt="consent")
            self.last_auth_url = auth_url  # để nút "Mở lại trình duyệt"
            # Mở browser hệ thống, Google redirect về localhost
            webbrowser.open(auth_url, new=1, autoraise=True)
            code, error = wait_for_code(server, timeout=300,
                                        cancel_event=cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                self.last_error = "Đã hủy kết nối."
                return False
            if error:
                self.last_error = f"Google từ chối cấp quyền: {error}"
                return False
            if not code:
                self.last_error = (
                    "Hết thời gian chờ xác thực (5 phút).\n"
                    "Hãy thử lại: bấm kết nối, trên trình duyệt đăng nhập "
                    "Google và bấm Cho phép.")
                return False
            # Đổi code lấy token, giới hạn 90s để không treo khi mạng đơ
            import concurrent.futures as _fut
            with _fut.ThreadPoolExecutor(max_workers=1) as _ex:
                _ft = _ex.submit(flow.fetch_token, code=code)
                try:
                    _ft.result(timeout=90)
                except _fut.TimeoutError:
                    self.last_error = ("Google phản hồi quá chậm khi đổi "
                                       "token (90s). Hãy thử kết nối lại.")
                    return False
            creds = flow.credentials
        except Exception as exc:  # noqa: BLE001 - lỗi OAuth/browser đa dạng
            if cancel_event is not None and cancel_event.is_set():
                self.last_error = "Đã hủy kết nối."
            else:
                self.last_error = f"Kết nối YouTube thất bại: {exc}"
            return False
        finally:
            server.stop()
        if not secrets.set_secret(self._token_key(), creds.to_json()):
            self.last_error = ("Lưu token thất bại (keyring không khả dụng).")
            return False
        self._mark_connected()
        return True

    def disconnect(self) -> None:
        # Ngắt kết nối: GIỮ LẠI tài khoản (tên/token) để kết nối lại sau,
        # chỉ đánh dấu disconnected. Xóa hẳn thì dùng nút 🗑 trong dialog.
        from app.core import db
        if self.account_id:
            db.set_account_status(self.account_id, "disconnected")
        else:
            secrets.delete_secret(self._token_key())
            db.delete_account(self.name)

    def is_connected(self) -> bool:
        return self._is_active() and self._get_credentials() is not None

    def _secret_keys(self) -> list[str]:
        return [self._token_key()]

    # -- upload -----------------------------------------------------------
    def upload(self, item: dict,
               progress_cb: Callable[[int], None]) -> UploadResult:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = self._get_credentials()
            if not creds:
                return UploadResult(
                    ok=False, error="Chưa kết nối YouTube hoặc token hết hạn.")
            import httplib2
            # Timeout rõ ràng cho từng request (mặc định httplib2 treo tới
            # khi OS timeout -> WinError 10060). 300s đủ cho chunk 8MB.
            # LƯU Ý: build() cấm truyền cả http và credentials cùng lúc
            # ("mutually exclusive") -> bọc http bằng AuthorizedHttp.
            try:
                from google_auth_httplib2 import AuthorizedHttp
                authed_http = AuthorizedHttp(
                    creds, http=httplib2.Http(timeout=300))
                youtube = build("youtube", "v3", http=authed_http)
            except ImportError:
                youtube = build("youtube", "v3", credentials=creds)
            media = MediaFileUpload(item["file_path"],
                                    chunksize=CHUNK_SIZE, resumable=True)
            body = build_video_body(item)
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress_cb(int(status.progress() * 100))
            final = ("scheduled" if "publishAt" in body["status"]
                     else "published")
            video_id = response.get("id")
            warning = None
            # Đặt ảnh bìa (không làm fail cả lượt đăng nếu lỗi)
            thumb = (item.get("thumbnail_path") or "").strip()
            if thumb:
                try:
                    import os as _os
                    if _os.path.isfile(thumb):
                        youtube.thumbnails().set(
                            videoId=video_id,
                            media_body=MediaFileUpload(
                                thumb, mimetype="image/jpeg"),
                        ).execute()
                    else:
                        warning = "Không tìm thấy file ảnh bìa, bỏ qua."
                except Exception as exc:  # noqa: BLE001
                    warning = f"Đặt ảnh bìa YouTube thất bại: {exc}"
            return UploadResult(ok=True, remote_id=video_id,
                                status=final, warning=warning)
        except FileNotFoundError:
            return UploadResult(ok=False, error="Không tìm thấy file video.")
        except Exception as exc:  # noqa: BLE001
            return UploadResult(ok=False, error=f"Lỗi YouTube: {exc}")
