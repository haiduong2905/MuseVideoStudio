"""Test OAuthCodeServer + wait_for_code (stdlib, không cần Qt/google)."""
import os
import sys
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platforms.oauth_callback import (OAuthCodeServer,  # noqa: E402
                                           wait_for_code)


def _hit(port: int, qs: str) -> int:
    with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/callback?{qs}",
            timeout=5) as resp:
        resp.read()
        return resp.status


class TestOAuthCodeServer(unittest.TestCase):
    def test_capture_code(self):
        srv = OAuthCodeServer()
        srv.start()
        try:
            status = _hit(srv.port, "code=abc123&state=xyz")
            self.assertEqual(status, 200)
            time.sleep(0.3)
            self.assertEqual(srv.code, "abc123")
            self.assertIsNone(srv.error)
            code, error = wait_for_code(srv, timeout=2)
            self.assertEqual(code, "abc123")
            self.assertIsNone(error)
        finally:
            srv.stop()

    def test_capture_error(self):
        srv = OAuthCodeServer()
        srv.start()
        try:
            _hit(srv.port, "error=access_denied")
            time.sleep(0.3)
            code, error = wait_for_code(srv, timeout=2)
            self.assertIsNone(code)
            self.assertEqual(error, "access_denied")
        finally:
            srv.stop()

    def test_wait_timeout(self):
        srv = OAuthCodeServer()
        srv.start()
        try:
            t0 = time.monotonic()
            code, error = wait_for_code(srv, timeout=1)
            dt = time.monotonic() - t0
            self.assertIsNone(code)
            self.assertIsNone(error)
            self.assertGreaterEqual(dt, 1.0)
            self.assertLess(dt, 3.0)
        finally:
            srv.stop()

    def test_cancel_event(self):
        srv = OAuthCodeServer()
        srv.start()
        try:
            ev = threading.Event()
            ev.set()
            t0 = time.monotonic()
            code, error = wait_for_code(srv, timeout=30, cancel_event=ev)
            dt = time.monotonic() - t0
            self.assertIsNone(code)
            self.assertIsNone(error)
            self.assertLess(dt, 2.0)  # hủy ngay, không chờ hết timeout
        finally:
            srv.stop()

    def test_fixed_port(self):
        srv = OAuthCodeServer(port=18765)
        srv.start()
        try:
            self.assertEqual(srv.port, 18765)
            self.assertIn("18765", srv.redirect_uri)
            _hit(18765, "code=zz9")
            time.sleep(0.3)
            self.assertEqual(srv.code, "zz9")
        finally:
            srv.stop()

    def test_stop_idempotent(self):
        srv = OAuthCodeServer()
        srv.start()
        srv.stop()
        srv.stop()  # không raise


if __name__ == "__main__":
    unittest.main()
