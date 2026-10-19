"""Test tách frame làm ảnh bìa (cần ffmpeg trên máy test)."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="su_test_thumb_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

from app.core import thumbnails  # noqa: E402

FFMPEG = shutil_which = None
import shutil  # noqa: E402
FFMPEG = shutil.which("ffmpeg")


def _make_video(path: str, seconds: int = 4) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"color=c=blue:s=640x360:d={seconds}",
         "-pix_fmt", "yuv420p", path],
        check=True, timeout=60)


@unittest.skipUnless(FFMPEG, "cần ffmpeg")
class TestExtractCandidates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video = os.path.join(_tmp, "sample.mp4")
        _make_video(cls.video)

    def test_extract_count(self):
        paths = thumbnails.extract_candidates(self.video, count=4)
        try:
            self.assertEqual(len(paths), 4)
            for p in paths:
                self.assertTrue(os.path.isfile(p))
                self.assertGreater(os.path.getsize(p), 1000)
        finally:
            thumbnails.cleanup_candidates(paths)

    def test_normalize_candidate(self):
        paths = thumbnails.extract_candidates(self.video, count=2)
        try:
            norm = thumbnails.prepare_thumbnail(paths[0])
            self.assertTrue(os.path.isfile(norm))
            self.assertLessEqual(
                os.path.getsize(norm), thumbnails.MAX_BYTES)
        finally:
            thumbnails.cleanup_candidates(paths)

    def test_duration_parse(self):
        dur = thumbnails._video_duration(FFMPEG, self.video)
        self.assertGreater(dur, 3.0)
        self.assertLess(dur, 5.0)

    def test_missing_video_raises(self):
        with self.assertRaises(ValueError):
            thumbnails.extract_candidates("/khong/ton/tai.mp4")


if __name__ == "__main__":
    unittest.main()
