"""Brief chuẩn: app xuất -> Khang paste vào khung chat -> assistant dựng.

Định dạng (design doc mục 6):
    [BRIEF] Mã dự án: <code> | Cảnh: <n> | Ngày: <yyyy-mm-dd>
    Loại: <text/ảnh/video/template>
    Tỉ lệ: <9:16> | Thời lượng: <10s> | Style: <Cinematic>
    Mô tả: <prompt đầy đủ>
    Text trên video: <nội dung / không>
    Nhạc: <mô tả vibe / không>
    Ảnh tham chiếu: <số lượng> (đính kèm khi paste)
    Ghi chú: <tùy chọn>
"""
from dataclasses import dataclass, field
from datetime import date

TAB_LABELS = {
    "text": "text",
    "image": "ảnh",
    "video": "video",
    "template": "template",
}


@dataclass
class Brief:
    project_code: str
    scene_no: int = 1
    scene_name: str = ""
    tab: str = "text"          # text | image | video | template
    prompt: str = ""
    ratio: str = "9:16"
    duration: int = 10         # giây
    style: str = "Cinematic"
    ref_count: int = 0
    onscreen_text: str = ""    # text trên video, "" = không
    music: str = ""            # mô tả nhạc, "" = không
    note: str = ""
    day: str = ""              # yyyy-mm-dd, mặc định hôm nay

    def __post_init__(self) -> None:
        self.project_code = (self.project_code or "").strip().upper()
        if not self.project_code:
            raise ValueError("Mã dự án không được trống.")
        if not self.prompt.strip():
            raise ValueError("Mô tả (prompt) không được trống.")
        if self.tab not in TAB_LABELS:
            raise ValueError(f"Loại brief không hợp lệ: {self.tab}")
        if not self.day:
            self.day = date.today().isoformat()


def build_brief_text(b: Brief) -> str:
    """Dựng text brief chuẩn để Khang copy/paste vào chat."""
    tab_label = TAB_LABELS[b.tab]
    scene = f"Cảnh {b.scene_no}"
    if b.scene_name.strip():
        scene += f" — {b.scene_name.strip()}"
    lines = [
        f"[BRIEF] Mã dự án: {b.project_code} | {scene} | Ngày: {b.day}",
        f"Loại: {tab_label}",
        f"Tỉ lệ: {b.ratio} | Thời lượng: {b.duration}s | Style: {b.style}",
        f"Mô tả: {b.prompt.strip()}",
        f"Text trên video: {b.onscreen_text.strip() or 'không'}",
        f"Nhạc: {b.music.strip() or 'không'}",
        f"Ảnh tham chiếu: {b.ref_count} "
        f"{'(đính kèm khi paste)' if b.ref_count else ''}".rstrip(),
    ]
    if b.note.strip():
        lines.append(f"Ghi chú: {b.note.strip()}")
    return "\n".join(lines)


def brief_from_db_row(row: dict, project_code: str,
                      ref_images: list | None = None) -> Brief:
    """Dựng Brief từ 1 dòng bảng briefs (ref_images là JSON đã parse)."""
    refs = ref_images if ref_images is not None else []
    try:
        import json
        raw = row.get("ref_images") or "[]"
        refs = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        refs = []
    return Brief(
        project_code=project_code,
        scene_no=row.get("scene_no") or 1,
        scene_name=row.get("scene_name") or "",
        tab=row.get("tab") or "text",
        prompt=row.get("prompt") or "",
        ratio=row.get("ratio") or "9:16",
        duration=row.get("duration") or 10,
        style=row.get("style") or "Cinematic",
        ref_count=len(refs),
    )
