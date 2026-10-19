"""Cấu hình nhẹ (JSON) lưu trong thư mục dữ liệu của app.

Dùng để nhớ các lựa chọn của user như khung giờ xếp lịch nhanh,
không dùng cho secret (secret nằm ở keyring).
"""
import json
import os

DEFAULTS = {
    # Khung giờ xếp lịch nhanh, cách nhau bởi dấu phẩy
    "quick_slots": "07:00, 11:30, 15:30, 19:00, 21:30",
}


def _path() -> str:
    from app.core import db
    return os.path.join(os.path.dirname(db.get_db_path()), "config.json")


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    return cfg


def save(patch: dict) -> None:
    cfg = load()
    cfg.update(patch)
    try:
        with open(_path(), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def get(key: str, default: str = "") -> str:
    return str(load().get(key, default))
