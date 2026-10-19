# Muse Video Studio — App desktop quản lý video + đăng đa nền tảng

App Windows (Python 3.11 + PySide6), UI tiếng Việt, dark theme theo mockup của Khang.
Kế thừa toàn bộ ruột SocialUploader (upload/scheduler/accounts), thêm pipeline
brief → mailbox → thư viện video tự động.

Pipeline: Khang soạn brief trong app → paste vào chat → assistant dựng video →
cập nhật manifest mailbox → app tự tải về máy, phân loại theo dự án →
tự chèn vào hàng đợi đăng → đăng đúng giờ lên YouTube / Facebook / TikTok.

## Kiến trúc

```
muse-video-studio/
  app/
    main.py            Entry point, QApplication, crash.log, single-instance
    ui/
      main_window.py   Sidebar 7 màn hình + content area (QStackedWidget)
      dashboard.py     Màn 1: thống kê, tạo nhanh, dự án gần đây        [Phase 4]
      brief_composer.py Màn 2: soạn brief, xuất brief chuẩn             [Phase 4]
      projects.py      Màn 3: quản lý dự án + cảnh (drag reorder)      [Phase 4]
      library.py       Màn 4: hàng đợi tải + thư viện (mailbox worker)  [Phase 4]
      scheduler_view.py Màn 5: lịch đăng (dùng core/scheduler.py)
      accounts_view.py Màn 6: tài khoản MXH (dùng platforms/)
      settings_view.py Màn 7: cài đặt + cấu hình mailbox
      detail_dialog.py KẾ THỪA: chi tiết video, trạng thái từng nền tảng
      batch_dialog.py  KẾ THỪA: thêm nhiều video + xếp lịch nhanh
      combos_dialog.py KẾ THỪA: quản lý combo kênh
      tiktok_reminder.py KẾ THỪA: popup nhắc đăng tay TikTok + snooze 15'
      theme.py         Theme dark theo docs/design-tokens.md          [Phase 2]
      app_icon.py      Icon app (1 chỗ duy nhất)
    core/
      db.py            SQLite + migrate từ SocialUploader + bảng mới
                       (projects, briefs, library, mailbox)           [bảng mới: Phase 4]
      scheduler.py     KẾ THỪA: QThread quét 30s; YT/FB upload ngay +
                       native schedule; TikTok đúng giờ hẹn vào inbox
      mailbox.py       MỚI: poll manifest → download → phân loại → dedup [Phase 4]
      brief.py         MỚI: model brief + xuất brief chuẩn             [Phase 4]
      secrets.py       Keyring, service "MuseVideoStudio", fallback đọc
                       service cũ "SocialUploader" (migrate-on-read)
      autostart.py     Registry HKCU Run, value "MuseVideoStudio"
      thumbnails.py    KẾ THỪA: chuẩn hóa ảnh bìa JPEG 1280x720 ≤2MB
      config.py        KẾ THỪA + thêm cấu hình mailbox
    platforms/
      base.py, youtube.py, facebook.py, tiktok.py, oauth_callback.py
                       KẾ THỪA NGUYÊN VẸN (kể cả fix TikTok false-success v1.9.1)
  docs/
    design-tokens.md   Token màu/font/spacing/component từ mockup
    gui-checklist.md   Checklist test tay 7 màn hình                  [Phase 5]
    packaging-checklist.md  Checklist chống lỗi build kiểu cũ         [Phase 6]
  tests/               Unit tests (mục tiêu ≥60, pytest xanh 100%)    [Phase 5]
  installer/installer.nsi  NSIS, đường dẫn tuyệt đối qua /D
  .github/workflows/build-windows.yml  Build + Verify bundle integrity
  muse-video-studio.spec  PyInstaller, icon tuyệt đối từ SPECPATH
```

## Quy tắc (kế thừa + mới)

- Không hardcode secret trong repo. Client ID/secret nhập qua UI, lưu keyring.
- UI chỉ dùng token trong `docs/design-tokens.md`; không mã màu lẻ tẻ.
- Mỗi video 1 `scheduled_at` chung; từng nền tảng tick bật/tắt + trạng thái riêng.
- Upload thất bại: retry tối đa 5 lần, giãn cách 15 phút, log rõ lỗi.
- Mailbox: retry tải 3 lần; dedup theo manifest `id`; chỉ append manifest, không sửa entry cũ.
- Máy phải bật + app đang chạy (kể cả thu gọn khay) thì scheduler + mailbox mới chạy.
- Đóng gói: PyInstaller one-dir qua GitHub Actions → Releases; build đỏ nếu thiếu
  base_library.zip / python311.dll / icon (bài học SocialUploader v1.0.3).
- Quy trình làm việc: `WORKFLOW.md` — mỗi phase có gate, không qua gate không sang phase mới.
