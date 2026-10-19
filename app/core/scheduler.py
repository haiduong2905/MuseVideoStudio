"""Scheduler: QThread quét mỗi 30 giây, upload qua QThreadPool.

- Item đến giờ (scheduled_at <= now), target enabled, status='pending',
  attempts < 5 -> đánh dấu 'uploading' rồi đẩy vào worker thread.
- Thành công: status = scheduled/published/draft (tùy platform) + remote_id.
- Thất bại: attempts+1; attempts < 5 -> về 'pending', thử lại sau 15 phút;
  đủ 5 lần -> 'failed'. Mọi bước đều ghi log vào DB.
"""
import logging
import threading
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal

from app.core import db
from app.platforms import get_platform, native_scheduling
from app.platforms.base import UploadResult

log = logging.getLogger(__name__)

SCAN_INTERVAL_S = 30
MAX_ATTEMPTS = 5
RETRY_DELAY_MIN = 15

# Lỗi xác thực/token: retry cũng vô ích -> đánh dấu failed ngay để user
# kết nối lại tài khoản, thay vì chờ 5 lần x 15 phút.
_AUTH_ERROR_MARKERS = (
    "error validating access token",
    "session has expired",
    "invalid oauth access token",
    "invalid_oauth_access_token",
    "invalid_grant",
    "token has been expired",
    "token hết hạn",
    "chưa kết nối",
)


def is_auth_error(error: str) -> bool:
    """True nếu lỗi do token hết hạn/không hợp lệ (không nên retry)."""
    low = (error or "").lower()
    return any(m in low for m in _AUTH_ERROR_MARKERS)


class SchedulerSignals(QObject):
    targets_changed = Signal()  # queue đổi trạng thái -> UI refresh bảng
    # Video TikTok đã vào nháp đến giờ cần đăng tay:
    # dict {target_id, queue_id, title, scheduled_at}
    tiktok_reminder = Signal(dict)


class UploadWorker(QRunnable):
    def __init__(self, target: dict, signals: SchedulerSignals) -> None:
        super().__init__()
        self.target = target
        self.signals = signals

    def run(self) -> None:  # noqa: C901 - luồng xử lý chính, giữ liền mạch
        target = self.target
        platform_name = target["platform"]
        account_id = target.get("account_id")
        try:
            platform = get_platform(platform_name, account_id)
        except KeyError:
            platform = None
        qid = target["queue_id"]
        content_type = target.get("content_type") or "video"
        if content_type == "post":
            item = {
                "text": "\n\n".join(
                    p for p in [target.get("title") or "",
                                (target.get("description") or "").strip(),
                                (target.get("hashtags") or "").strip()]
                    if p).strip(),
                "image_paths": target.get("image_paths") or "[]",
                "scheduled_at": target.get("scheduled_at") or db.now_iso(),
            }
            label = f"bài viết {(target.get('title') or '')[:40]}"
        else:
            item = {
                "file_path": target["file_path"],
                "title": target.get("title") or "",
                "description": target.get("description") or "",
                "hashtags": target.get("hashtags") or "",
                "scheduled_at": target.get("scheduled_at") or db.now_iso(),
                "thumbnail_path": target.get("thumbnail_path") or "",
            }
            label = f"{target.get('title') or 'video'}"

        if platform is None:
            db.add_log(qid, platform_name, "error",
                       "Không tìm thấy platform, bỏ qua.")
            db.update_target(target["id"], status="failed",
                             error="Platform không khả dụng.")
            self.signals.targets_changed.emit()
            return

        db.add_log(qid, platform.name, "info",
                   f"Bắt đầu đăng {platform.display_name}: {label}")
        try:
            if content_type == "post":
                result = platform.upload_post(item, lambda _p: None)
            else:
                result = platform.upload(item, lambda _p: None)
        except Exception as exc:  # noqa: BLE001 - không để worker crash
            log.exception("Upload worker lỗi")
            result = UploadResult(ok=False, error=str(exc))

        if result.ok:
            status = result.status or "scheduled"
            db.update_target(target["id"], status=status,
                             remote_id=result.remote_id, error=None,
                             next_retry_at=None)
            extra = ""
            if native_scheduling(platform_name) and status == "scheduled":
                extra = " — nền tảng sẽ tự đăng đúng giờ hẹn."
            db.add_log(qid, platform.name, "info",
                       f"Đăng {platform.display_name} thành công "
                       f"({label}).{extra}")
            if result.warning:
                db.add_log(qid, platform.name, "warning",
                           f"{label}: {result.warning}")
        else:
            attempts = (target.get("attempts") or 0) + 1
            if is_auth_error(result.error):
                # Token hết hạn/không hợp lệ: retry vô ích -> failed ngay,
                # báo rõ để user kết nối lại tài khoản.
                db.update_target(target["id"], status="failed",
                                 attempts=attempts, error=result.error,
                                 next_retry_at=None)
                db.add_log(qid, platform.name, "error",
                           f"Đăng {platform.display_name} thất bại: "
                           f"{result.error}. Token có thể đã hết hạn — hãy "
                           f"vào Tài khoản kết nối lại rồi bấm Đăng lại.")
            elif attempts < MAX_ATTEMPTS:
                retry_at = (datetime.now()
                            + timedelta(minutes=RETRY_DELAY_MIN)
                            ).strftime("%Y-%m-%dT%H:%M:%S")
                db.update_target(target["id"], status="pending",
                                 attempts=attempts, error=result.error,
                                 next_retry_at=retry_at)
                db.add_log(qid, platform.name, "warning",
                           f"Đăng {platform.display_name} thất bại "
                           f"(lần {attempts}/{MAX_ATTEMPTS}): "
                           f"{result.error}. Thử lại sau {RETRY_DELAY_MIN} phút.")
            else:
                db.update_target(target["id"], status="failed",
                                 attempts=attempts, error=result.error,
                                 next_retry_at=None)
                db.add_log(qid, platform.name, "error",
                           f"Đăng {platform.display_name} thất bại sau "
                           f"{MAX_ATTEMPTS} lần: {result.error}")
        self.signals.targets_changed.emit()


class SchedulerThread(QThread):
    """Vòng lặp nền: mỗi 30s quét item đến giờ."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.signals = SchedulerSignals()
        self.pool = QThreadPool.globalInstance()
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(SCAN_INTERVAL_S):
            try:
                self.process_due()
                self.check_tiktok_reminders()
            except Exception:  # noqa: BLE001
                log.exception("Scheduler quét lỗi")

    def check_tiktok_reminders(self) -> int:
        """Tìm video TikTok đã vào nháp mà user chưa đăng tay -> nhắc.

        Đánh dấu reminded=1 trước khi phát signal để không nhắc trùng.
        Trả về số video đã nhắc.
        """
        now = db.now_iso()
        drafts = db.get_unreminded_tiktok_drafts(now)
        for d in drafts:
            db.update_target(d["target_id"], reminded=1,
                             next_reminder_at=None)
            db.add_log(d["queue_id"], "tiktok", "info",
                       "Video đã vào hộp thư TikTok — nhắc user đăng tay.")
            self.signals.tiktok_reminder.emit(d)
        if drafts:
            self.signals.targets_changed.emit()
        return len(drafts)

    def process_due(self) -> int:
        """Quét và đẩy target cần upload vào worker. Trả về số đã đẩy.

        - Nền tảng có native_scheduling (YouTube/Facebook): upload NGAY khi
          pending — nền tảng giữ lịch và tự đăng đúng giờ.
        - Nền tảng còn lại (TikTok): chỉ upload khi đã đến giờ hẹn.
        """
        now = db.now_iso()
        pending = db.get_pending_targets(now)
        count = 0
        for target in pending:
            platform_name = target["platform"]
            try:
                is_native = native_scheduling(platform_name)
            except KeyError:
                continue
            if not db.account_is_active(target.get("account_id")):
                continue  # tài khoản đã Ngắt: giữ pending, chờ kết nối lại
            if not is_native \
                    and (target.get("scheduled_at") or "") > now:
                continue  # chưa đến giờ hẹn
            # Đánh dấu trước để lần quét sau không bắt lại
            db.update_target(target["id"], status="uploading")
            self.pool.start(UploadWorker(target, self.signals))
            count += 1
        return count

    def stop(self) -> None:
        self._stop.set()
        self.wait()
