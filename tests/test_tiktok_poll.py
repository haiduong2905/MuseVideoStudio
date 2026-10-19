"""Test: TikTok poll timeout KHÔNG được báo thành công giả.

Bug thực tế: hết 3 phút poll mà TikTok chưa SUCCESS, code cũ vẫn
return ok=True -> user tưởng video đã vào bản nháp nhưng không có.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platforms.tiktok import TikTokPlatform  # noqa: E402


def _resp(payload, status_code=200):
    m = mock.Mock()
    m.status_code = status_code
    m.json.return_value = payload
    return m


class _FakeClock:
    """Đồng hồ giả: sleep() tua nhanh thời gian, tránh busy-loop 180s thật."""
    def __init__(self):
        self.now = 1_000_000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class TestTikTokPollTimeout(unittest.TestCase):
    def _platform(self):
        plat = TikTokPlatform()
        plat._get_valid_token = lambda: "fake"
        return plat

    def test_poll_timeout_returns_failure(self):
        plat = self._platform()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(b"\x00" * 1024)
        tmp.close()
        try:
            init = _resp({"error": {"code": "ok"},
                          "data": {"upload_url": "http://x/upload",
                                   "publish_id": "p1"}})
            processing = _resp({"data": {"status": "PROCESSING_UPLOAD"}})

            def fake_post(url, **kwargs):
                if "init" in url:
                    return init
                return processing

            item = {"file_path": tmp.name, "title": "T"}
            with mock.patch("app.platforms.tiktok.requests.post",
                            side_effect=fake_post), \
                 mock.patch.object(TikTokPlatform, "_put_chunks",
                                   return_value=None), \
                 mock.patch("app.platforms.tiktok.time",
                            _FakeClock()):
                res = plat.upload(item, lambda _p: None)
            self.assertFalse(res.ok,
                             "Hết 3 phút chưa SUCCESS phải failed, "
                             "không được báo thành công giả")
            self.assertIn("3 phút", res.error)
        finally:
            os.unlink(tmp.name)

    def test_poll_success_still_ok(self):
        plat = self._platform()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(b"\x00" * 1024)
        tmp.close()
        try:
            calls = {"n": 0}

            def fake_post(url, **kwargs):
                if "init" in url:
                    return _resp(
                        {"error": {"code": "ok"},
                         "data": {"upload_url": "http://x/upload",
                                  "publish_id": "p1"}})
                calls["n"] += 1
                if calls["n"] < 2:
                    return _resp({"data": {"status": "PROCESSING_UPLOAD"}})
                return _resp({"data": {"status": "SUCCESS"}})

            item = {"file_path": tmp.name, "title": "T"}
            with mock.patch("app.platforms.tiktok.requests.post",
                            side_effect=fake_post), \
                 mock.patch.object(TikTokPlatform, "_put_chunks",
                                   return_value=None), \
                 mock.patch("app.platforms.tiktok.time",
                            _FakeClock()):
                res = plat.upload(item, lambda _p: None)
            self.assertTrue(res.ok)
            self.assertEqual(res.status, "draft")
        finally:
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
