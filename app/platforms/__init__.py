"""Platform adapters: youtube, facebook, tiktok.

Factory tạo platform instance gắn với 1 tài khoản cụ thể.

Mỗi nền tảng có thể có nhiều tài khoản (VD: 2 kênh YouTube khác nhau).
Mỗi instance platform được gắn với 1 account_id và đọc token riêng
từ keyring theo key per-account.
"""
from .base import BasePlatform, UploadResult
from .facebook import FacebookPlatform
from .tiktok import TikTokPlatform
from .youtube import YouTubePlatform

PLATFORM_CLASSES: dict[str, type[BasePlatform]] = {
    "youtube": YouTubePlatform,
    "facebook": FacebookPlatform,
    "tiktok": TikTokPlatform,
}

PLATFORM_ORDER = ["youtube", "facebook", "tiktok"]
PLATFORM_LABELS = {"youtube": "YouTube", "facebook": "Facebook",
                   "tiktok": "TikTok"}


def get_platform(name: str,
                 account_id: int | None = None) -> BasePlatform:
    """Tạo platform instance cho tài khoản cụ thể."""
    cls = PLATFORM_CLASSES[name]
    return cls(account_id=account_id)


def native_scheduling(name: str) -> bool:
    """Nền tảng có lịch hẹn native không (không cần instance)."""
    return PLATFORM_CLASSES[name].native_scheduling


__all__ = ["BasePlatform", "UploadResult", "FacebookPlatform",
           "TikTokPlatform", "YouTubePlatform", "PLATFORM_CLASSES",
           "PLATFORM_ORDER", "PLATFORM_LABELS", "get_platform",
           "native_scheduling"]
