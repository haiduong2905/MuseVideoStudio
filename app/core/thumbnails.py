"""Chuẩn hóa ảnh thumbnail theo quy định nền tảng.

YouTube: JPEG/PNG, tối đa 2MB (khuyên 1280x720).
Facebook video: tham số `thumb` nhận dữ liệu ảnh thô.
TikTok inbox: API không hỗ trợ đặt ảnh bìa -> bỏ qua.

Tự tách frame từ video làm ảnh bìa: dùng ffmpeg (ưu tiên imageio-ffmpeg
đóng gói sẵn trong app, fallback sang ffmpeg của hệ thống).
"""
import os
import re
import shutil
import subprocess
import uuid

MAX_W, MAX_H = 1280, 720
MAX_BYTES = 2 * 1024 * 1024  # giới hạn của YouTube
ACCEPT_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
CANDIDATE_COUNT = 8


def get_thumb_dir() -> str:
    from app.core import db
    path = os.path.join(os.path.dirname(db.get_db_path()), "thumbs")
    os.makedirs(path, exist_ok=True)
    return path


def persist_candidate(src_path: str) -> str:
    """Copy ảnh ứng viên user đã CHỌN vào thư mục bền vững của app.

    File tạm của dải ứng viên sẽ bị xóa khi tách frame cho video khác,
    nên ảnh đã chọn phải được copy ra chỗ riêng. Trả về đường dẫn mới.
    Dọn luôn file trong thư mục quá 30 ngày để khỏi phình.
    """
    import time
    dest_dir = get_thumb_dir()
    cutoff = time.time() - 30 * 86400
    for name in os.listdir(dest_dir):
        p = os.path.join(dest_dir, name)
        try:
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
        except OSError:
            pass
    ext = os.path.splitext(src_path)[1].lower() or ".jpg"
    dst = os.path.join(dest_dir, f"{uuid.uuid4().hex}{ext}")
    shutil.copy2(src_path, dst)
    return dst


def discard_persisted(path: str) -> None:
    """Xóa file ảnh đã persist khi user bỏ chọn (chỉ xóa trong thumbs/)."""
    try:
        if not path:
            return
        tdir = os.path.abspath(get_thumb_dir())
        apath = os.path.abspath(path)
        if apath.startswith(tdir + os.sep) and os.path.isfile(apath):
            os.remove(apath)
    except OSError:
        pass


def prepare_thumbnail(src_path: str, dest_name: str | None = None) -> str:
    """Copy + chuẩn hóa ảnh về JPEG <=2MB, vừa khung 1280x720.

    Trả về đường dẫn file đã chuẩn hóa trong thư mục thumbs của app.
    Raise ValueError nếu file không phải ảnh hợp lệ.
    """
    from PIL import Image

    if not os.path.isfile(src_path):
        raise ValueError("Không tìm thấy file ảnh.")
    try:
        img = Image.open(src_path)
        img.load()
    except Exception as exc:
        raise ValueError(f"File không phải ảnh hợp lệ: {exc}")

    img = img.convert("RGB")
    img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

    dest = os.path.join(get_thumb_dir(),
                        dest_name or f"{uuid.uuid4().hex}.jpg")
    quality = 88
    while True:
        img.save(dest, "JPEG", quality=quality, optimize=True)
        if os.path.getsize(dest) <= MAX_BYTES or quality <= 40:
            break
        quality -= 12
    if os.path.getsize(dest) > MAX_BYTES:
        # ảnh quá phức tạp: giảm kích thước một nửa rồi thử lại
        img.thumbnail((MAX_W // 2, MAX_H // 2), Image.LANCZOS)
        img.save(dest, "JPEG", quality=60, optimize=True)
    return dest


def describe_rules() -> str:
    return ("Ảnh bìa áp dụng cho YouTube (chuẩn 1280×720, ≤2MB, app tự "
            "chuẩn hóa) và Facebook. TikTok (chế độ nháp) không hỗ trợ đặt "
            "ảnh bìa qua API — anh chọn trong app TikTok lúc đăng tay.")


# ------------------------------------------------- tách frame từ video
def _ffmpeg_exe() -> str | None:
    """Đường dẫn ffmpeg: ưu tiên bản đóng gói trong app."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


def ffmpeg_available() -> bool:
    return _ffmpeg_exe() is not None


# Trên Windows: ẩn cửa sổ cmd khi gọi ffmpeg (nếu không mỗi lần tách
# frame lại nháy 1 cửa sổ console).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_ffmpeg(args: list, **kwargs):
    return subprocess.run(args, creationflags=_NO_WINDOW, **kwargs)


def _video_duration(ffmpeg: str, video_path: str) -> float:
    """Đọc thời lượng video (giây) từ stderr của `ffmpeg -i`."""
    try:
        proc = _run_ffmpeg(
            [ffmpeg, "-i", video_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Không đọc được video: {exc}")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)",
                  proc.stderr.decode("utf-8", "replace"))
    if not m:
        raise ValueError("Không xác định được thời lượng video.")
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


def _is_too_dark(jpg_path: str, threshold: float = 18.0) -> bool:
    """True nếu frame gần như đen (tránh chọn frame chuyển cảnh)."""
    try:
        from PIL import Image, ImageStat
        img = Image.open(jpg_path).convert("L").resize((64, 36))
        return ImageStat.Stat(img).mean[0] < threshold
    except Exception:
        return False


def extract_candidates(video_path: str,
                       count: int = CANDIDATE_COUNT) -> list[str]:
    """Tách `count` frame rải đều video làm ứng viên ảnh bìa.

    Trả về list đường dẫn JPEG trong thư mục tạm (chưa chuẩn hóa —
    gọi prepare_thumbnail() khi user chốt 1 ảnh).
    Raise ValueError nếu không tách được.
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        raise ValueError("Không tìm thấy ffmpeg để tách frame.")
    if not os.path.isfile(video_path):
        raise ValueError("Không tìm thấy file video.")
    duration = _video_duration(ffmpeg, video_path)
    if duration < 1:
        raise ValueError("Video quá ngắn để tách frame.")

    out_dir = os.path.join(get_thumb_dir(),
                           f"cand_{uuid.uuid4().hex[:8]}")
    os.makedirs(out_dir, exist_ok=True)
    results: list[str] = []
    for i in range(1, count + 1):
        # rải đều, bỏ 5% đầu/cuối (thường là intro đen hoặc outro)
        t = duration * (0.05 + 0.90 * i / (count + 1))
        out = os.path.join(out_dir, f"frame_{i:02d}.jpg")
        ok = False
        for attempt in (t, min(t + 1.0, duration * 0.98)):
            try:
                _run_ffmpeg(
                    [ffmpeg, "-y", "-v", "error",
                     "-ss", f"{attempt:.2f}", "-i", video_path,
                     "-frames:v", "1", "-q:v", "4", out],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=60, check=True)
            except (OSError, subprocess.SubprocessError):
                continue
            if os.path.isfile(out) and not _is_too_dark(out):
                ok = True
                break
            # frame quá tối: thử mốc tiếp theo, nếu vẫn tối thì lấy luôn
            # (đỡ hơn là thiếu ảnh)
            if os.path.isfile(out):
                ok = True
                break
        if ok:
            results.append(out)
    if not results:
        raise ValueError("Không tách được frame nào từ video.")
    return results


def cleanup_candidates(paths: list[str]) -> None:
    """Xóa file ứng viên tạm (sau khi user đã chốt hoặc hủy)."""
    seen_dirs = set()
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
                seen_dirs.add(os.path.dirname(p))
        except OSError:
            pass
    for d in seen_dirs:
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except OSError:
            pass
