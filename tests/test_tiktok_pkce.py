"""Test PKCE + auth URL TikTok (không cần Qt/google)."""
import hashlib
import os
import re
import sys
import unittest
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platforms.tiktok import (build_auth_url,  # noqa: E402
                                   generate_pkce)


class TestTikTokPKCE(unittest.TestCase):
    def test_pkce_pair_valid(self):
        verifier, challenge = generate_pkce()
        # verifier: 43-128 ký tự, chỉ ký tự unreserved
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9\-._~]+", verifier),
                        f"verifier có ký tự lạ: {verifier}")
        # TikTok desktop: challenge = HEX của SHA256(verifier)
        expected = hashlib.sha256(verifier.encode("ascii")).hexdigest()
        self.assertEqual(challenge, expected)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", challenge),
                        f"challenge không phải hex 64 ký tự: {challenge}")

    def test_pkce_unique(self):
        v1, _ = generate_pkce()
        v2, _ = generate_pkce()
        self.assertNotEqual(v1, v2)

    def test_auth_url_has_pkce(self):
        _, challenge = generate_pkce()
        url = build_auth_url("test_key", "state123", challenge)
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs["client_key"], ["test_key"])
        self.assertEqual(qs["response_type"], ["code"])
        self.assertEqual(qs["code_challenge"], [challenge])
        self.assertEqual(qs["code_challenge_method"], ["S256"])
        self.assertEqual(qs["redirect_uri"],
                         ["http://localhost:8765/callback/"])
        self.assertIn("video.upload", qs["scope"][0])


if __name__ == "__main__":
    unittest.main()
