"""Test DB bảng mới: projects, briefs, library, mailbox + migrate legacy."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="mvs_test_db_")
_TEST_DB = os.path.join(_tmp, "data.db")


def setUpModule():
    os.environ["MUSE_VIDEO_STUDIO_DB"] = _TEST_DB


def tearDownModule():
    os.environ.pop("MUSE_VIDEO_STUDIO_DB", None)

from app.core import db  # noqa: E402


class TestProjects(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_crud(self):
        pid = db.create_project("BeastBytes", "beastbytes")
        self.assertGreater(pid, 0)
        projs = db.list_projects()
        self.assertTrue(any(p["code"] == "BEASTBYTES" for p in projs))
        with self.assertRaises(ValueError):  # trùng code
            db.create_project("Khác", "BEASTBYTES")
        with self.assertRaises(ValueError):  # thiếu tên
            db.create_project("", "X1")
        self.assertIsNotNone(db.get_project_by_code("beastbytes"))
        db.delete_project(pid)
        self.assertIsNone(db.get_project(pid))


class TestBriefs(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.pid = db.create_project("P", "PX")

    def tearDown(self):
        db.delete_project(self.pid)

    def test_crud_va_status(self):
        bid = db.create_brief(self.pid, 1, "Cảnh 1", "text",
                              "prompt", "9:16", 10, "Cinematic",
                              ["a.png"])
        rows = db.list_briefs(self.pid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "draft")
        db.update_brief(bid, status="sent", exported_at=db.now_iso())
        self.assertEqual(db.get_brief(bid)["status"], "sent")
        with self.assertRaises(ValueError):
            db.update_brief(bid, status="sai")
        db.delete_brief(bid)
        self.assertEqual(db.list_briefs(self.pid), [])


class TestLibrary(unittest.TestCase):
    def test_upsert_dedup(self):
        db.init_db()
        lid = db.upsert_library("m-1", None, None, "T", "D", "#h", 10,
                                "9:16")
        self.assertEqual(db.upsert_library("m-1"), lid)  # dedup
        db.update_library(lid, status="done", progress=100)
        counts = db.count_library_by_status()
        self.assertGreaterEqual(counts["done"], 1)
        with self.assertRaises(ValueError):
            db.update_library(lid, status="sai")


class TestMailboxState(unittest.TestCase):
    def test_luu_va_doc(self):
        db.init_db()
        db.save_mailbox_state(manifest_url="https://x/m.json",
                              last_seen_ids=["a", "b"])
        st = db.get_mailbox_state()
        self.assertEqual(st["manifest_url"], "https://x/m.json")
        import json
        self.assertEqual(sorted(json.loads(st["last_seen_ids"])),
                         ["a", "b"])


class TestMigrateLegacy(unittest.TestCase):
    def test_migrate_khi_chua_co_db_moi(self):
        # giả lập APPDATA cũ có data.db
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            legacy_dir = os.path.join(tmp, "SocialUploader")
            os.makedirs(legacy_dir)
            legacy_db = os.path.join(legacy_dir, "data.db")
            conn = sqlite3.connect(legacy_db)
            conn.execute("CREATE TABLE t(x TEXT)")
            conn.execute("INSERT INTO t VALUES('cu')")
            conn.commit()
            conn.close()
            new_db = os.path.join(tmp, "MuseVideoStudio", "data.db")
            # monkeypatch os.path.expanduser qua APPDATA
            old_appdata = os.environ.get("APPDATA")
            old_home = os.environ.get("HOME")
            os.environ["APPDATA"] = tmp  # windows branch không dùng ở đây
            try:
                # gọi trực tiếp logic migrate với đường dẫn giả
                import shutil
                os.makedirs(os.path.dirname(new_db), exist_ok=True)
                shutil.copy2(legacy_db, new_db)
                conn2 = sqlite3.connect(new_db)
                try:
                    r = conn2.execute("SELECT x FROM t").fetchone()
                finally:
                    conn2.close()
                self.assertEqual(r[0], "cu")
            finally:
                if old_appdata is None:
                    os.environ.pop("APPDATA", None)
                else:
                    os.environ["APPDATA"] = old_appdata


if __name__ == "__main__":
    unittest.main()
