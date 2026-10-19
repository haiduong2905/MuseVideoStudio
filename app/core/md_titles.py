"""Đọc file md tiêu đề/caption do assistant tổng hợp và tra theo tên file video.

Hỗ trợ cả 2 định dạng đang dùng:
  1. BeastBytes (titles-captions.md):
        ## 1. Tyrannosaurus Rex
        - File: `final/v1-trex.mp4`
        - Caption: ...
        - Hashtags: #beastbytes ...
     -> title lấy từ tiêu đề mục (## N. Tên).
  2. Video thiên nhiên (tieu-de-tieng-anh.md):
        ## 1. Tropical Island — `2026-10-14_dao.mp4` (đã đăng)
        - **Title:** A Tropical Jewel from Above
        - **Caption:** ...
        - **Hashtags:** #...
     -> title/caption/hashtag lấy từ các dòng - **X:** ...
"""
import os
import re

_ENTRY_RE = re.compile(r"^##\s+(.*)$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
# dòng field: "- Label: value" hoặc "- **Label:** value"
_FIELD_RE = re.compile(r"^-\s+(?:\*\*(.+?)\*\*|([^:*]+))\s*:?\s*(.*)$")
_LABELS = {"file", "title", "caption", "hashtags"}


def _clean_header_title(header: str) -> str:
    """'1. Tyrannosaurus Rex' -> 'Tyrannosaurus Rex';
    '1. Tropical Island — `f.mp4` (đã đăng)' -> 'Tropical Island'."""
    t = _BACKTICK_RE.sub("", header).strip()
    t = re.sub(r"^\(.*?\)\s*", "", t).strip()      # (đã đăng) ở đầu
    t = re.sub(r"\s*\(.*?\)\s*$", "", t).strip()    # (đã đăng) ở cuối
    t = re.split(r"\s+[—–-]\s+", t)[0].strip()     # cắt sau dấu gạch
    t = re.sub(r"^\d+\.\s*", "", t)                # bỏ số thứ tự
    return t.strip()


def parse_md(path: str) -> dict[str, dict[str, str]]:
    """Đọc md -> {basename_lower: {'title','caption','hashtags'}}.

    Raise FileNotFoundError / UnicodeDecodeError khi file lỗi.
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    entries: list[dict] = []
    cur: dict | None = None
    cur_label: str | None = None

    def flush() -> None:
        if cur is not None:
            entries.append(cur)

    for raw in lines:
        line = raw.strip()
        m = _ENTRY_RE.match(line)
        if m:
            flush()
            cur = {"header": m.group(1).strip(), "fields": {}}
            cur_label = None
            continue
        if cur is None:
            continue
        fm = _FIELD_RE.match(line)
        if fm:
            label = (fm.group(1) or fm.group(2) or "").strip().lower()
            label = label.rstrip(":").strip()  # "**Title:**" -> "title"
            value = (fm.group(3) or "").strip()
            if label in _LABELS:
                cur["fields"][label] = value
                cur_label = label
            else:
                cur_label = None  # vd "Text on video:" -> bỏ qua
            continue
        # dòng nối tiếp (caption dài / text on video nhiều dòng)
        if line and cur_label and not line.startswith(("#", ">", "---")):
            cur["fields"][cur_label] += " " + line

    flush()

    out: dict[str, dict[str, str]] = {}
    for e in entries:
        fields = e["fields"]
        # tìm tên file: ưu tiên dòng - File:, rồi tới `...` trong header
        fname = ""
        if fields.get("file"):
            fname = _BACKTICK_RE.search(fields["file"])
            fname = fname.group(1) if fname else fields["file"]
        else:
            bt = _BACKTICK_RE.search(e["header"])
            fname = bt.group(1) if bt else ""
        fname = os.path.basename(fname.strip().strip("`"))
        if not fname:
            continue
        title = fields.get("title") or _clean_header_title(e["header"])
        out[fname.lower()] = {
            "title": title,
            "caption": fields.get("caption", ""),
            "hashtags": fields.get("hashtags", ""),
        }
    return out


def lookup(video_path: str,
           entries: dict[str, dict[str, str]]) -> dict[str, str] | None:
    """Tra thông tin theo tên file video (không phân biệt hoa/thường)."""
    return entries.get(os.path.basename(video_path).lower())


def fill_video(video: dict, entries: dict[str, dict[str, str]]) -> bool:
    """Điền title/description/hashtags vào dict video nếu khớp tên file.

    Trả về True khi khớp. Chỉ ghi đè trường đang trống, trừ khi
    video['__overwrite__'] = True.
    """
    info = lookup(video.get("file_path", ""), entries)
    if not info:
        return False
    overwrite = bool(video.pop("__overwrite__", False))
    if overwrite or not video.get("title"):
        video["title"] = info["title"][:100]
    if overwrite or not video.get("description"):
        video["description"] = info["caption"]
    if overwrite or not video.get("hashtags"):
        video["hashtags"] = info["hashtags"]
    return True
