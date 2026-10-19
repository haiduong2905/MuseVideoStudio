"""Test parser md tiêu đề/caption (app/core/md_titles.py)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.md_titles import fill_video, lookup, parse_md  # noqa: E402

BEAST_MD = """# Titles & Captions — BeastBytes

## 1. Tyrannosaurus Rex
- File: `final/v1-trex.mp4`
- Text on video:
  Tyrannosaurus Rex
  Strongest bite of any land animal
- Caption: Tyrannosaurus rex ruled North America 68-66 million years ago.
- Hashtags: #beastbytes #animalfacts #trex

## 2. Triceratops
- File: `final/v2-triceratops.mp4`
- Caption: Triceratops had three horns.
- Hashtags: #beastbytes #triceratops
"""

NATURE_MD = """# Tieu de

## 1. Tropical Island — `2026-10-14_dao.mp4` (đã đăng)
- **Title:** A Tropical Jewel from Above
- **Caption:** A jewel in the middle of the ocean.
- **Hashtags:** #tropicalisland #ocean

## 2. Forest — `2026-10-14_rung.mp4`
- **Title:** Hidden Waterfall
- **Caption:** Where the forest sings.
- **Hashtags:** #waterfall #nature
"""


def _write_md(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".md", prefix="su_titles_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TestParseMd(unittest.TestCase):
    def test_beastbytes_format(self):
        entries = parse_md(_write_md(BEAST_MD))
        self.assertEqual(len(entries), 2)
        e = entries["v1-trex.mp4"]
        self.assertEqual(e["title"], "Tyrannosaurus Rex")
        self.assertIn("ruled North America", e["caption"])
        self.assertIn("#trex", e["hashtags"])

    def test_nature_format(self):
        entries = parse_md(_write_md(NATURE_MD))
        e = entries["2026-10-14_dao.mp4"]
        self.assertEqual(e["title"], "A Tropical Jewel from Above")
        self.assertEqual(e["caption"],
                         "A jewel in the middle of the ocean.")
        self.assertIn("#tropicalisland", e["hashtags"])

    def test_entry_without_filename_skipped(self):
        entries = parse_md(_write_md("## 1. No file here\n- Caption: x\n"))
        self.assertEqual(entries, {})

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            parse_md("/tmp/khong-ton-tai-xyz.md")

    def test_lookup_case_insensitive(self):
        entries = parse_md(_write_md(BEAST_MD))
        e = lookup("/home/user/V1-TREX.MP4", entries)
        self.assertIsNotNone(e)
        self.assertEqual(e["title"], "Tyrannosaurus Rex")
        self.assertIsNone(lookup("/home/user/khac.mp4", entries))

    def test_fill_video_empty_only(self):
        entries = parse_md(_write_md(BEAST_MD))
        v = {"file_path": "/x/v1-trex.mp4", "title": "Tự gõ",
             "description": "", "hashtags": ""}
        self.assertTrue(fill_video(v, entries))
        # title đã có -> giữ nguyên; trường trống -> điền từ md
        self.assertEqual(v["title"], "Tự gõ")
        self.assertIn("ruled North America", v["description"])
        self.assertIn("#trex", v["hashtags"])

    def test_fill_video_overwrite(self):
        entries = parse_md(_write_md(BEAST_MD))
        v = {"file_path": "/x/v1-trex.mp4", "title": "Tự gõ",
             "description": "", "hashtags": "", "__overwrite__": True}
        self.assertTrue(fill_video(v, entries))
        self.assertEqual(v["title"], "Tyrannosaurus Rex")
        self.assertNotIn("__overwrite__", v)

    def test_fill_video_no_match(self):
        entries = parse_md(_write_md(BEAST_MD))
        v = {"file_path": "/x/khong-co.mp4", "title": "",
             "description": "", "hashtags": ""}
        self.assertFalse(fill_video(v, entries))


if __name__ == "__main__":
    unittest.main()
