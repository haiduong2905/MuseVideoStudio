"""Test cho tính năng combo kênh + multi-account.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="su_test_combo_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

from app.core import db  # noqa: E402
from app.platforms import get_platform, native_scheduling  # noqa: E402


class TestAccounts(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_add_and_list(self):
        a1 = db.add_account("youtube", "Kênh Serene")
        a2 = db.add_account("youtube", "Kênh BeastBytes")
        self.assertNotEqual(a1, a2)
        accs = db.list_accounts("youtube")
        labels = [a["label"] for a in accs]
        self.assertIn("Kênh Serene", labels)
        self.assertIn("Kênh BeastBytes", labels)

    def test_duplicate_label_auto_numbered(self):
        db.add_account("facebook", "Page A")
        a2 = db.add_account("facebook", "Page A")
        acc = db.get_account_by_id(a2)
        self.assertEqual(acc["label"], "Page A (2)")

    def test_get_update_delete(self):
        aid = db.add_account("tiktok", "TT Test",
                             meta={"note": "x"})
        acc = db.get_account_by_id(aid)
        self.assertEqual(acc["platform"], "tiktok")
        self.assertEqual(acc["meta"]["note"], "x")
        db.update_account(aid, label="TT Mới")
        self.assertEqual(db.get_account_by_id(aid)["label"], "TT Mới")
        db.delete_account_by_id(aid)
        self.assertIsNone(db.get_account_by_id(aid))

    def test_legacy_get_account(self):
        db.add_account("youtube", "Kênh Cũ")
        acc = db.get_account("youtube")
        self.assertIsNotNone(acc)
        self.assertEqual(acc["platform"], "youtube")


class TestCombos(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.yt1 = db.add_account("youtube", "YT Serene")
        self.yt2 = db.add_account("youtube", "YT Beast")
        self.fb1 = db.add_account("facebook", "FB Serene")

    def test_create_list_delete(self):
        cid = db.create_combo("Serene")
        combos = db.list_combos()
        self.assertTrue(any(c["name"] == "Serene" for c in combos))
        # trùng tên -> lỗi
        with self.assertRaises(ValueError):
            db.create_combo("Serene")
        db.delete_combo(cid)
        self.assertFalse(any(c["id"] == cid for c in db.list_combos()))

    def test_members(self):
        cid = db.create_combo("BeastBytes")
        db.set_combo_members(cid, {"youtube": self.yt2,
                                   "facebook": self.fb1,
                                   "tiktok": None})
        combo = db.get_combo(cid)
        self.assertEqual(combo["members"]["youtube"]["id"], self.yt2)
        self.assertEqual(combo["members"]["facebook"]["id"], self.fb1)
        self.assertNotIn("tiktok", combo["members"])
        # gỡ youtube khỏi combo
        db.set_combo_members(cid, {"youtube": None})
        combo = db.get_combo(cid)
        self.assertNotIn("youtube", combo["members"])

    def test_rename(self):
        cid = db.create_combo("Tên Cũ")
        db.rename_combo(cid, "Tên Mới")
        self.assertEqual(db.get_combo(cid)["name"], "Tên Mới")


class TestQueueWithCombo(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.yt = db.add_account("youtube", "YT 1")
        self.fb = db.add_account("facebook", "FB 1")
        self.cid = db.create_combo("Combo Test")
        db.set_combo_members(self.cid, {"youtube": self.yt,
                                        "facebook": self.fb})

    def test_add_queue_with_combo_and_targets(self):
        qid = db.add_queue("/tmp/a.mp4", "Tiêu đề",
                           scheduled_at="2030-01-01T10:00:00",
                           combo_id=self.cid)
        db.set_targets(qid, {"youtube": (True, self.yt),
                             "facebook": (True, self.fb),
                             "tiktok": (False, None)})
        items = db.list_queue()
        item = [i for i in items if i["id"] == qid][0]
        self.assertEqual(item["combo_name"], "Combo Test")
        tg = item["targets"]
        self.assertEqual(tg["youtube"]["account_id"], self.yt)
        self.assertEqual(tg["youtube"]["account_label"], "YT 1")
        self.assertEqual(tg["facebook"]["account_id"], self.fb)
        self.assertEqual(tg["tiktok"]["enabled"], 0)


class TestPlatformFactory(unittest.TestCase):
    def test_per_account_keys(self):
        for plat, prefix in [("youtube", "youtube_token_json"),
                             ("facebook", "facebook_token_json"),
                             ("tiktok", "tiktok_token_json")]:
            p = get_platform(plat, account_id=7)
            self.assertEqual(p.account_id, 7)
            self.assertTrue(p._token_key().endswith("_7"),
                            f"{plat}: {p._token_key()}")
            p0 = get_platform(plat)
            self.assertEqual(p0._token_key(), prefix)

    def test_native_scheduling(self):
        self.assertTrue(native_scheduling("youtube"))
        self.assertTrue(native_scheduling("facebook"))
        self.assertFalse(native_scheduling("tiktok"))


class TestMigration(unittest.TestCase):
    """Giả lập DB cũ (accounts PK=platform) -> migrate sang schema mới."""

    def test_migrate_old_accounts(self):
        import sqlite3
        path = os.path.join(_tmp, "mig.db")
        if os.path.exists(path):
            os.remove(path)
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE accounts (
            platform TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT '',
            connected_at TEXT NOT NULL DEFAULT '', meta_json TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO accounts VALUES('youtube','Kênh X','2026-01-01','{}')")
        conn.execute(
            "INSERT INTO accounts VALUES('facebook','Page Y','2026-01-01','{}')")
        conn.commit()
        conn.close()
        os.environ["SOCIAL_UPLOADER_DB"] = path
        db.init_db()
        accs = db.list_accounts()
        self.assertEqual(len(accs), 2)
        self.assertTrue(all("id" in a for a in accs))
        # khôi phục DB test chính
        os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")


if __name__ == "__main__":
    unittest.main()
