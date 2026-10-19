"""Test: gọi ffmpeg không hiện cửa sổ cmd trên Windows.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import thumbnails  # noqa: E402


class TestNoWindowFlag(unittest.TestCase):
    def test_run_ffmpeg_hides_console(self):
        with mock.patch.object(
                thumbnails.subprocess, "run") as m_run:
            thumbnails._run_ffmpeg(["ffmpeg", "-version"],
                                   stdout=thumbnails.subprocess.DEVNULL)
        _args, kwargs = m_run.call_args
        self.assertIn("creationflags", kwargs)
        # Trên Linux CREATE_NO_WINDOW = 0, trên Windows = 0x08000000;
        # quan trọng là luôn truyền flag này.
        self.assertEqual(
            kwargs["creationflags"],
            getattr(thumbnails.subprocess, "CREATE_NO_WINDOW", 0))

    def test_no_window_const_defined(self):
        self.assertTrue(hasattr(thumbnails, "_NO_WINDOW"))


if __name__ == "__main__":
    unittest.main()
