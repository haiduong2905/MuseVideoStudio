"""Test package init.

Import PySide6 thật TRƯỚC mọi test module, để các test stub PySide6
(test_main_window_filter, test_no_window) dùng sys.modules.setdefault
không ghi đè Qt thật mà các test khác (mailbox worker...) đang dùng.
"""
try:
    import PySide6.QtCore  # noqa: F401
    import PySide6.QtWidgets  # noqa: F401
except ImportError:
    pass
