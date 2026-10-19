"""Test cho trạng thái tài khoản: Ngắt giữ lại, scheduler bỏ qua.

Chạy:  python -m unittest discover   (từ thư mục project)
"""
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_qt_module(name):
    mod = types.ModuleType(name)

    class _DummyMeta(type):
        def __getattr__(cls, attr):
            return _dummy(attr)

    def _dummy(attr):
        return _DummyMeta(attr, (), {
            "__init__": lambda self, *a, **k: None,
        })

    def __getattr__(attr, _n=name):
        return _dummy(attr)

    mod.__getattr__ = __getattr__
    return mod


_qt = types.ModuleType("PySide6")
for _sub in ("QtCore", "QtGui", "QtWidgets"):
    _m = _make_qt_module(f"PySide6.{_sub}")
    setattr(_qt, _sub, _m)
    sys.modules.setdefault(f"PySide6.{_sub}", _m)
sys.modules.setdefault("PySide6", _qt)

_tmp = tempfile.mkdtemp(prefix="su_test_accstatus_")
os.environ["SOCIAL_UPLOADER_DB"] = os.path.join(_tmp, "data.db")

from app.core import db  # noqa: E402
from app.platforms import get_platform  # noqa: E402


class TestAccountStatus(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_disconnect_keeps_account(self):
        acc_id = db.add_account("facebook", "Test Page")
        plat = get_platform("facebook", acc_id)
        # giả lập đã kết nối: lưu page_id + token trực tiếp
        # (keyring có thể không khả dụng trên máy test -> bỏ qua nếu vậy)
        from app.core import secrets as secrets_mod
        _has_kr = secrets_mod.set_secret(f"facebook_page_id_{acc_id}", "123")
        _has_kr = secrets_mod.set_secret(
            f"facebook_token_json_{acc_id}", "tok") and _has_kr
        db.set_account_status(acc_id, "active")
        self.assertTrue(db.account_is_active(acc_id))
        # Ngắt: tài khoản vẫn còn, chỉ đổi status
        plat.disconnect()
        acc = db.get_account_by_id(acc_id)
        self.assertIsNotNone(acc)
        self.assertEqual(acc["label"], "Test Page")
        self.assertFalse(db.account_is_active(acc_id))
        if _has_kr:
            self.assertFalse(plat.is_connected())
            # token vẫn giữ trong keyring
            self.assertEqual(
                secrets_mod.get_secret(f"facebook_token_json_{acc_id}"),
                "tok")
        # purge: xóa hẳn
        plat.purge()
        self.assertIsNone(db.get_account_by_id(acc_id))
        if _has_kr:
            self.assertIsNone(
                secrets_mod.get_secret(f"facebook_token_json_{acc_id}"))

    def test_legacy_none_account_id_is_active(self):
        self.assertTrue(db.account_is_active(None))

    def test_time_slots(self):
        from app.ui.datetime_picker import time_slots
        slots = time_slots()
        self.assertEqual(len(slots), 96)
        self.assertEqual(slots[0], "00:00")
        self.assertEqual(slots[-1], "23:45")
        self.assertIn("15:00", slots)


if __name__ == "__main__":
    unittest.main()
