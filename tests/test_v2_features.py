"""Test cho đợt tính năng 2: thumbnail, xếp lịch nhanh, nhắc TikTok.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DB test dùng thư mục tạm, không động vào DB thật
_tmp = tempfile.mkdtemp(prefix="su_test_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

from app.core import db  # noqa: E402
from app.core.thumbnails import MAX_BYTES, prepare_thumbnail  # noqa: E402
from app.ui.batch_dialog import (build_quick_plan, parse_slots,  # noqa: E402
                                 title_from_filename)


class TestParseSlots(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_slots("07:00, 11:30,15:30"),
                         ["07:00", "11:30", "15:30"])

    def test_sorted_unique(self):
        self.assertEqual(parse_slots("21:30, 07:00, 07:00"),
                         ["07:00", "21:30"])

    def test_semicolon_separator(self):
        self.assertEqual(parse_slots("7:00;12:00"), ["07:00", "12:00"])

    def test_invalid(self):
        for bad in ["", "25:00", "abc", "07-00", "12:60"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_slots(bad)


class TestQuickPlan(unittest.TestCase):
    def test_distributes_across_days(self):
        now = datetime(2026, 10, 17, 6, 0, 0)
        plan = build_quick_plan(["07:00", "19:00"], date(2026, 10, 17),
                                now, 5)
        self.assertEqual(plan, [
            "2026-10-17T07:00:00",
            "2026-10-17T19:00:00",
            "2026-10-18T07:00:00",
            "2026-10-18T19:00:00",
            "2026-10-19T07:00:00",
        ])

    def test_skips_past_slots_today(self):
        now = datetime(2026, 10, 17, 12, 0, 0)
        plan = build_quick_plan(["07:00", "19:00"], date(2026, 10, 17),
                                now, 2)
        # 07:00 đã qua -> bỏ, lấy 19:00 hôm nay rồi 07:00 hôm sau
        self.assertEqual(plan, ["2026-10-17T19:00:00",
                                "2026-10-18T07:00:00"])

    def test_start_future_date(self):
        now = datetime(2026, 10, 17, 6, 0, 0)
        plan = build_quick_plan(["08:00"], date(2026, 10, 20), now, 2)
        self.assertEqual(plan, ["2026-10-20T08:00:00",
                                "2026-10-21T08:00:00"])

    def test_title_from_filename(self):
        self.assertEqual(title_from_filename("/a/v12-quetzalcoatlus.mp4"),
                         "v12 quetzalcoatlus")


class TestThumbnail(unittest.TestCase):
    def test_prepare_large_image(self):
        from PIL import Image
        src = os.path.join(_tmp, "big.png")
        # ảnh 3000x2000 nhiều chi tiết -> file gốc lớn
        img = Image.new("RGB", (3000, 2000))
        px = img.load()
        for x in range(0, 3000, 10):
            for y in range(0, 2000, 10):
                px[x, y] = (x % 256, y % 256, (x * y) % 256)
        img.save(src, "PNG")
        out = prepare_thumbnail(src, dest_name="t1.jpg")
        self.assertTrue(os.path.isfile(out))
        self.assertLessEqual(os.path.getsize(out), MAX_BYTES)
        with Image.open(out) as got:
            self.assertLessEqual(got.width, 1280)
            self.assertLessEqual(got.height, 720)

    def test_invalid_image(self):
        bad = os.path.join(_tmp, "notimg.txt")
        with open(bad, "w") as fh:
            fh.write("hello")
        with self.assertRaises(ValueError):
            prepare_thumbnail(bad)


class TestTikTokReminderDb(unittest.TestCase):
    def test_unreminded_drafts(self):
        db.init_db()
        # migration: cột mới phải tồn tại
        qid = db.add_queue("/v/a.mp4", "Video A",
                           scheduled_at="2026-10-17T10:00:00")
        db.set_targets(qid, {"youtube": False, "facebook": False,
                             "tiktok": True})
        # chưa draft -> không nhắc
        self.assertEqual(db.get_unreminded_tiktok_drafts(
            "2026-10-17T11:00:00"), [])
        # giả lập đã upload vào nháp
        tg = None
        for it in db.list_queue():
            if it["id"] == qid:
                tg = it["targets"]["tiktok"]
        db.update_target(tg["id"], status="draft")
        got = db.get_unreminded_tiktok_drafts("2026-10-17T11:00:00")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["title"], "Video A")
        # đánh dấu đã nhắc -> hết
        db.update_target(tg["id"], reminded=1)
        self.assertEqual(db.get_unreminded_tiktok_drafts(
            "2026-10-17T11:00:00"), [])
        # snooze 15 phút -> nhắc lại khi đến giờ
        db.update_target(tg["id"], reminded=0,
                         next_reminder_at="2026-10-17T11:10:00")
        self.assertEqual(db.get_unreminded_tiktok_drafts(
            "2026-10-17T11:05:00"), [])
        got = db.get_unreminded_tiktok_drafts("2026-10-17T11:15:00")
        self.assertEqual(len(got), 1)


if __name__ == "__main__":
    unittest.main()
