# Muse Video Studio

App desktop (Windows 10/11) giúp upload video 1 lần, đặt lịch, tool tự đăng lên
**YouTube** / **Facebook Reels** / **TikTok** đúng giờ. Giao diện tiếng Việt.

## Chạy dev

```bat
pip install -r requirements.txt
python -m app.main
```

(Yêu cầu Python 3.11+. Trên Linux test UI với `QT_QPA_PLATFORM=offscreen`.)

## Đóng gói bản cài đặt (trên Windows)

```bat
pip install -r requirements.txt
pyinstaller muse-video-studio.spec
```

File chạy: `dist/MuseVideoStudio/MuseVideoStudio.exe`. Có thể build tự động qua
GitHub Actions (windows-latest) và đăng file ở mục Releases.

## Kết nối tài khoản (làm 1 lần)

1. **Cài đặt** trong app: nhập Client ID/Secret.
   - *YouTube*: Google Cloud Console → tạo OAuth client ID loại **Desktop**,
     bật **YouTube Data API v3**. Lưu ý: app chưa qua kiểm duyệt của Google
     thì video upload lên sẽ bị khóa private.
   - *TikTok*: TikTok Developers → tạo app, bật **Login Kit**, thêm Redirect URI
     `http://localhost:8765/callback`, xin scope `video.upload`.
   - *Facebook*: tạo app ở Meta Developers, lấy **Page access token**
     (cần quyền quản lý Page). Không cần nhập Client ID/Secret.
2. **Tài khoản** trong app: bấm Kết nối từng nền tảng.
   - TikTok đăng ở chế độ **hộp nháp (inbox)**: video nằm trong app TikTok,
     bạn mở app bấm đăng tay. Giới hạn ~5 video chờ / 24 giờ.

## Cách dùng

1. **Thêm video** (hoặc kéo-thả file vào dialog): chọn file, tiêu đề, mô tả,
   hashtag, giờ đăng (tối thiểu sau hiện tại 10 phút), tick nền tảng.
2. App tự đăng đúng giờ — **máy phải bật và app đang chạy**.
   Bật "Tự khởi động cùng Windows" trong Cài đặt để không quên mở app.
3. **Đăng ngay**: bỏ qua lịch hẹn, đăng trong ~30 giây.
4. Thất bại mạng/API: tự thử lại tối đa 5 lần, giãn cách 15 phút; xem chi tiết
   ở panel nhật ký.

Dữ liệu (hàng đợi, log) lưu ở `%APPDATA%/MuseVideoStudio/data.db`.
Token/credential lưu trong Windows Credential Manager (qua keyring),
không nằm trong code.
