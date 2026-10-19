"""Ô chọn ngày + giờ: QDateEdit (lịch popup) + QComboBox giờ (bấm chọn/gõ tay).

Khang phản hồi QDateTimeEdit gộp cũ "không chọn được giờ", còn QTimeEdit
mũi tên lên/xuống thì "quá kém" — nên giờ là combo 96 khung (cách 15 phút),
bấm chọn hoặc gõ trực tiếp "15:07".

API tương thích QDateTimeEdit: dateTime(), setDateTime(),
setMinimumDateTime(), signal dateTimeChanged.
"""
from PySide6.QtCore import QDateTime, QTime, Signal
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QWidget


def time_slots() -> list[str]:
    """96 khung giờ cách 15 phút: '00:00' ... '23:45'."""
    return [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]


def parse_time(text: str) -> QTime | None:
    """Parse 'HH:mm'/'H:mm'. Trả về None nếu sai định dạng."""
    t = QTime.fromString(text.strip(), "HH:mm")
    if not t.isValid():
        t = QTime.fromString(text.strip(), "H:mm")
    return t if t.isValid() else None


def fix_calendar_popup(date_edit) -> None:
    """Ép lịch popup đủ rộng cho ngày 2 chữ số.

    Một số máy render cột lịch quá hẹp khiến ngày 2 chữ số (10-31, T7/CN)
    bị cắt thành "...". Ép cỡ ô tối thiểu để luôn hiện đủ.
    """
    try:
        cal = date_edit.calendarWidget()
        if cal is None:
            return
        cal.setMinimumSize(360, 300)
        from PySide6.QtWidgets import QTableView
        table = cal.findChild(QTableView)
        if table is not None:
            table.horizontalHeader().setDefaultSectionSize(46)
            table.verticalHeader().setDefaultSectionSize(34)
    except Exception:  # noqa: BLE001
        pass


class DateTimePicker(QWidget):
    dateTimeChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.date_edit = QDateEdit()
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setCalendarPopup(True)
        fix_calendar_popup(self.date_edit)

        self.time_combo = QComboBox()
        self.time_combo.setEditable(True)
        self.time_combo.addItems(time_slots())
        self.time_combo.setMinimumWidth(110)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self.date_edit, 1)
        lay.addWidget(self.time_combo, 0)

        self._min_dt: QDateTime | None = None
        self._last_valid = QDateTime.currentDateTime()
        self.date_edit.dateChanged.connect(self._on_changed)
        # Chọn từ danh sách -> nhận ngay; gõ tay -> chỉ nhận khi xong
        # (tránh revert khi đang gõ dở, VD mới gõ "1")
        self.time_combo.activated.connect(lambda _i: self._on_changed())
        self.time_combo.lineEdit().editingFinished.connect(
            self._on_changed)

    # -- API tương thích QDateTimeEdit --
    def dateTime(self) -> QDateTime:
        t = parse_time(self.time_combo.currentText()) or QTime(0, 0)
        return QDateTime(self.date_edit.date(), t)

    def setDateTime(self, qdt: QDateTime) -> None:
        self.date_edit.blockSignals(True)
        self.time_combo.blockSignals(True)
        try:
            self.date_edit.setDate(qdt.date())
            self.time_combo.setCurrentText(qdt.toString("HH:mm"))
            self._last_valid = qdt
        finally:
            self.date_edit.blockSignals(False)
            self.time_combo.blockSignals(False)

    def setMinimumDateTime(self, qdt: QDateTime) -> None:
        self._min_dt = qdt
        self.date_edit.setMinimumDate(qdt.date())
        if self.dateTime() < qdt:
            self.setDateTime(qdt)

    # -- nội bộ --
    def _on_changed(self, *args) -> None:
        # Giờ gõ tay sai định dạng -> trả về giá trị hợp lệ gần nhất
        if parse_time(self.time_combo.currentText()) is None:
            self.time_combo.blockSignals(True)
            try:
                self.time_combo.setCurrentText(
                    self._last_valid.toString("HH:mm"))
            finally:
                self.time_combo.blockSignals(False)
            return
        # Không cho hẹn quá khứ: kẹp về tối thiểu
        if self._min_dt is not None and self.dateTime() < self._min_dt:
            self.setDateTime(self._min_dt)
            self.dateTimeChanged.emit()
            return
        self._last_valid = self.dateTime()
        self.dateTimeChanged.emit()
