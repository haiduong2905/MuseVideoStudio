"""Test persist_candidate / discard_persisted (không cần Qt)."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="su_test_persist_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

from app.core.thumbnails import (discard_persisted, get_thumb_dir,  # noqa: E402
                                 persist_candidate)


class TestPersistCandidate(unittest.TestCase):
    def test_persist_and_discard(self):
        src = os.path.join(_tmp, "src.jpg")
        with open(src, "wb") as fh:
            fh.write(b"\xff\xd8\xff" + b"x" * 100)
        dst = persist_candidate(src)
        self.assertTrue(os.path.isfile(dst))
        self.assertTrue(os.path.abspath(dst).startswith(
            os.path.abspath(get_thumb_dir())))
        self.assertNotEqual(os.path.abspath(dst), os.path.abspath(src))
        # file gốc vẫn còn (chỉ copy)
        self.assertTrue(os.path.isfile(src))
        discard_persisted(dst)
        self.assertFalse(os.path.exists(dst))

    def test_discard_ignores_outside(self):
        outside = os.path.join(_tmp, "outside.jpg")
        with open(outside, "wb") as fh:
            fh.write(b"data")
        discard_persisted(outside)  # không được xóa file ngoài thumbs/
        self.assertTrue(os.path.isfile(outside))
        discard_persisted("")
        discard_persisted(None)

    def test_cleanup_old_files(self):
        old = os.path.join(get_thumb_dir(), "old_thumb.jpg")
        with open(old, "wb") as fh:
            fh.write(b"old")
        ancient = time.time() - 31 * 86400
        os.utime(old, (ancient, ancient))
        src = os.path.join(_tmp, "src2.jpg")
        with open(src, "wb") as fh:
            fh.write(b"\xff\xd8\xff")
        persist_candidate(src)  # trigger dọn file cũ
        self.assertFalse(os.path.exists(old))


if __name__ == "__main__":
    unittest.main()
