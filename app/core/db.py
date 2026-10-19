"""SQLite storage cho Muse Video Studio.

DB nằm ở %APPDATA%/MuseVideoStudio/data.db trên Windows,
fallback ~/.muse-video-studio/data.db trên các hệ khác.

Mỗi hàm tự mở/đóng connection nên an toàn khi gọi từ nhiều thread.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    platform     TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    connected_at TEXT NOT NULL DEFAULT '',
    meta_json    TEXT NOT NULL DEFAULT '{}',
    UNIQUE(platform, label)
);
CREATE TABLE IF NOT EXISTS combos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS combo_members (
    combo_id   INTEGER NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
    platform   TEXT NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    UNIQUE(combo_id, platform)
);
CREATE TABLE IF NOT EXISTS queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path    TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    hashtags     TEXT NOT NULL DEFAULT '',
    scheduled_at TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    thumbnail_path TEXT NOT NULL DEFAULT '',
    combo_id     INTEGER REFERENCES combos(id) ON DELETE SET NULL,
    content_type TEXT NOT NULL DEFAULT 'video',
    image_paths  TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS queue_targets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id     INTEGER NOT NULL REFERENCES queue(id) ON DELETE CASCADE,
    platform     TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    status       TEXT NOT NULL DEFAULT 'pending',
    remote_id    TEXT,
    error        TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT,
    reminded     INTEGER NOT NULL DEFAULT 0,
    next_reminder_at TEXT,
    updated_at   TEXT NOT NULL,
    account_id   INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    UNIQUE(queue_id, platform)
);
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id   INTEGER,
    platform   TEXT NOT NULL DEFAULT '',
    level      TEXT NOT NULL DEFAULT 'info',
    message    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_targets_due
    ON queue_targets(platform, status, enabled, attempts);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at);
-- Muse Video Studio: bảng mới (giữ nguyên bảng cũ của SocialUploader)
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    code       TEXT NOT NULL UNIQUE,
    thumbnail  TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS briefs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    scene_no   INTEGER NOT NULL DEFAULT 1,
    scene_name TEXT NOT NULL DEFAULT '',
    tab        TEXT NOT NULL DEFAULT 'text',
    prompt     TEXT NOT NULL DEFAULT '',
    ratio      TEXT NOT NULL DEFAULT '9:16',
    duration   INTEGER NOT NULL DEFAULT 10,
    style      TEXT NOT NULL DEFAULT 'Cinematic',
    ref_images TEXT NOT NULL DEFAULT '[]',
    status     TEXT NOT NULL DEFAULT 'draft',
    exported_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS library (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    manifest_id  TEXT NOT NULL UNIQUE,
    project_id   INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    brief_id     INTEGER REFERENCES briefs(id) ON DELETE SET NULL,
    file_path    TEXT NOT NULL DEFAULT '',
    title        TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    hashtags     TEXT NOT NULL DEFAULT '',
    duration     INTEGER NOT NULL DEFAULT 10,
    ratio        TEXT NOT NULL DEFAULT '9:16',
    status       TEXT NOT NULL DEFAULT 'queued',
    progress     INTEGER NOT NULL DEFAULT 0,
    error        TEXT NOT NULL DEFAULT '',
    downloaded_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS mailbox (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    manifest_url  TEXT NOT NULL DEFAULT '',
    etag          TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    last_poll_at  TEXT NOT NULL DEFAULT '',
    last_seen_ids TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_library_status ON library(status);
CREATE INDEX IF NOT EXISTS idx_briefs_project ON briefs(project_id);
"""

VALID_STATUSES = {"pending", "uploading", "scheduled", "published", "draft", "failed"}


def get_db_dir() -> str:
    """Thư mục chứa database."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "MuseVideoStudio")
    else:
        path = os.path.join(os.path.expanduser("~"), ".muse-video-studio")
    os.makedirs(path, exist_ok=True)
    return path


def _legacy_db_path() -> str | None:
    """Đường dẫn data.db của app cũ (SocialUploader), nếu tồn tại."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        p = os.path.join(base, "SocialUploader", "data.db")
    else:
        p = os.path.join(os.path.expanduser("~"), ".social-uploader",
                         "data.db")
    return p if os.path.isfile(p) else None


def migrate_from_legacy() -> bool:
    """Lần đầu chạy: copy data.db của SocialUploader sang nếu chưa có DB mới.

    Trả về True nếu đã migrate (hoặc DB mới đã tồn tại — không cần làm gì).
    Tài khoản, combos, hàng đợi, lịch sử đăng của Khang được giữ nguyên.
    """
    new_path = os.path.join(get_db_dir(), "data.db")
    if os.path.isfile(new_path):
        return True
    legacy = _legacy_db_path()
    if not legacy:
        return True
    try:
        import shutil
        shutil.copy2(legacy, new_path)
        return True
    except OSError:
        return False


def get_db_path() -> str:
    override = (os.environ.get("MUSE_VIDEO_STUDIO_DB")
                or os.environ.get("SOCIAL_UPLOADER_DB"))  # fallback test cũ
    if override:
        path = os.path.abspath(override)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path
    migrate_from_legacy()
    return os.path.join(get_db_dir(), "data.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Thêm cột mới cho DB đã tạo từ phiên bản cũ."""
    qcols = {r[1] for r in
             conn.execute("PRAGMA table_info(queue)").fetchall()}
    if "thumbnail_path" not in qcols:
        conn.execute("ALTER TABLE queue ADD COLUMN "
                     "thumbnail_path TEXT NOT NULL DEFAULT ''")
    if "combo_id" not in qcols:
        conn.execute("ALTER TABLE queue ADD COLUMN "
                     "combo_id INTEGER REFERENCES combos(id) "
                     "ON DELETE SET NULL")
    if "content_type" not in qcols:
        conn.execute("ALTER TABLE queue ADD COLUMN "
                     "content_type TEXT NOT NULL DEFAULT 'video'")
    if "image_paths" not in qcols:
        conn.execute("ALTER TABLE queue ADD COLUMN "
                     "image_paths TEXT NOT NULL DEFAULT '[]'")
    tcols = {r[1] for r in
             conn.execute("PRAGMA table_info(queue_targets)").fetchall()}
    if "reminded" not in tcols:
        conn.execute("ALTER TABLE queue_targets ADD COLUMN "
                     "reminded INTEGER NOT NULL DEFAULT 0")
    if "next_reminder_at" not in tcols:
        conn.execute("ALTER TABLE queue_targets ADD COLUMN "
                     "next_reminder_at TEXT")
    if "account_id" not in tcols:
        conn.execute("ALTER TABLE queue_targets ADD COLUMN "
                     "account_id INTEGER REFERENCES accounts(id) "
                     "ON DELETE SET NULL")
    if "status" not in {r[1] for r in
                        conn.execute("PRAGMA table_info(accounts)").fetchall()}:
        # v1.8.0: "Ngắt kết nối" giữ lại tài khoản (tên/ID/token),
        # chỉ đánh dấu disconnected thay vì xóa dòng.
        conn.execute("ALTER TABLE accounts ADD COLUMN "
                     "status TEXT NOT NULL DEFAULT 'active'")
    _migrate_accounts(conn)
    _backfill_target_accounts(conn)


def _migrate_accounts(conn: sqlite3.Connection) -> None:
    """Chuyển bảng accounts cũ (platform làm PK) sang schema mới (id PK).

    Mỗi platform cũ thành 1 account riêng; token keyring được chuyển
    sang key per-account ở lần connect tiếp theo (giữ tương thích).
    """
    cols = {r[1]: r for r in
            conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "id" in cols:
        return  # đã là schema mới
    conn.execute("""
        CREATE TABLE accounts_new (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            platform     TEXT NOT NULL,
            label        TEXT NOT NULL DEFAULT '',
            connected_at TEXT NOT NULL DEFAULT '',
            meta_json    TEXT NOT NULL DEFAULT '{}',
            UNIQUE(platform, label)
        )
    """)
    for row in conn.execute(
            "SELECT platform, label, connected_at, meta_json FROM accounts"):
        label = row[1] or row[0]
        conn.execute(
            "INSERT INTO accounts_new(platform, label, connected_at, "
            "meta_json) VALUES(?, ?, ?, ?)",
            (row[0], label, row[2], row[3]))
    conn.execute("DROP TABLE accounts")
    conn.execute("ALTER TABLE accounts_new RENAME TO accounts")


def _backfill_target_accounts(conn: sqlite3.Connection) -> None:
    """Gán account_id cho target cũ: lấy account đầu tiên của platform đó."""
    rows = conn.execute(
        "SELECT id, platform FROM queue_targets "
        "WHERE account_id IS NULL").fetchall()
    if not rows:
        return
    acc_map: dict[str, int] = {}
    for (tid, platform) in rows:
        if platform not in acc_map:
            r = conn.execute(
                "SELECT id FROM accounts WHERE platform = ? "
                "ORDER BY id ASC LIMIT 1", (platform,)).fetchone()
            acc_map[platform] = r[0] if r else None
        if acc_map[platform]:
            conn.execute(
                "UPDATE queue_targets SET account_id = ? WHERE id = ?",
                (acc_map[platform], tid))


def init_db() -> None:
    """Tạo bảng nếu chưa có (migration đơn giản)."""
    with _connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _row_to_dict(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------- accounts
def add_account(platform: str, label: str,
                meta: dict | None = None) -> int:
    """Thêm tài khoản mới, trả về id. Label trùng trong cùng platform
    sẽ được đánh số tự động."""
    label = (label or "").strip() or platform
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    with _connect() as conn:
        base = label
        n = 2
        while conn.execute(
                "SELECT 1 FROM accounts WHERE platform = ? AND label = ?",
                (platform, label)).fetchone():
            label = f"{base} ({n})"
            n += 1
        cur = conn.execute(
            """INSERT INTO accounts(platform, label, connected_at, meta_json)
               VALUES(?, ?, ?, ?)""",
            (platform, label, now_iso(), meta_json),
        )
        return cur.lastrowid


def upsert_account(platform: str, label: str, meta: dict | None = None) -> None:
    """Giữ tương thích: cập nhật account đầu tiên của platform."""
    acc = get_account(platform)
    if acc:
        update_account(acc["id"], label=label, meta=meta)
    else:
        add_account(platform, label, meta)


def get_account(platform: str) -> dict | None:
    """Account đầu tiên của platform (tương thích code cũ)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE platform = ? ORDER BY id ASC "
            "LIMIT 1", (platform,)
        ).fetchone()
    return _account_dict(row)


def get_account_by_id(account_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return _account_dict(row)


def list_accounts(platform: str | None = None) -> list[dict]:
    with _connect() as conn:
        if platform:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE platform = ? ORDER BY id ASC",
                (platform,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM accounts ORDER BY platform, id ASC").fetchall()
    return [_account_dict(r) for r in rows]


def update_account(account_id: int, label: str | None = None,
                   meta: dict | None = None) -> None:
    sets, values = [], []
    if label is not None:
        sets.append("label = ?")
        values.append(label)
    if meta is not None:
        sets.append("meta_json = ?")
        values.append(json.dumps(meta, ensure_ascii=False))
    if not sets:
        return
    sets.append("connected_at = ?")
    values.append(now_iso())
    values.append(account_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE accounts SET {', '.join(sets)} WHERE id = ?", values)


def delete_account_by_id(account_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


def set_account_status(account_id: int, status: str) -> None:
    """'active' | 'disconnected'. Ngắt kết nối chỉ đổi status, giữ lại
    tên/ID/token để kết nối lại mà không nhập lại."""
    with _connect() as conn:
        conn.execute("UPDATE accounts SET status = ?, connected_at = ? "
                     "WHERE id = ?",
                     (status, now_iso(), account_id))


def account_is_active(account_id: int | None) -> bool:
    """Tài khoản có đang ở trạng thái active không.

    account_id None (target cũ) -> coi như active để tương thích.
    """
    if account_id is None:
        return True
    with _connect() as conn:
        row = conn.execute("SELECT status FROM accounts WHERE id = ?",
                           (account_id,)).fetchone()
    return row is None or (row[0] or "active") == "active"


def delete_account(platform: str) -> None:
    """Giữ tương thích: xóa mọi account của platform."""
    with _connect() as conn:
        conn.execute("DELETE FROM accounts WHERE platform = ?", (platform,))


def _account_dict(row) -> dict | None:
    d = _row_to_dict(row)
    if d:
        try:
            d["meta"] = json.loads(d.get("meta_json") or "{}")
        except (ValueError, TypeError):
            d["meta"] = {}
    return d


# ---------------------------------------------------------------- combos
def create_combo(name: str) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("Tên combo không được trống.")
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO combos(name, created_at) VALUES(?, ?)",
                (name, now_iso()))
        except sqlite3.IntegrityError:
            raise ValueError(f'Combo "{name}" đã tồn tại.')
        return cur.lastrowid


def rename_combo(combo_id: int, name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("Tên combo không được trống.")
    with _connect() as conn:
        try:
            conn.execute("UPDATE combos SET name = ? WHERE id = ?",
                         (name, combo_id))
        except sqlite3.IntegrityError:
            raise ValueError(f'Combo "{name}" đã tồn tại.')


def delete_combo(combo_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM combo_members WHERE combo_id = ?",
                     (combo_id,))
        conn.execute("DELETE FROM combos WHERE id = ?", (combo_id,))


def list_combos() -> list[dict]:
    """Kèm members: dict platform -> account dict."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM combos ORDER BY name ASC").fetchall()
        combos = [dict(r) for r in rows]
        for c in combos:
            mrows = conn.execute(
                """SELECT m.platform, a.id, a.label, a.meta_json
                   FROM combo_members m
                   JOIN accounts a ON a.id = m.account_id
                   WHERE m.combo_id = ?""", (c["id"],)).fetchall()
            members = {}
            for m in mrows:
                try:
                    meta = json.loads(m["meta_json"] or "{}")
                except (ValueError, TypeError):
                    meta = {}
                members[m["platform"]] = {
                    "id": m["id"], "label": m["label"], "meta": meta}
            c["members"] = members
    return combos


def get_combo(combo_id: int) -> dict | None:
    for c in list_combos():
        if c["id"] == combo_id:
            return c
    return None


def set_combo_members(combo_id: int,
                      members: dict[str, int | None]) -> None:
    """members: platform -> account_id (None = gỡ khỏi combo)."""
    with _connect() as conn:
        for platform, account_id in members.items():
            if account_id is None:
                conn.execute(
                    "DELETE FROM combo_members WHERE combo_id = ? "
                    "AND platform = ?", (combo_id, platform))
            else:
                conn.execute(
                    """INSERT INTO combo_members(combo_id, platform,
                                                 account_id)
                       VALUES(?, ?, ?)
                       ON CONFLICT(combo_id, platform) DO UPDATE SET
                         account_id=excluded.account_id""",
                    (combo_id, platform, account_id))


# ---------------------------------------------------------------- queue
def add_queue(file_path: str, title: str, description: str = "",
              hashtags: str = "", scheduled_at: str = "", note: str = "",
              thumbnail_path: str = "",
              combo_id: int | None = None,
              content_type: str = "video",
              image_paths: list[str] | None = None) -> int:
    if content_type not in ("video", "post"):
        raise ValueError(f"content_type không hợp lệ: {content_type}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO queue(file_path, title, description, hashtags,
                                 scheduled_at, created_at, note,
                                 thumbnail_path, combo_id, content_type,
                                 image_paths)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_path, title, description, hashtags,
             scheduled_at or now_iso(), now_iso(), note, thumbnail_path,
             combo_id, content_type,
             json.dumps(image_paths or [], ensure_ascii=False)),
        )
        return cur.lastrowid


def update_queue(queue_id: int, **fields) -> None:
    allowed = {"file_path", "title", "description", "hashtags",
               "scheduled_at", "note", "thumbnail_path", "combo_id",
               "content_type", "image_paths"}
    if "image_paths" in fields and isinstance(fields["image_paths"], list):
        fields = dict(fields)
        fields["image_paths"] = json.dumps(fields["image_paths"],
                                            ensure_ascii=False)
    sets = [f"{k} = ?" for k in fields if k in allowed]
    if not sets:
        return
    values = [fields[k] for k in fields if k in allowed]
    values.append(queue_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE queue SET {', '.join(sets)} WHERE id = ?", values)


def delete_queue(queue_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM queue_targets WHERE queue_id = ?", (queue_id,))
        conn.execute("DELETE FROM logs WHERE queue_id = ?", (queue_id,))
        conn.execute("DELETE FROM queue WHERE id = ?", (queue_id,))


def get_queue(queue_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM queue WHERE id = ?", (queue_id,)).fetchone()
    return _row_to_dict(row)


def list_queue() -> list[dict]:
    """Trả về queue kèm targets của từng item (dict platform -> target).

    Mỗi item có thêm 'combo_name' (tên combo nếu có).
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT q.*, c.name AS combo_name
               FROM queue q LEFT JOIN combos c ON c.id = q.combo_id
               ORDER BY q.scheduled_at ASC, q.id ASC""").fetchall()
        items = [dict(r) for r in rows]
        for item in items:
            trows = conn.execute(
                """SELECT t.*, a.label AS account_label
                   FROM queue_targets t
                   LEFT JOIN accounts a ON a.id = t.account_id
                   WHERE t.queue_id = ?""",
                (item["id"],)).fetchall()
            item["targets"] = {t["platform"]: dict(t) for t in trows}
    return items


# ---------------------------------------------------------------- targets
def set_targets(queue_id: int,
                platforms: dict[str, bool | tuple[bool, int | None]]) -> None:
    """Đồng bộ tick bật/tắt nền tảng cho 1 queue item.

    platforms: platform -> True/False, hoặc (enabled, account_id).
    """
    with _connect() as conn:
        for platform, spec in platforms.items():
            if isinstance(spec, tuple):
                enabled, account_id = spec
            else:
                enabled, account_id = spec, None
            if account_id is None:
                # tự lấy account đầu tiên của platform (tương thích cũ)
                r = conn.execute(
                    "SELECT id FROM accounts WHERE platform = ? "
                    "ORDER BY id ASC LIMIT 1", (platform,)).fetchone()
                account_id = r[0] if r else None
            conn.execute(
                """INSERT INTO queue_targets(queue_id, platform, enabled,
                                             account_id, updated_at)
                   VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(queue_id, platform) DO UPDATE SET
                     enabled=excluded.enabled,
                     account_id=excluded.account_id,
                     updated_at=excluded.updated_at""",
                (queue_id, platform, 1 if enabled else 0, account_id,
                 now_iso()),
            )


def update_target(target_id: int, **fields) -> None:
    allowed = {"enabled", "status", "remote_id", "error",
               "attempts", "next_retry_at", "reminded", "next_reminder_at"}
    if "status" in fields and fields["status"] not in VALID_STATUSES:
        raise ValueError(f"status không hợp lệ: {fields['status']}")
    sets = [f"{k} = ?" for k in fields if k in allowed]
    if not sets:
        return
    sets.append("updated_at = ?")
    values = [fields[k] for k in fields if k in allowed]
    values += [now_iso(), target_id]
    with _connect() as conn:
        conn.execute(
            f"UPDATE queue_targets SET {', '.join(sets)} WHERE id = ?", values)


def get_due_targets(now: str) -> list[dict]:
    """Các target đến giờ đăng: enabled, pending, attempts<5, quá giờ,
    và đã qua thời gian chờ retry (nếu có)."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.*, q.file_path, q.title, q.description, q.hashtags,
                      q.scheduled_at, q.thumbnail_path, q.content_type,
                      q.image_paths
               FROM queue_targets t
               JOIN queue q ON q.id = t.queue_id
               WHERE t.enabled = 1 AND t.status = 'pending'
                 AND t.attempts < 5
                 AND q.scheduled_at <= ?
                 AND (t.next_retry_at IS NULL OR t.next_retry_at <= ?)
               ORDER BY q.scheduled_at ASC""",
            (now, now)).fetchall()
    return [dict(r) for r in rows]


def get_pending_targets(now: str) -> list[dict]:
    """Các target chờ xử lý: enabled, pending, attempts<5, qua retry.

    KHÔNG lọc theo giờ hẹn — scheduler tự quyết theo từng nền tảng:
    nền tảng có native_scheduling thì upload ngay, còn lại chờ đến giờ.
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.*, q.file_path, q.title, q.description, q.hashtags,
                      q.scheduled_at, q.thumbnail_path, q.content_type,
                      q.image_paths
               FROM queue_targets t
               JOIN queue q ON q.id = t.queue_id
               WHERE t.enabled = 1 AND t.status = 'pending'
                 AND t.attempts < 5
                 AND (t.next_retry_at IS NULL OR t.next_retry_at <= ?)
               ORDER BY q.scheduled_at ASC""",
            (now,)).fetchall()
    return [dict(r) for r in rows]


def get_unreminded_tiktok_drafts(now: str) -> list[dict]:
    """Các video TikTok đã vào nháp mà chưa nhắc user đăng tay."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.id AS target_id, t.queue_id, q.title,
                      q.scheduled_at, q.thumbnail_path, q.content_type,
                      q.image_paths
               FROM queue_targets t
               JOIN queue q ON q.id = t.queue_id
               WHERE t.platform = 'tiktok' AND t.enabled = 1
                 AND t.status = 'draft' AND t.reminded = 0
                 AND (t.next_reminder_at IS NULL
                      OR t.next_reminder_at <= ?)
               ORDER BY q.scheduled_at ASC""",
            (now,)).fetchall()
    return [dict(r) for r in rows]


def reset_targets_for_repost(queue_id: int) -> None:
    """Đặt lại target (pending/failed) để đăng ngay."""
    with _connect() as conn:
        conn.execute(
            """UPDATE queue_targets
               SET status='pending', attempts=0, next_retry_at=NULL,
                   error=NULL, updated_at=?
               WHERE queue_id = ? AND enabled = 1
                 AND status IN ('pending', 'failed')""",
            (now_iso(), queue_id))


# ---------------------------------------------------------------- logs
def add_log(queue_id: int | None, platform: str, level: str,
            message: str) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO logs(queue_id, platform, level, message, created_at)
               VALUES(?, ?, ?, ?, ?)""",
            (queue_id, platform, level, message, now_iso()))


def get_logs(limit: int = 200) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_logs() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM logs")


# ------------------------------------------------- projects & briefs
BRIEF_STATUSES = {"draft", "sent", "rendering", "done"}
LIBRARY_STATUSES = {"queued", "downloading", "done", "failed", "paused"}


def create_project(name: str, code: str) -> int:
    """Tạo dự án mới. code duy nhất (dùng khớp với manifest)."""
    name = (name or "").strip()
    code = (code or "").strip().upper()
    if not name or not code:
        raise ValueError("Tên và mã dự án không được trống.")
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO projects(name, code, created_at) "
                "VALUES(?, ?, ?)",
                (name, code, now_iso()))
        except sqlite3.IntegrityError:
            raise ValueError(f"Mã dự án '{code}' đã tồn tại.")
        return cur.lastrowid


def list_projects() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM briefs b
                        WHERE b.project_id = p.id) AS scene_count
               FROM projects p ORDER BY p.id DESC""").fetchall()
    return [dict(r) for r in rows]


def get_project(pid: int) -> dict | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    return dict(r) if r else None


def get_project_by_code(code: str) -> dict | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM projects WHERE code = ?",
            ((code or "").strip().upper(),)).fetchone()
    return dict(r) if r else None


def delete_project(pid: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (pid,))


def create_brief(project_id: int, scene_no: int = 1,
                 scene_name: str = "", tab: str = "text",
                 prompt: str = "", ratio: str = "9:16",
                 duration: int = 10, style: str = "Cinematic",
                 ref_images: list[str] | None = None) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO briefs(project_id, scene_no, scene_name, tab,
                                  prompt, ratio, duration, style, ref_images,
                                  status)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
            (project_id, scene_no, scene_name, tab, prompt, ratio,
             duration, style,
             json.dumps(ref_images or [], ensure_ascii=False)))
        return cur.lastrowid


def list_briefs(project_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM briefs WHERE project_id = ? "
            "ORDER BY scene_no ASC, id ASC",
            (project_id,)).fetchall()
    return [dict(r) for r in rows]


def get_brief(bid: int) -> dict | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM briefs WHERE id = ?", (bid,)).fetchone()
    return dict(r) if r else None


def update_brief(bid: int, **fields) -> None:
    allowed = {"scene_no", "scene_name", "tab", "prompt", "ratio",
               "duration", "style", "ref_images", "status", "exported_at"}
    if "status" in fields and fields["status"] not in BRIEF_STATUSES:
        raise ValueError(f"status brief không hợp lệ: {fields['status']}")
    if "ref_images" in fields and isinstance(fields["ref_images"], list):
        fields = dict(fields)
        fields["ref_images"] = json.dumps(fields["ref_images"],
                                          ensure_ascii=False)
    sets = [f"{k} = ?" for k in fields if k in allowed]
    if not sets:
        return
    values = [fields[k] for k in fields if k in allowed]
    values.append(bid)
    with _connect() as conn:
        conn.execute(
            f"UPDATE briefs SET {', '.join(sets)} WHERE id = ?", values)


def delete_brief(bid: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM briefs WHERE id = ?", (bid,))


# ------------------------------------------------- library & mailbox
def upsert_library(manifest_id: str, project_id: int | None = None,
                   brief_id: int | None = None, title: str = "",
                   description: str = "", hashtags: str = "",
                   duration: int = 10, ratio: str = "9:16") -> int:
    """Thêm video từ manifest; đã tồn tại thì trả về id cũ (dedup)."""
    with _connect() as conn:
        r = conn.execute(
            "SELECT id FROM library WHERE manifest_id = ?",
            (manifest_id,)).fetchone()
        if r:
            return r[0]
        cur = conn.execute(
            """INSERT INTO library(manifest_id, project_id, brief_id, title,
                                   description, hashtags, duration, ratio,
                                   status)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'queued')""",
            (manifest_id, project_id, brief_id, title, description,
             hashtags, duration, ratio))
        return cur.lastrowid


def get_library_by_manifest(manifest_id: str) -> dict | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM library WHERE manifest_id = ?",
            (manifest_id,)).fetchone()
    return dict(r) if r else None


def list_library(status: str | None = None) -> list[dict]:
    with _connect() as conn:
        if status:
            rows = conn.execute(
                """SELECT l.*, p.name AS project_name, p.code AS project_code
                   FROM library l LEFT JOIN projects p
                     ON p.id = l.project_id
                   WHERE l.status = ? ORDER BY l.id DESC""",
                (status,)).fetchall()
        else:
            rows = conn.execute(
                """SELECT l.*, p.name AS project_name, p.code AS project_code
                   FROM library l LEFT JOIN projects p
                     ON p.id = l.project_id
                   ORDER BY l.id DESC""").fetchall()
    return [dict(r) for r in rows]


def update_library(lid: int, **fields) -> None:
    allowed = {"project_id", "brief_id", "file_path", "title",
               "description", "hashtags", "duration", "ratio", "status",
               "progress", "error", "downloaded_at"}
    if "status" in fields and fields["status"] not in LIBRARY_STATUSES:
        raise ValueError(
            f"status library không hợp lệ: {fields['status']}")
    sets = [f"{k} = ?" for k in fields if k in allowed]
    if not sets:
        return
    values = [fields[k] for k in fields if k in allowed]
    values.append(lid)
    with _connect() as conn:
        conn.execute(
            f"UPDATE library SET {', '.join(sets)} WHERE id = ?", values)


def count_library_by_status() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM library "
            "GROUP BY status").fetchall()
    out = {s: 0 for s in LIBRARY_STATUSES}
    for r in rows:
        out[r[0]] = r[1]
    return out


def get_mailbox_state() -> dict:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM mailbox ORDER BY id ASC LIMIT 1").fetchone()
        if not r:
            conn.execute("INSERT INTO mailbox DEFAULT VALUES")
            r = conn.execute(
                "SELECT * FROM mailbox ORDER BY id ASC LIMIT 1").fetchone()
    return dict(r)


def save_mailbox_state(**fields) -> None:
    allowed = {"manifest_url", "etag", "last_modified", "last_poll_at",
               "last_seen_ids"}
    if "last_seen_ids" in fields and isinstance(
            fields["last_seen_ids"], (list, set)):
        fields = dict(fields)
        fields["last_seen_ids"] = json.dumps(sorted(fields["last_seen_ids"]))
    sets = [f"{k} = ?" for k in fields if k in allowed]
    if not sets:
        return
    values = [fields[k] for k in fields if k in allowed]
    with _connect() as conn:
        r = conn.execute(
            "SELECT id FROM mailbox ORDER BY id ASC LIMIT 1").fetchone()
        if not r:
            conn.execute("INSERT INTO mailbox DEFAULT VALUES")
            r = conn.execute(
                "SELECT id FROM mailbox ORDER BY id ASC LIMIT 1").fetchone()
        conn.execute(
            f"UPDATE mailbox SET {', '.join(sets)} WHERE id = ?",
            values + [r[0]])
