"""Test bài viết (post): DB + Facebook upload_post (mock requests)."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="su_test_post_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

from app.core import db  # noqa: E402
from app.platforms import get_platform  # noqa: E402
from app.platforms.base import UploadResult  # noqa: E402


class FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class TestPostDB(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_add_post(self):
        qid = db.add_queue(
            "", "Dòng tiêu đề", description="Nội dung bài",
            scheduled_at="2030-06-01T10:00:00",
            content_type="post", image_paths=["/tmp/a.jpg", "/tmp/b.png"])
        item = db.get_queue(qid)
        self.assertEqual(item["content_type"], "post")
        self.assertEqual(json.loads(item["image_paths"]),
                         ["/tmp/a.jpg", "/tmp/b.png"])

    def test_invalid_content_type(self):
        with self.assertRaises(ValueError):
            db.add_queue("/tmp/x.mp4", "t", content_type="story")

    def test_update_image_paths(self):
        qid = db.add_queue("", "t", content_type="post")
        db.update_queue(qid, image_paths=["/tmp/c.jpg"])
        item = db.get_queue(qid)
        self.assertEqual(json.loads(item["image_paths"]), ["/tmp/c.jpg"])

    def test_migration_adds_columns(self):
        import sqlite3
        path = os.path.join(_tmp, "mig2.db")
        if os.path.exists(path):
            os.remove(path)
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
            hashtags TEXT NOT NULL DEFAULT '', scheduled_at TEXT NOT NULL,
            created_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
            thumbnail_path TEXT NOT NULL DEFAULT '')""")
        conn.commit()
        conn.close()
        os.environ["SOCIAL_UPLOADER_DB"] = path
        db.init_db()
        qid = db.add_queue("/tmp/v.mp4", "t")
        item = db.get_queue(qid)
        self.assertEqual(item["content_type"], "video")
        self.assertEqual(item["image_paths"], "[]")
        os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")


class TestFacebookUploadPost(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.plat = get_platform("facebook", account_id=999)
        # giả lập đã kết nối
        self.plat._get_creds = lambda: ("12345", "tok_test")

    def _item(self, text="Hello", images=None):
        return {"text": text,
                "image_paths": json.dumps(images or []),
                "scheduled_at": "2030-06-01T10:00:00"}

    @patch("app.platforms.facebook.requests.post")
    def test_text_only_scheduled(self, mock_post):
        mock_post.return_value = FakeResp(200, {"id": "123_456"})
        res = self.plat.upload_post(self._item(), lambda _p: None)
        self.assertTrue(res.ok)
        self.assertEqual(res.status, "scheduled")
        self.assertEqual(res.remote_id, "123_456")
        # kiểm tra params gửi đi
        _, kwargs = mock_post.call_args
        data = kwargs["data"]
        self.assertEqual(data["message"], "Hello")
        self.assertEqual(data["published"], "false")
        self.assertIn("scheduled_publish_time", data)
        self.assertNotIn("attached_media", data)

    @patch("app.platforms.facebook.requests.post")
    def test_with_images(self, mock_post):
        # tạo 2 file ảnh giả
        import tempfile as tf
        imgs = []
        for i in range(2):
            p = os.path.join(_tmp, f"img{i}.jpg")
            with open(p, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0" + b"0" * 100)
            imgs.append(p)

        calls = []

        def fake_post(url, data=None, files=None, timeout=None):
            calls.append((url, data, bool(files)))
            if url.endswith("/photos"):
                return FakeResp(200, {"id": f"photo_{len(calls)}"})
            return FakeResp(200, {"id": "123_789"})

        mock_post.side_effect = fake_post
        res = self.plat.upload_post(
            self._item("Bài có ảnh", imgs), lambda _p: None)
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.remote_id, "123_789")
        # 2 lần upload ảnh + 1 lần đăng feed
        self.assertEqual(len(calls), 3)
        feed_data = calls[-1][1]
        media = json.loads(feed_data["attached_media"])
        self.assertEqual(len(media), 2)
        self.assertTrue(all("media_fbid" in m for m in media))

    @patch("app.platforms.facebook.requests.post")
    def test_empty_post_rejected(self, mock_post):
        res = self.plat.upload_post(self._item("", []), lambda _p: None)
        self.assertFalse(res.ok)
        mock_post.assert_not_called()

    def test_unsupported_platform(self):
        yt = get_platform("youtube", account_id=1)
        res = yt.upload_post(self._item(), lambda _p: None)
        self.assertFalse(res.ok)
        self.assertIn("chưa hỗ trợ", res.error)


if __name__ == "__main__":
    unittest.main()
