"""Test QueueModel._match_filter — stub PySide6 generic (PEP 562)."""
import os
import sys
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

from app.ui.queue_model import QueueModel  # noqa: E402


def _item(statuses):
    return {"targets": {f"p{i}": {"enabled": True, "status": s}
                        for i, s in enumerate(statuses)}}


class TestMatchFilter(unittest.TestCase):
    def test_failed(self):
        m = QueueModel._match_filter
        self.assertTrue(m(_item(["failed"]), "failed"))
        self.assertTrue(m(_item(["failed", "pending"]), "failed"))
        self.assertFalse(m(_item(["pending"]), "failed"))
        self.assertFalse(m(_item([]), "failed"))

    def test_pending(self):
        m = QueueModel._match_filter
        self.assertTrue(m(_item(["pending"]), "pending"))
        self.assertFalse(m(_item(["scheduled"]), "pending"))

    def test_uploading(self):
        m = QueueModel._match_filter
        self.assertTrue(m(_item(["uploading"]), "uploading"))
        self.assertFalse(m(_item(["pending"]), "uploading"))

    def test_done(self):
        m = QueueModel._match_filter
        self.assertTrue(m(_item(["scheduled"]), "done"))
        self.assertTrue(m(_item(["published", "draft"]), "done"))
        self.assertFalse(m(_item(["scheduled", "failed"]), "done"))
        self.assertFalse(m(_item([]), "done"))

    def test_disabled_target_ignored(self):
        item = {"targets": {"youtube": {"enabled": False, "status": "failed"},
                            "facebook": {"enabled": True,
                                         "status": "scheduled"}}}
        self.assertFalse(QueueModel._match_filter(item, "failed"))
        self.assertTrue(QueueModel._match_filter(item, "done"))


if __name__ == "__main__":
    unittest.main()
