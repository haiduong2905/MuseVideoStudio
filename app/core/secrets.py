"""Wrapper keyring — lưu token/credential vào Windows Credential Manager.

Service name: "MuseVideoStudio". Key quy ước:
  {platform}_token_json  — token OAuth / access token (JSON string)
  youtube_client         — {"client_id": ..., "client_secret": ...}
  tiktok_client          — {"client_key": ..., "client_secret": ...}
  facebook_page_id       — Page ID (không nhạy cảm nhưng để chung cho gọn)

keyring được import lazy trong từng hàm để import module không bao giờ
đụng độ dependency. KHÔNG BAO GIỜ log giá trị secret.
"""
import logging

log = logging.getLogger(__name__)

SERVICE = "MuseVideoStudio"
_LEGACY_SERVICE = "SocialUploader"  # đọc fallback 1 lần rồi migrate sang mới


def _backend():
    import keyring  # lazy: chỉ cần khi thực sự đọc/ghi
    return keyring


def set_secret(key: str, value: str) -> bool:
    """Lưu secret. Trả về True nếu thành công."""
    try:
        _backend().set_password(SERVICE, key, value)
        return True
    except Exception as exc:  # noqa: BLE001 - keyring backend có thể lỗi
        log.warning("Không lưu được secret '%s': %s", key, type(exc).__name__)
        return False


def get_secret(key: str) -> str | None:
    """Đọc secret, trả về None nếu chưa có hoặc lỗi.

    Fallback: nếu service mới chưa có mà service cũ (SocialUploader) có,
    tự migrate sang service mới rồi trả về — Khang không phải nối lại
    tài khoản đã kết nối ở app cũ.
    """
    try:
        val = _backend().get_password(SERVICE, key)
        if val:
            return val
        legacy = _backend().get_password(_LEGACY_SERVICE, key)
        if legacy:
            try:
                _backend().set_password(SERVICE, key, legacy)
            except Exception:
                pass
            return legacy
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Không đọc được secret '%s': %s", key, type(exc).__name__)
        return None


def delete_secret(key: str) -> bool:
    """Xóa secret. Trả về True nếu thành công."""
    try:
        _backend().delete_password(SERVICE, key)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Không xóa được secret '%s': %s", key, type(exc).__name__)
        return False


def has_secret(key: str) -> bool:
    return bool(get_secret(key))
