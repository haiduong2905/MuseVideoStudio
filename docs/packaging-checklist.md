# Packaging Checklist — trước khi giao bản build cho Khang

Đánh dấu từng mục. Bất kỳ mục nào FAIL -> không giao.

## Trước khi push
- [ ] `python -m unittest discover` xanh 120/120 (từ project root).
- [ ] `python -m py_compile` toàn bộ `app/` + `tests/` không lỗi.
- [ ] Không còn `print(` debug, không TODO/FIXME trong `app/`.
- [ ] UI không còn chữ "SocialUploader" (trừ comment/migration).
- [ ] `muse-video-studio.spec`: icon qua `SPECPATH` tuyệt đối; `datas`
      có `HUONG-DAN.md` và `app/assets` (kiểm tra file tồn tại).
- [ ] `installer/installer.nsi`: `Name`, `InstallDir`, registry,
      shortcut đều là MuseVideoStudio; taskkill cả exe mới lẫn cũ.
- [ ] `.github/workflows/build-windows.yml`: bước test, bundle integrity,
      đường dẫn tuyệt đối `/D` cho makensis — còn nguyên.

## Trên GitHub Actions (theo dõi build)
- [ ] Bước "Run unit tests" xanh.
- [ ] Bước "Build with PyInstaller" xanh, không warning lạ về missing module.
- [ ] Bước "Diagnose bundle": có `dist/MuseVideoStudio/_internal/`,
      `base_library.zip` ≥ 500KB, `python311.dll` tồn tại.
- [ ] Bước NSIS: `MuseVideoStudio-Setup.exe` được tạo, size > 30MB.
- [ ] Release/artifact có đủ 2 file: `MuseVideoStudio-win64.zip`,
      `MuseVideoStudio-Setup.exe`.

## Sau khi cài trên máy Khang (kết hợp docs/gui-checklist.md)
- [ ] Mở app không hiện cmd; icon mới hiện ở taskbar.
- [ ] Tài khoản + hàng đợi cũ còn nguyên (migration DB + keyring).
- [ ] Chạy hết `docs/gui-checklist.md`.

## Bài học SocialUploader (không tái phạm)
| Lỗi cũ | Đã chống |
|---|---|
| Icon NSIS đường dẫn tương đối (v1.7.0) | spec dùng SPECPATH; nsi dùng /DICONICO tuyệt đối |
| Bundle thiếu base_library.zip vẫn ship (v1.0.3) | bước Diagnose bundle throw khi thiếu |
| Build khi test rớt | bước Run unit tests trước PyInstaller |
| dist/ cũ sót lại | bước Clean stale build artifacts |
