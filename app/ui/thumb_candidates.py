"""Dải ảnh bìa ứng viên tự tách từ video — bấm để chọn.

Dùng chung cho dialog thêm 1 video và thêm nhiều video.
Việc tách frame chạy nền để không đơ UI.
"""
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.core.thumbnails import (cleanup_candidates, extract_candidates,
                                 ffmpeg_available)


class _ExtractSignals(QObject):
    done = Signal(str, list)  # video_path, paths
    error = Signal(str, str)  # video_path, message


class _ExtractTask(QRunnable):
    def __init__(self, video_path: str, count: int,
                 signals: _ExtractSignals) -> None:
        super().__init__()
        self.video_path = video_path
        self.count = count
        self.signals = signals

    def run(self) -> None:
        try:
            paths = extract_candidates(self.video_path, count=self.count)
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(self.video_path, str(exc))
        else:
            self.signals.done.emit(self.video_path, paths)


class ThumbCandidates(QWidget):
    """Widget chọn ảnh bìa từ frame video. Phát `picked(path)` khi user
    bấm chọn 1 ảnh."""

    picked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._paths: list[str] = []
        self._active_video: str | None = None  # video đang tách (chống race)
        self._pool = QThreadPool.globalInstance()

        self.status = QLabel("Chưa tách frame.")
        self.status.setStyleSheet("color: gray; font-size: 11px;")

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.buttonClicked.connect(self._on_clicked)

        inner = QWidget()
        self.strip = QHBoxLayout(inner)
        self.strip.setContentsMargins(0, 0, 0, 0)
        self.strip.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        scroll.setFixedHeight(110)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.status)
        lay.addWidget(scroll)
        self.setVisible(False)

    # -- API --------------------------------------------------------------
    def extract(self, video_path: str, count: int = 3) -> None:
        """Bắt đầu tách frame từ video (chạy nền, mặc định 3 ảnh).

        Nếu user đổi video giữa chừng, kết quả cũ về trễ sẽ bị bỏ
        (không hiện nhầm frame của video khác).
        """
        self.clear()
        if not video_path:
            return
        if not ffmpeg_available():
            self.status.setText("Không tìm thấy ffmpeg, "
                                "không tách frame được.")
            self.setVisible(True)
            return
        self._active_video = video_path
        self.setVisible(True)
        self.status.setText("⏳ Đang tách frame từ video…")
        self.signals = _ExtractSignals()
        self.signals.done.connect(self._on_done)
        self.signals.error.connect(self._on_error)
        self._pool.start(_ExtractTask(video_path, count, self.signals))

    def keep(self, path: str) -> None:
        """Đánh dấu file đã được user chọn: clear() sau này không xóa nó.

        Dùng kèm persist_candidate(): file gốc trong _paths được giữ lại
        để bản copy bền vững luôn hợp lệ đến lúc prepare_thumbnail().
        """
        if path in self._paths:
            self._paths.remove(path)

    def clear(self) -> None:
        """Xóa dải ảnh + file tạm."""
        self._active_video = None
        cleanup_candidates(self._paths)
        self._paths = []
        while self.strip.count() > 1:  # giữ lại stretch cuối
            item = self.strip.takeAt(0)
            w = item.widget()
            if w:
                self.group.removeButton(w)
                w.deleteLater()
        self.setVisible(False)

    # -- nội bộ -----------------------------------------------------------
    def _on_done(self, video_path: str, paths: list) -> None:
        # Bỏ kết quả trễ của video đã chuyển đi (tránh hiện nhầm ảnh)
        if video_path != self._active_video:
            cleanup_candidates(paths)
            return
        self._paths = list(paths)
        for p in self._paths:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(128, 96)
            btn.setIcon(QIcon(QPixmap(p)))
            btn.setIconSize(QSize(120, 68))
            btn.setToolTip(p)
            btn.setProperty("path", p)
            btn.setStyleSheet(
                "QPushButton:checked { border: 3px solid #2da44e; }")
            self.group.addButton(btn)
            self.strip.insertWidget(self.strip.count() - 1, btn)
        self.status.setText(f"Đã tách {len(self._paths)} frame — "
                            "bấm vào 1 ảnh để chọn làm ảnh bìa.")

    def _on_error(self, video_path: str, msg: str) -> None:
        if video_path != self._active_video:
            return
        self.status.setText(f"Không tách được frame: {msg}")

    def _on_clicked(self, btn: QPushButton) -> None:
        path = btn.property("path")
        if path:
            self.picked.emit(str(path))
