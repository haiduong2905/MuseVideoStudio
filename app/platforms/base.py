"""Interface chung cho các nền tảng đăng video."""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class UploadResult:
    ok: bool
    remote_id: Optional[str] = None
    status: Optional[str] = None   # pending|uploading|scheduled|published|draft|failed
    error: Optional[str] = None
    warning: Optional[str] = None  # cảnh báo không nghiêm trọng (vd: đặt ảnh bìa lỗi)


class BasePlatform:
    """Mỗi nền tảng implement: connect / disconnect / is_connected / upload.

    `item` là dict gồm: file_path, title, description, hashtags, scheduled_at
    (scheduled_at: ISO local "YYYY-MM-DDTHH:MM:SS").
    `progress_cb` nhận int 0..100.
    """

    name: str = ""
    display_name: str = ""
    # True: nền tảng có lịch hẹn native (YouTube publishAt, Facebook
    # video_state=SCHEDULED) -> scheduler upload NGAY khi thêm vào hàng đợi,
    # nền tảng tự đăng đúng giờ, tắt máy sau khi upload xong cũng được.
    # False: phải upload đúng giờ hẹn (TikTok inbox) -> máy phải bật lúc đó.
    native_scheduling: bool = False

    def __init__(self, account_id: int | None = None) -> None:
        self.last_error: str = ""
        self.last_auth_url: str = ""  # URL OAuth vừa mở (nút "Mở lại")
        # Tài khoản mà instance này phụ trách (multi-account).
        # None = chưa gắn tài khoản cụ thể.
        self.account_id = account_id

    # -- kết nối ---------------------------------------------------------
    def connect(self, parent_widget=None,
                cancel_event=None) -> bool:
        """Kết nối tài khoản. YouTube/TikTok: chạy trên luồng nền, hủy được
        qua cancel_event (threading.Event). Facebook: form nhập trên GUI."""
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError

    def _is_active(self) -> bool:
        """Tài khoản có đang ở trạng thái active không (chưa bị Ngắt).

        Dùng trong is_connected(): Ngắt kết nối giữ lại tên/ID/token,
        chỉ đánh dấu disconnected.
        """
        if not self.account_id:
            return True
        try:
            from app.core import db
            return db.account_is_active(self.account_id)
        except Exception:  # noqa: BLE001
            return True

    def _mark_connected(self) -> None:
        """Gọi khi connect thành công: status -> active."""
        if not self.account_id:
            return
        try:
            from app.core import db
            db.set_account_status(self.account_id, "active")
        except Exception:  # noqa: BLE001
            pass

    def _secret_keys(self) -> list[str]:
        """Các key secrets của account này (để xóa hẳn khi purge)."""
        return []

    def purge(self) -> None:
        """Xóa HẲN tài khoản khỏi máy: secrets + dòng DB.

        Khác disconnect(): disconnect chỉ đánh dấu disconnected và GIỮ
        lại tên/ID/token để kết nối lại sau.
        """
        try:
            from app.core import secrets as secrets_mod
            for k in self._secret_keys():
                try:
                    secrets_mod.delete_secret(k)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
        if self.account_id:
            try:
                from app.core import db
                db.delete_account_by_id(self.account_id)
            except Exception:  # noqa: BLE001
                pass

    # -- đăng ------------------------------------------------------------
    def upload(self, item: dict,
               progress_cb: Callable[[int], None]) -> UploadResult:
        raise NotImplementedError

    def upload_post(self, item: dict,
                    progress_cb: Callable[[int], None]) -> UploadResult:
        """Đăng bài viết (chữ/ảnh). Mặc định: nền tảng không hỗ trợ.

        item: text, image_paths (JSON list), scheduled_at.
        """
        return UploadResult(
            ok=False,
            error=f"{self.display_name or self.name} chưa hỗ trợ đăng "
                  f"bài viết qua API (chỉ đăng được video).")
