"""TikTok Content Posting API — chế độ inbox (draft).

POST /v2/post/publish/inbox/video/init/ -> PUT từng chunk lên upload_url
-> poll /v2/post/publish/status/fetch/ -> video nằm trong hộp thư TikTok,
user mở app TikTok bấm đăng tay.

Scope cần: video.upload (không cần audit cho chế độ inbox).
Giới hạn: tối đa ~5 video đang chờ / 24 giờ.
"""
import json
import os
import time
import uuid
from typing import Callable, Optional
from urllib.parse import urlencode

import requests

from .base import BasePlatform, UploadResult
from app.core import db, secrets

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
TOKEN_KEY = "tiktok_token_json"
CLIENT_KEY = "tiktok_client"
REDIRECT_URI = "http://localhost:8765/callback/"  # khớp đúng URI đã đăng ký (TikTok bắt có / cuối)
SCOPES = "video.upload"
CHUNK_SIZE = 32 * 1024 * 1024  # 32MB


def parse_client_config() -> Optional[dict]:
    raw = secrets.get_secret(CLIENT_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if data.get("client_key") and data.get("client_secret"):
            return data
    except (ValueError, TypeError):
        pass
    return None


def build_init_body(file_size: int, title: str) -> dict:
    """Body cho /post/publish/inbox/video/init/. Tách riêng để test.

    Theo docs Media Transfer của TikTok, source_info BẮT BUỘC gồm
    video_size, chunk_size và total_chunk_count = ceil(video_size/chunk).
    Thiếu total_chunk_count -> init fail ngay: "The video info is empty".
    """
    chunk = min(CHUNK_SIZE, file_size)
    total_chunks = (file_size + chunk - 1) // chunk
    return {
        "post_info": {"title": (title or "").strip()[:2200]},
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk,
            "total_chunk_count": total_chunks,
        },
    }


def generate_pkce() -> tuple[str, str]:
    """Tạo cặp (code_verifier, code_challenge) cho PKCE.

    LƯU Ý: TikTok desktop yêu cầu code_challenge = SHA256 dạng HEX
    (khác với chuẩn RFC 7636 dùng base64url!). Tách riêng để test.
    """
    import hashlib
    import secrets as secrets_lib  # tránh nhầm với app.core.secrets

    alphabet = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                "0123456789-._~")
    verifier = "".join(secrets_lib.choice(alphabet) for _ in range(64))
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    return verifier, challenge


def build_auth_url(client_key: str, state: str,
                   code_challenge: str) -> str:
    """URL authorize TikTok (kèm PKCE). Tách riêng để test."""
    return ("https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": client_key,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }))


def _api_error(resp: requests.Response) -> str:
    try:
        data = resp.json()
        msg = data.get("error", {}).get("message") if isinstance(
            data.get("error"), dict) else data.get("message")
        code = data.get("error_code") or data.get("code")
        text = f"{msg or resp.text}".strip()[:300]
        return f"[{code}] {text}" if code else text
    except ValueError:
        return resp.text[:300]


def _friendly_error(raw: str) -> str:
    low = raw.lower()
    if "5" in raw and ("24" in raw or "pending" in low or "limit" in low):
        return ("TikTok giới hạn tối đa 5 video đang chờ trong 24 giờ. "
                "Hãy đăng bớt video trong hộp thư TikTok rồi thử lại sau.")
    return f"Lỗi TikTok: {raw}"


class TikTokPlatform(BasePlatform):
    name = "tiktok"
    display_name = "TikTok"
    # TikTok KHÔNG có lịch hẹn trong API -> giữ native_scheduling=False:
    # scheduler chỉ upload khi đến giờ hẹn (máy phải bật lúc đó), video vào
    # hộp thư nháp, user mở app TikTok bấm đăng tay.
    native_scheduling = False

    def _token_key(self) -> str:
        return f"{TOKEN_KEY}_{self.account_id}" if self.account_id \
            else TOKEN_KEY

    # -- token ------------------------------------------------------------
    def _load_token(self) -> Optional[dict]:
        raw = secrets.get_secret(self._token_key())
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    def _get_valid_token(self) -> Optional[str]:
        tok = self._load_token()
        if not tok or not tok.get("access_token"):
            return None
        # Refresh sớm 10 phút trước khi hết hạn (access_token ~24h)
        expires_at = tok.get("expires_at", 0)
        if expires_at - time.time() < 600:
            tok = self._refresh_token(tok)
            if not tok:
                return None
        return tok["access_token"]

    def _refresh_token(self, tok: dict) -> Optional[dict]:
        cfg = parse_client_config()
        if not cfg or not tok.get("refresh_token"):
            return None
        try:
            resp = requests.post(TOKEN_URL, data={
                "client_key": cfg["client_key"],
                "client_secret": cfg["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": tok["refresh_token"],
            }, timeout=20)
            data = resp.json()
        except requests.RequestException:
            return None
        if "access_token" not in data:
            return None
        new_tok = {
            "access_token": data["access_token"],
            # TikTok rotate refresh_token: luôn persist token mới
            "refresh_token": data.get("refresh_token",
                                      tok.get("refresh_token")),
            "expires_at": time.time() + int(data.get("expires_in", 86400)),
            "open_id": data.get("open_id", tok.get("open_id")),
            "scope": data.get("scope", ""),
        }
        secrets.set_secret(self._token_key(), json.dumps(new_tok))
        return new_tok

    # -- connect ----------------------------------------------------------
    def connect(self, parent_widget=None,
                cancel_event=None) -> bool:
        """OAuth TikTok qua browser hệ thống.

        CHẠY TRÊN LUỒNG NỀN — không gọi trực tiếp trên luồng giao diện.
        Hủy giữa chừng qua cancel_event (threading.Event).
        """
        import webbrowser

        from .oauth_callback import OAuthCodeServer, wait_for_code

        cfg = parse_client_config()
        if not cfg:
            self.last_error = ("Chưa nhập Client Key/Secret của TikTok.\n"
                               "Vào Cài đặt để nhập trước khi kết nối.")
            return False
        server = OAuthCodeServer(port=8765)  # đúng cổng đã đăng ký app TikTok
        try:
            server.start()
        except OSError as exc:
            self.last_error = (
                f"Không mở được cổng 8765: {exc}\n"
                "Có thể app khác đang giữ cổng này — tắt rồi thử lại.")
            return False
        try:
            state = uuid.uuid4().hex
            code_verifier, code_challenge = generate_pkce()
            auth_url = build_auth_url(cfg["client_key"], state,
                                      code_challenge)
            self.last_auth_url = auth_url  # để nút "Mở lại trình duyệt"
            webbrowser.open(auth_url, new=1, autoraise=True)
            code, error = wait_for_code(server, timeout=180,
                                        cancel_event=cancel_event)
        finally:
            server.stop()
        if cancel_event is not None and cancel_event.is_set():
            self.last_error = "Đã hủy kết nối."
            return False
        if error:
            self.last_error = (f"TikTok từ chối cấp quyền: {error}")
            return False
        if not code:
            self.last_error = ("Hết thời gian chờ xác thực (180s). "
                               "Hãy thử lại và bấm Cho phép trên trình duyệt.")
            return False
        try:
            resp = requests.post(TOKEN_URL, data={
                "client_key": cfg["client_key"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            }, timeout=20)
            data = resp.json()
        except requests.RequestException as exc:
            self.last_error = f"Không đổi được token TikTok: {exc}"
            return False
        if "access_token" not in data:
            self.last_error = f"TikTok báo lỗi: {_api_error(resp)}"
            return False
        tok = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_at": time.time() + int(data.get("expires_in", 86400)),
            "open_id": data.get("open_id", ""),
            "scope": data.get("scope", ""),
        }
        secrets.set_secret(self._token_key(), json.dumps(tok))
        db.upsert_account(self.name, f"TikTok ({tok['open_id'][:8]}…)"
                          if tok["open_id"] else "TikTok", {})
        self._mark_connected()
        return True

    def disconnect(self) -> None:
        # Ngắt kết nối: GIỮ LẠI tài khoản (tên/token) để kết nối lại sau,
        # chỉ đánh dấu disconnected. Xóa hẳn thì dùng nút 🗑 trong dialog.
        if self.account_id:
            db.set_account_status(self.account_id, "disconnected")
        else:
            secrets.delete_secret(self._token_key())
            db.delete_account(self.name)

    def is_connected(self) -> bool:
        return self._is_active() and self._load_token() is not None

    def _secret_keys(self) -> list[str]:
        return [self._token_key()]

    # -- upload -----------------------------------------------------------
    def _put_chunks(self, upload_url: str, file_path: str, file_size: int,
                    chunk_size: int,
                    progress_cb: Callable[[int], None]) -> None:
        with open(file_path, "rb") as fh:
            start = 0
            while start < file_size:
                end = min(start + chunk_size, file_size) - 1
                fh.seek(start)
                chunk = fh.read(end - start + 1)
                last = (end == file_size - 1)
                resp = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range":
                            f"bytes {start}-{end}/{file_size}",
                    },
                    data=chunk,
                    timeout=600,
                )
                expected = 201 if last else 206
                if resp.status_code != expected:
                    raise RuntimeError(
                        f"Upload chunk thất bại "
                        f"(HTTP {resp.status_code}): {_api_error(resp)}")
                start = end + 1
                progress_cb(min(90, int(start * 100 / file_size)))

    def upload(self, item: dict,
               progress_cb: Callable[[int], None]) -> UploadResult:
        access_token = self._get_valid_token()
        if not access_token:
            return UploadResult(ok=False,
                                error="Chưa kết nối TikTok hoặc token hết hạn.")
        try:
            file_size = os.path.getsize(item["file_path"])
        except OSError:
            return UploadResult(ok=False, error="Không tìm thấy file video.")
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            # B1: init
            body = build_init_body(file_size, item.get("title", ""))
            r = requests.post(INIT_URL, headers=headers, json=body,
                              timeout=30)
            data = r.json()
            if (r.status_code != 200
                    or data.get("error_code") not in (None, "ok", 0, "")):
                return UploadResult(
                    ok=False, error=_friendly_error(_api_error(r)))
            info = data.get("data") or {}
            upload_url = info.get("upload_url")
            publish_id = info.get("publish_id")
            if not upload_url or not publish_id:
                return UploadResult(
                    ok=False, error=_friendly_error(_api_error(r)))

            # B2: PUT chunks
            self._put_chunks(upload_url, item["file_path"], file_size,
                             body["source_info"]["chunk_size"], progress_cb)

            # B3: poll trạng thái (tối đa ~3 phút)
            # LƯU Ý: hết 3 phút mà chưa SUCCESS thì KHÔNG được báo thành
            # công giả (bug cũ) — đánh failed để user kiểm tra tay trước
            # khi bấm đăng lại, tránh upload trùng.
            deadline = time.time() + 180
            last_status = "?"
            poll_ok = False
            while time.time() < deadline:
                try:
                    s = requests.post(
                        STATUS_URL, headers=headers,
                        json={"publish_id": publish_id},
                        timeout=20).json()
                except requests.RequestException:
                    time.sleep(10)
                    continue
                data = s.get("data") or {}
                status = data.get("status")
                last_status = status or "?"
                if status == "SUCCESS":
                    poll_ok = True
                    break
                if status == "FAILED":
                    detail = data.get("error_code") or ""
                    return UploadResult(
                        ok=False,
                        error=_friendly_error(
                            f"TikTok xử lý video thất bại {detail}".strip()))
                time.sleep(10)
            if not poll_ok:
                return UploadResult(
                    ok=False,
                    error=(f"TikTok chưa xử lý xong video sau 3 phút "
                           f"(trạng thái cuối: {last_status}). "
                           f"Hãy mở app TikTok kiểm tra bản nháp trước — "
                           f"nếu chưa có thì bấm Đăng ngay để thử lại."))

            progress_cb(100)
            # Video nằm trong hộp thư TikTok -> trạng thái 'draft'
            return UploadResult(ok=True, remote_id=str(publish_id),
                                status="draft")
        except requests.RequestException as exc:
            return UploadResult(ok=False, error=f"Lỗi mạng TikTok: {exc}")
        except Exception as exc:  # noqa: BLE001
            return UploadResult(ok=False, error=f"Lỗi TikTok: {exc}")
