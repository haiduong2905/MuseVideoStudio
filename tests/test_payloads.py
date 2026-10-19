"""Unit test (stdlib unittest) cho các hàm dựng payload.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platforms.youtube import build_video_body, is_immediate_publish, to_utc_iso
from app.platforms.facebook import build_finish_params, to_unix
from app.platforms.tiktok import build_init_body
from app.platforms.youtube import YouTubePlatform
from app.platforms.facebook import FacebookPlatform
from app.platforms.tiktok import TikTokPlatform


def _future_iso(days=2):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00")


def _past_iso(hours=1):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00")


class TestYouTubeBody(unittest.TestCase):
    def _item(self, **kw):
        base = {
            "file_path": "x.mp4",
            "title": "Tiêu đề test",
            "description": "Mô tả test",
            "hashtags": "#beastbytes #animalfacts",
            "scheduled_at": _future_iso(),
        }
        base.update(kw)
        return base

    def test_title_truncated_to_100_chars(self):
        body = build_video_body(self._item(title="A" * 150))
        self.assertEqual(len(body["snippet"]["title"]), 100)

    def test_publish_at_is_utc_iso(self):
        body = build_video_body(self._item(
            scheduled_at="2030-10-17T10:00:00+00:00"))
        publish_at = body["status"]["publishAt"]
        self.assertTrue(publish_at.endswith("Z"), publish_at)
        self.assertEqual(publish_at, "2030-10-17T10:00:00.000Z")

    def test_to_utc_iso_converts_offset(self):
        # +07:00 -> UTC lùi 7 tiếng
        self.assertEqual(to_utc_iso("2026-10-17T17:00:00+07:00"),
                         "2026-10-17T10:00:00.000Z")

    def test_private_status(self):
        body = build_video_body(self._item())
        self.assertEqual(body["status"]["privacyStatus"], "private")

    def test_immediate_publish_when_schedule_passed(self):
        # Giờ hẹn đã qua -> đăng public luôn, không có publishAt
        body = build_video_body(self._item(scheduled_at=_past_iso()))
        self.assertEqual(body["status"]["privacyStatus"], "public")
        self.assertNotIn("publishAt", body["status"])
        self.assertTrue(is_immediate_publish(_past_iso()))
        self.assertFalse(is_immediate_publish(_future_iso()))

    def test_description_appends_hashtags(self):
        body = build_video_body(self._item())
        desc = body["snippet"]["description"]
        self.assertIn("Mô tả test", desc)
        self.assertIn("#beastbytes", desc)

    def test_tags_from_hashtags(self):
        body = build_video_body(self._item())
        self.assertIn("beastbytes", body["snippet"]["tags"])
        self.assertIn("animalfacts", body["snippet"]["tags"])


class TestFacebookFinishParams(unittest.TestCase):
    def test_scheduled_state_and_int_timestamp(self):
        params = build_finish_params("vid123", "mô tả", 1780000000)
        self.assertEqual(params["video_state"], "SCHEDULED")
        self.assertEqual(params["upload_phase"], "finish")
        self.assertEqual(params["video_id"], "vid123")
        self.assertIsInstance(params["scheduled_publish_time"], int)

    def test_float_timestamp_becomes_int(self):
        params = build_finish_params("v", "d", 1780000000.9)
        self.assertEqual(params["scheduled_publish_time"], 1780000000)

    def test_to_unix_roundtrip(self):
        ts = to_unix("2026-10-17T10:00:00+00:00")
        self.assertEqual(ts, 1792231200)

    def test_published_state_omits_schedule_time(self):
        params = build_finish_params("v", "d", 1780000000,
                                     video_state="PUBLISHED")
        self.assertEqual(params["video_state"], "PUBLISHED")
        self.assertNotIn("scheduled_publish_time", params)


class TestNativeSchedulingFlags(unittest.TestCase):
    def test_youtube_facebook_upload_immediately(self):
        self.assertTrue(YouTubePlatform.native_scheduling)
        self.assertTrue(FacebookPlatform.native_scheduling)

    def test_tiktok_waits_for_schedule(self):
        self.assertFalse(TikTokPlatform.native_scheduling)


class TestTikTokInitBody(unittest.TestCase):
    def test_file_upload_source(self):
        body = build_init_body(50 * 1024 * 1024, "Tiêu đề")
        src = body["source_info"]
        self.assertEqual(src["source"], "FILE_UPLOAD")
        self.assertEqual(src["video_size"], 50 * 1024 * 1024)
        # file > 32MB -> chunk 32MB
        self.assertEqual(src["chunk_size"], 32 * 1024 * 1024)
        self.assertEqual(body["post_info"]["title"], "Tiêu đề")

    def test_small_file_single_chunk(self):
        body = build_init_body(5 * 1024 * 1024, "T")
        self.assertEqual(body["source_info"]["chunk_size"], 5 * 1024 * 1024)
        self.assertEqual(body["source_info"]["total_chunk_count"], 1)

    def test_total_chunk_count_ceil(self):
        # 50MB / 32MB -> ceil = 2 chunk
        body = build_init_body(50 * 1024 * 1024, "Tiêu đề")
        self.assertEqual(body["source_info"]["total_chunk_count"], 2)
        # thiếu total_chunk_count -> TikTok init fail "The video info is empty"
        self.assertIn("total_chunk_count", body["source_info"])


if __name__ == "__main__":
    unittest.main()
