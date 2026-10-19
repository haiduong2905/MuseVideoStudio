"""Test core/mailbox.py — parse manifest, dedup, download, checksum."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.mailbox import (ManifestError, download_file, new_videos,
                              parse_manifest, safe_filename, verify_sha256)


def _video_dict(**kw):
    base = {"id": "bb-001", "file_url": "https://x/y.mp4",
            "project_code": "beastbytes", "title": "T"}
    base.update(kw)
    return base


class TestParseManifest(unittest.TestCase):
    def test_hop_le(self):
        vs = parse_manifest({"videos": [_video_dict()]})
        self.assertEqual(len(vs), 1)
        self.assertEqual(vs[0].id, "bb-001")
        self.assertEqual(vs[0].project_code, "BEASTBYTES")

    def test_thieu_videos(self):
        with self.assertRaises(ManifestError):
            parse_manifest({})

    def test_videos_khong_phai_list(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"videos": "x"})

    def test_thieu_id(self):
        d = _video_dict()
        del d["id"]
        with self.assertRaises(ManifestError):
            parse_manifest({"videos": [d]})

    def test_thieu_file_url(self):
        d = _video_dict()
        del d["file_url"]
        with self.assertRaises(ManifestError):
            parse_manifest({"videos": [d]})

    def test_brief_id_sai_thanh_none(self):
        vs = parse_manifest({"videos": [_video_dict(brief_id="abc")]})
        self.assertIsNone(vs[0].brief_id)

    def test_manifest_rong_ok(self):
        self.assertEqual(parse_manifest({"videos": []}), [])


class TestNewVideos(unittest.TestCase):
    def test_dedup_theo_id(self):
        vs = parse_manifest({"videos": [_video_dict(id="a"),
                                         _video_dict(id="b")]})
        fresh = new_videos(vs, {"a"})
        self.assertEqual([v.id for v in fresh], ["b"])


class TestSafeFilename(unittest.TestCase):
    def test_ky_tu_cam(self):
        self.assertEqual(safe_filename('a<b>:"/\\|?*c'), "a_b________c")

    def test_rong(self):
        self.assertEqual(safe_filename(""), "video")


class TestVerifySha256(unittest.TestCase):
    def test_dung(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            p = f.name
        try:
            h = hashlib.sha256(b"hello").hexdigest()
            self.assertTrue(verify_sha256(p, h))
            self.assertFalse(verify_sha256(p, "0" * 64))
            self.assertTrue(verify_sha256(p, ""))  # không kiểm
        finally:
            os.remove(p)


class TestDownloadFile(unittest.TestCase):
    def test_file_url_va_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.mp4")
            with open(src, "wb") as f:
                f.write(b"x" * 3000000)
            dest = os.path.join(tmp, "sub", "dst.mp4")
            calls = []
            download_file(Path(src).as_uri(), dest,
                          progress_cb=lambda d, t: calls.append((d, t)))
            self.assertTrue(os.path.isfile(dest))
            self.assertEqual(os.path.getsize(dest), 3000000)
            self.assertTrue(calls)  # progress được gọi
            self.assertFalse(os.path.exists(dest + ".part"))  # dọn .part

    def test_url_sai_bao_loi(self):
        with tempfile.TemporaryDirectory() as tmp:
            bogus = Path(tmp) / "khong_ton_tai.mp4"
            with self.assertRaises(ManifestError):
                download_file(bogus.as_uri(),
                              os.path.join(tmp, "d.mp4"))


if __name__ == "__main__":
    unittest.main()
