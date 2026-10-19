"""Integration test: MailboxWorker.poll_once với manifest file:// local.

Mô phỏng trọn vòng Plan B: fetch manifest -> parse -> dedup -> tải file
-> ghi library -> tự chèn vào hàng đợi đăng.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="mvs_test_worker_")
_TEST_DB = os.path.join(_tmp, "data.db")


def setUpModule():
    os.environ["MUSE_VIDEO_STUDIO_DB"] = _TEST_DB


def tearDownModule():
    os.environ.pop("MUSE_VIDEO_STUDIO_DB", None)


from PySide6.QtCore import QCoreApplication  # noqa: E402

from app.core import db  # noqa: E402
from app.core.mailbox import MailboxWorker  # noqa: E402

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QCoreApplication([])


class TestPollOnce(unittest.TestCase):
    def setUp(self):
        _ensure_app()
        db.init_db()
        self.workdir = tempfile.mkdtemp(prefix="mvs_manifest_")
        # id duy nhất theo tên test để các test độc lập nhau
        self.vid = "bb-" + self._testMethodName.replace("_", "-")
        # file video giả
        self.video_src = os.path.join(self.workdir, "v1.mp4")
        with open(self.video_src, "wb") as f:
            f.write(b"FAKEVIDEO" * 1000)
        manifest = {
            "updated_at": "2026-10-19T15:00:00+07:00",
            "videos": [{
                "id": self.vid,
                "project_code": "BEASTBYTES",
                "title": "Video test",
                "description": "Mô tả",
                "hashtags": "#beastbytes",
                "duration": 10,
                "ratio": "9:16",
                "file_url": "file://" + self.video_src,
            }],
        }
        self.manifest_path = os.path.join(self.workdir, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        if not db.get_project_by_code("BEASTBYTES"):
            db.create_project("BeastBytes", "BEASTBYTES")

    def _worker(self):
        return MailboxWorker(
            "file://" + self.manifest_path,
            os.path.join(self.workdir, "out"),
            poll_minutes=5, auto_queue=True)

    def test_poll_tai_va_tu_chen_queue(self):
        w = self._worker()
        n = w.poll_once()
        self.assertEqual(n, 1)
        row = db.get_library_by_manifest(self.vid)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "done")
        self.assertTrue(os.path.isfile(row["file_path"]))
        # file nằm trong thư mục mã dự án
        self.assertIn("BEASTBYTES", row["file_path"])
        # tự chèn vào hàng đợi đăng
        q = db.list_queue()
        mine = [x for x in q if self.vid in (x.get("note") or "")]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["title"], "Video test")

    def test_poll_lan_2_khong_tai_lai(self):
        w = self._worker()
        self.assertEqual(w.poll_once(), 1)
        w2 = self._worker()
        self.assertEqual(w2.poll_once(), 0)  # dedup theo id

    def test_khong_co_url_tra_ve_0(self):
        w = MailboxWorker("", os.path.join(self.workdir, "out"))
        db.save_mailbox_state(manifest_url="")
        self.assertEqual(w.poll_once(), 0)


if __name__ == "__main__":
    unittest.main()
