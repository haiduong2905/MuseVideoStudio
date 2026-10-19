"""Mailbox Plan B: poll manifest -> tải video về máy -> phân loại -> dedup.

Logic thuần (parse/diff/download) tách khỏi QThread để unit test được.
Worker chỉ điều phối + phát signal cho UI.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

CHUNK = 1024 * 1024  # 1MB
MAX_RETRIES = 3


class ManifestError(Exception):
    """Manifest sai định dạng hoặc không tải được."""


@dataclass
class ManifestVideo:
    id: str
    file_url: str
    project_code: str = ""
    brief_id: int | None = None
    scene: str = ""
    title: str = ""
    description: str = ""
    hashtags: str = ""
    duration: int = 10
    ratio: str = "9:16"
    sha256: str = ""
    created_at: str = ""


def parse_manifest(payload: dict) -> list[ManifestVideo]:
    """Parse manifest.json. Raise ManifestError nếu sai định dạng."""
    if not isinstance(payload, dict):
        raise ManifestError("Manifest phải là JSON object.")
    videos = payload.get("videos")
    if not isinstance(videos, list):
        raise ManifestError("Manifest thiếu trường 'videos' (list).")
    out = []
    for i, v in enumerate(videos):
        if not isinstance(v, dict):
            raise ManifestError(f"videos[{i}] phải là object.")
        vid = (v.get("id") or "").strip()
        url = (v.get("file_url") or "").strip()
        if not vid:
            raise ManifestError(f"videos[{i}] thiếu 'id'.")
        if not url:
            raise ManifestError(f"videos[{i}] (id={vid}) thiếu 'file_url'.")
        try:
            brief_id = v.get("brief_id")
            brief_id = int(brief_id) if brief_id is not None else None
        except (ValueError, TypeError):
            brief_id = None
        out.append(ManifestVideo(
            id=vid, file_url=url,
            project_code=(v.get("project_code") or "").strip().upper(),
            brief_id=brief_id,
            scene=(v.get("scene") or "").strip(),
            title=(v.get("title") or "").strip() or vid,
            description=(v.get("description") or "").strip(),
            hashtags=(v.get("hashtags") or "").strip(),
            duration=int(v.get("duration") or 10),
            ratio=(v.get("ratio") or "9:16").strip(),
            sha256=(v.get("sha256") or "").strip().lower(),
            created_at=(v.get("created_at") or "").strip(),
        ))
    return out


def new_videos(videos: list[ManifestVideo],
               seen_ids: set[str]) -> list[ManifestVideo]:
    """Lọc video chưa từng thấy (dedup theo id)."""
    return [v for v in videos if v.id not in seen_ids]


def fetch_manifest(url: str, etag: str = "",
                   last_modified: str = "",
                   timeout: int = 30) -> tuple[
                       list[ManifestVideo] | None, str, str]:
    """Tải manifest. Trả về (videos|None nếu 304, etag, last_modified).

    Raise ManifestError khi lỗi mạng hoặc JSON sai.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "MuseVideoStudio"})
    if etag:
        req.add_header("If-None-Match", etag)
    if last_modified:
        req.add_header("If-Modified-Since", last_modified)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 304:
                return None, etag, last_modified
            raw = resp.read()
            new_etag = resp.headers.get("ETag", "")
            new_lm = resp.headers.get("Last-Modified", "")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, etag, last_modified
        raise ManifestError(f"HTTP {e.code} khi tải manifest.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ManifestError(f"Không tải được manifest: {e}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise ManifestError(f"Manifest không phải JSON hợp lệ: {e}")
    return parse_manifest(payload), new_etag, new_lm


def download_file(url: str, dest_path: str,
                  progress_cb=None,
                  timeout: int = 180) -> str:
    """Tải file về dest_path (ghi .part rồi rename — atomic).

    progress_cb(downloaded_bytes, total_bytes|0). Trả về dest_path.
    Raise OSError/ManifestError khi lỗi.
    """
    tmp_path = dest_path + ".part"
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "MuseVideoStudio"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise ManifestError(f"Tải video thất bại: {e}")
    os.replace(tmp_path, dest_path)
    return dest_path


def verify_sha256(path: str, expected: str) -> bool:
    """Kiểm tra sha256 file. expected rỗng -> True (không kiểm)."""
    if not expected:
        return True
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest() == expected.lower()


def safe_filename(name: str) -> str:
    """Tên file an toàn cho Windows."""
    bad = '<>:"/\\|?*'
    out = "".join("_" if c in bad else c for c in (name or "")).strip()
    return out[:120] or "video"


class MailboxWorker(QThread):
    """Vòng poll manifest trong thread riêng, phát signal cho UI."""

    video_started = Signal(str)          # manifest_id
    video_progress = Signal(str, int)    # manifest_id, percent 0-100
    video_done = Signal(str, str)        # manifest_id, file_path
    video_failed = Signal(str, str)      # manifest_id, error
    poll_finished = Signal(int)          # số video mới trong lần poll này

    def __init__(self, manifest_url: str, dest_root: str,
                 poll_minutes: int = 15, auto_queue: bool = True,
                 parent=None) -> None:
        super().__init__(parent)
        self.manifest_url = manifest_url
        self.dest_root = dest_root
        self.poll_minutes = max(5, poll_minutes)
        self.auto_queue = auto_queue
        self._stop = False
        self._poll_now = False

    def stop(self) -> None:
        self._stop = True

    def request_poll(self) -> None:
        """Yêu cầu poll ngay (nút 'Kiểm tra ngay'), không chờ hết chu kỳ."""
        self._poll_now = True

    def run(self) -> None:
        while not self._stop:
            try:
                self.poll_once()
            except Exception:
                pass  # lỗi đã phát qua signal; không sập thread
            self._poll_now = False
            for _ in range(self.poll_minutes * 60 * 10):
                if self._stop or self._poll_now:
                    break
                time.sleep(0.1)

    def poll_once(self) -> int:
        """1 vòng poll. Trả về số video mới. Raise ManifestError nếu lỗi."""
        from app.core import db
        state = db.get_mailbox_state()
        url = self.manifest_url or state.get("manifest_url") or ""
        if not url:
            return 0
        try:
            seen = set(json.loads(state.get("last_seen_ids") or "[]"))
        except (ValueError, TypeError):
            seen = set()
        videos, etag, last_mod = fetch_manifest(
            url, state.get("etag") or "", state.get("last_modified") or "")
        if videos is None:  # 304 không đổi
            db.save_mailbox_state(last_poll_at=db.now_iso())
            self.poll_finished.emit(0)
            return 0
        fresh = new_videos(videos, seen)
        for v in fresh:
            if self._stop:
                break
            self._download_one(v, db)
            seen.add(v.id)
        db.save_mailbox_state(
            manifest_url=url, etag=etag, last_modified=last_mod,
            last_poll_at=db.now_iso(), last_seen_ids=seen)
        self.poll_finished.emit(len(fresh))
        return len(fresh)

    def _download_one(self, v: ManifestVideo, db) -> None:
        project = db.get_project_by_code(v.project_code) if v.project_code \
            else None
        subdir = (project["code"] if project
                  else (v.project_code or "Chung"))
        dest_dir = os.path.join(self.dest_root, safe_filename(subdir))
        dest = os.path.join(dest_dir,
                            safe_filename(f"{v.id}.mp4"))
        lid = db.upsert_library(
            v.id, project["id"] if project else None, v.brief_id,
            v.title, v.description, v.hashtags, v.duration, v.ratio)
        db.update_library(lid, status="downloading", progress=0, error="",
                          file_path=dest)
        self.video_started.emit(v.id)

        last_err = ""
        for attempt in range(1, MAX_RETRIES + 1):
            if self._stop:
                db.update_library(lid, status="paused")
                return
            try:
                def _cb(done, total, _vid=v.id, _lid=lid):
                    pct = int(done * 100 / total) if total else 0
                    db.update_library(_lid, progress=min(pct, 99))
                    self.video_progress.emit(_vid, min(pct, 99))

                download_file(v.file_url, dest, progress_cb=_cb)
                if not verify_sha256(dest, v.sha256):
                    raise ManifestError("File tải về sai checksum.")
                db.update_library(lid, status="done", progress=100,
                                  downloaded_at=db.now_iso())
                if v.brief_id:
                    try:
                        db.update_brief(v.brief_id, status="done")
                    except Exception:
                        pass
                self.video_done.emit(v.id, dest)
                if self.auto_queue:
                    self._auto_insert_queue(db, lid, dest, v)
                return
            except Exception as e:  # noqa: BLE001 - retry rồi báo lỗi
                last_err = str(e)
        db.update_library(lid, status="failed", error=last_err)
        self.video_failed.emit(v.id, last_err)

    def _auto_insert_queue(self, db, lid: int, dest: str,
                           v: ManifestVideo) -> None:
        """Chèn video mới vào hàng đợi đăng (scheduler xử lý tiếp)."""
        from app.core import config
        try:
            offset_min = int(config.get("auto_queue_offset_min", "60"))
        except ValueError:
            offset_min = 60
        from datetime import datetime, timedelta
        scheduled = (datetime.now() +
                     timedelta(minutes=max(5, offset_min)))
        combos = db.list_combos()
        combo_id = combos[0]["id"] if combos else None
        qid = db.add_queue(
            dest, v.title, v.description, v.hashtags,
            scheduled_at=scheduled.strftime("%Y-%m-%dT%H:%M:%S"),
            note=f"Tự động thêm từ mailbox ({v.id}).",
            combo_id=combo_id)
        db.set_targets(qid, {"youtube": True, "facebook": True,
                             "tiktok": True})
        db.add_log(qid, "", "info",
                   f"Tự động thêm vào hàng đợi đăng lúc "
                   f"{scheduled.strftime('%d/%m %H:%M')}.")
