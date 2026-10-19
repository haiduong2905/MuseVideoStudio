"""Test core/brief.py — định dạng brief chuẩn."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.brief import Brief, brief_from_db_row, build_brief_text


class TestBuildBriefText(unittest.TestCase):
    def _brief(self, **kw):
        base = dict(project_code="beastbytes", scene_no=1,
                    scene_name="Cảnh 1", tab="text",
                    prompt="A cute cat walking in a garden.",
                    ratio="9:16", duration=10, style="Cinematic",
                    ref_count=2, day="2026-10-19")
        base.update(kw)
        return Brief(**base)

    def test_format_day_du(self):
        t = build_brief_text(self._brief())
        self.assertIn("[BRIEF] Mã dự án: BEASTBYTES | Cảnh 1 — Cảnh 1 "
                      "| Ngày: 2026-10-19", t)
        self.assertIn("Loại: text", t)
        self.assertIn("Tỉ lệ: 9:16 | Thời lượng: 10s | Style: Cinematic", t)
        self.assertIn("Mô tả: A cute cat walking in a garden.", t)
        self.assertIn("Text trên video: không", t)
        self.assertIn("Nhạc: không", t)
        self.assertIn("Ảnh tham chiếu: 2 (đính kèm khi paste)", t)

    def test_tab_labels(self):
        t = build_brief_text(self._brief(tab="image"))
        self.assertIn("Loại: ảnh", t)
        t = build_brief_text(self._brief(tab="template"))
        self.assertIn("Loại: template", t)

    def test_optional_fields(self):
        t = build_brief_text(self._brief(onscreen_text="FACT: mèo ngủ 16h",
                                         music="vui tươi",
                                         note="Ưu tiên góc cận"))
        self.assertIn("Text trên video: FACT: mèo ngủ 16h", t)
        self.assertIn("Nhạc: vui tươi", t)
        self.assertIn("Ghi chú: Ưu tiên góc cận", t)

    def test_project_code_chuan_hoa(self):
        t = build_brief_text(self._brief(project_code="  beastbytes "))
        self.assertIn("Mã dự án: BEASTBYTES", t)

    def test_thieu_prompt_bao_loi(self):
        with self.assertRaises(ValueError):
            self._brief(prompt="   ")

    def test_thieu_ma_du_an_bao_loi(self):
        with self.assertRaises(ValueError):
            self._brief(project_code="")

    def test_tab_sai_bao_loi(self):
        with self.assertRaises(ValueError):
            self._brief(tab="audio")

    def test_brief_from_db_row(self):
        row = {"scene_no": 2, "scene_name": "Cảnh 2", "tab": "text",
               "prompt": "prompt", "ratio": "16:9", "duration": 15,
               "style": "Tự nhiên", "ref_images": '["a.png", "b.png"]'}
        b = brief_from_db_row(row, "BB")
        self.assertEqual(b.ref_count, 2)
        self.assertEqual(b.ratio, "16:9")
        t = build_brief_text(b)
        self.assertIn("Mã dự án: BB", t)


if __name__ == "__main__":
    unittest.main()
