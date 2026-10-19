# WORKFLOW — Quy trình senior gated cho Muse Video Studio

Mục tiêu: **build một lần, đúng ngay từ đầu** — không lặp lại vòng build đi build lại
như SocialUploader (v1.0.3 → v1.9.1: lỗi NSIS đường dẫn tương đối, thiếu
base_library.zip trong bundle, TikTok false-success, UX sửa sau đóng gói...).

## Nguyên tắc

1. **Shift-left**: mọi lỗi phải bị bắt ở phase rẻ nhất (design review → unit test →
   checklist), không để lọt tới tay Khang mới phát hiện.
2. **Gate giữa các phase**: mỗi phase kết thúc bằng review checklist; không qua gate
   thì không sang phase tiếp theo.
3. **Không hardcode, không đoán**: mọi hằng số (đường dẫn, URL, timeout) nằm ở một
   chỗ, có test khóa lại.
4. **Mọi bug từng gặp ở SocialUploader có regression test** trước khi đóng gói.

## Các phase và gate

### Phase 0 — Design tokens (hiện tại)
- Trích xuất đầy đủ màu sắc, font, spacing, component từ mockup → `docs/design-tokens.md`.
- Gate: mọi màn hình trong code chỉ dùng token, không mã màu lẻ tẻ.

### Phase 1 — Khung project
- Copy SocialUploader làm nền, đổi tên app, giữ nguyên `platforms/` + `core/` chưa đụng.
- Gate: `python -m py_compile` toàn bộ file pass; cây thư mục đúng ARCHITECTURE mới.

### Phase 2 — Theme + sidebar 7 màn hình
- Dựng stylesheet dark + sidebar navigation khớp mockup 1:1 (màu, bo góc, chip, toggle).
- Mỗi màn hình là 1 widget riêng, main_window chỉ điều phối.
- Gate: **pixel-review** — chụp từng màn hình (offscreen render), đối chiếu với mockup:
  sidebar, màu accent, chip trạng thái, toggle, thẻ thống kê.

### Phase 3 — Migrate ruột SocialUploader
- Giữ nguyên logic: `platforms/`, `scheduler.py`, `db.py` (mở rộng thêm bảng mới, migrate),
  `secrets.py`, `autostart.py`, `thumbnails.py`, batch/detail dialog, TikTok reminder.
- Adapter: UI mới gọi vào core cũ qua interface, không copy-paste logic rồi sửa linh tinh.
- Gate: toàn bộ test cũ của SocialUploader vẫn pass trên codebase mới (không regression).

### Phase 4 — Module mới (brief, mailbox, library, dashboard, projects)
- `core/brief.py`: model + xuất brief chuẩn (đúng đặc tả mục 6 design doc).
- `core/mailbox.py`: poll manifest → download → phân loại → dedup theo id → retry 3 lần.
- Views: dashboard, brief_composer, projects, library, scheduler_view, accounts_view, settings_view.
- Gate: unit test cho mọi logic mới (brief format, manifest parse, dedup, phân loại,
  retry, auto-insert queue).

### Phase 5 — Test + senior self-review
- Unit tests ≥ 60, chạy `pytest` xanh 100%.
- GUI checklist 7 màn hình (tay, theo `docs/gui-checklist.md`).
- Self-review kiểu senior: đọc lại diff toàn bộ, kiểm tra (a) không còn chuỗi
  "SocialUploader" sót trong UI, (b) không hardcode đường dẫn Windows trong logic,
  (c) mọi except đều log rõ, (d) không có `print` debug.
- Gate: 3 mục trên đều đạt mới sang Phase 6.

### Phase 6 — Verify đóng gói (chống lỗi build kiểu cũ)
- Kiểm tra `muse-video-studio.spec`: đường dẫn tuyệt đối cho icon (bài học v1.7.0),
  datas đầy đủ.
- Kiểm tra workflow `.github/workflows/build.yml`: bước "Verify bundle integrity"
  (base_library.zip, python311.dll, icon) — build đỏ nếu thiếu (bài học v1.0.3).
- Kiểm tra `installer/installer.nsi`: đường dẫn tuyệt đối qua /D (bài học v1.7.1).
- Gate: checklist đóng gói trong `docs/packaging-checklist.md` tick đủ.

### Phase 7 — Bàn giao
- Đóng gói source zip, hướng dẫn Khang: push → tag → build → cài.
- Khang cài xong mới coi là hoàn thành; SocialUploader cũ giữ song song 1 tuần.

## Bài học SocialUploader → áp dụng ngay
| Lỗi cũ | Chống bằng |
|---|---|
| NSIS không mở được icon (đường dẫn tương đối) | spec/nsi dùng đường dẫn tuyệt đối, có checklist |
| Bundle thiếu base_library.zip mà vẫn ship | bước Verify bundle integrity làm build đỏ |
| TikTok false-success (báo có draft khi không có) | giữ fix v1.9.1 + regression test |
| Sửa UX sau đóng gói → build lại | pixel-review ở Phase 2, GUI checklist ở Phase 5 |
| Build lỗi Khang mới phát hiện qua screenshot | mọi phase có gate, không qua gate không build |
