"""Test is_auth_error — cần stub PySide6 vì scheduler import Qt ở top-level."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -- stub PySide6.QtCore tối thiểu --
_qt = types.ModuleType("PySide6")
_qtcore = types.ModuleType("PySide6.QtCore")


class _QObject:
    def __init__(self, *a, **k):
        pass


class _Signal:
    def __init__(self, *a, **k):
        pass

    def connect(self, *a, **k):
        pass

    def emit(self, *a, **k):
        pass


for _n in ("QObject", "QRunnable", "QThread", "QThreadPool"):
    setattr(_qtcore, _n, _QObject)
_qtcore.Signal = _Signal
_qt.QtCore = _qtcore
sys.modules.setdefault("PySide6", _qt)
sys.modules.setdefault("PySide6.QtCore", _qtcore)

from app.core.scheduler import is_auth_error  # noqa: E402


class TestIsAuthError(unittest.TestCase):
    def test_facebook_expired(self):
        self.assertTrue(is_auth_error(
            "Facebook từ chối: Error validating access token: "
            "Session has expired on Saturday, 17-Oct-26 12:00:00 PDT."))

    def test_facebook_invalid_token(self):
        self.assertTrue(is_auth_error("Invalid OAuth access token."))

    def test_youtube_invalid_grant(self):
        self.assertTrue(is_auth_error(
            "invalid_grant: Token has been expired or revoked."))

    def test_not_connected(self):
        self.assertTrue(is_auth_error(
            "Chưa kết nối YouTube hoặc token hết hạn."))

    def test_network_error_not_auth(self):
        self.assertFalse(is_auth_error(
            "[WinError 10060] A connection attempt failed because the "
            "connected party did not properly respond."))

    def test_generic_error_not_auth(self):
        self.assertFalse(is_auth_error("Facebook từ chối: video quá dài."))

    def test_empty(self):
        self.assertFalse(is_auth_error(""))
        self.assertFalse(is_auth_error(None))


if __name__ == "__main__":
    unittest.main()
