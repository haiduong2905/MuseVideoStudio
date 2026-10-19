# GUI Checklist — kiểm tra tay trên bản build Windows

Chạy sau khi cài `MuseVideoStudio-Setup.exe`. Mọi mục phải PASS mới giao.

## Khởi động & khung
- [ ] Mở app: không hiện cửa sổ cmd đen.
- [ ] Theme dark toàn app, sidebar navy 208px, logo + "Muse Video Studio".
- [ ] 7 mục sidebar bấm chuyển màn hình mượt, mục đang chọn highlight.
- [ ] Cuối sidebar: "❓ Trợ giúp" mở được, "Muse Video Studio v1.0.0".
- [ ] Bấm X: hỏi "Thu nhỏ xuống khay / Thoát hẳn / Hủy"; chọn khay ->
      icon dưới khay hệ thống, app vẫn chạy.
- [ ] Chuột phải icon khay: "Mở cửa sổ", "Thoát hẳn" hoạt động.

## Màn 1 — Dashboard
- [ ] 4 thẻ số liệu đúng (dự án / tổng video / đang xử lý / đã hoàn thành).
- [ ] 4 nút "Tạo nhanh" nhảy sang Soạn brief đúng tab.
- [ ] Banner + nút "Tạo video ngay →" hoạt động.
- [ ] "Dự án gần đây" hiện đúng, "Xem tất cả" sang màn Dự án.

## Màn 2 — Soạn brief
- [ ] Chưa có dự án: bấm "Xuất brief" báo "Hãy tạo dự án trước".
- [ ] "＋ Dự án mới": tạo được, mã trùng báo lỗi rõ.
- [ ] Thiếu prompt: bấm xuất báo "Hãy nhập mô tả".
- [ ] "＋ Thêm ảnh": chọn nhiều ảnh, hiện (n/9), quá 9 không nhận thêm.
- [ ] "Xuất brief": hiện popup thành công; paste ra Notepad đúng định dạng
      `[BRIEF] Mã dự án: ... | Cảnh: ...` (đối chiếu design doc mục 6).
- [ ] Nút radio tỉ lệ/thời lượng: mục đang chọn highlight viền tím.

## Màn 3 — Dự án
- [ ] Combo dự án liệt kê đúng; đổi dự án -> danh sách cảnh đổi theo.
- [ ] "Thêm cảnh" nhảy sang Soạn brief.
- [ ] Bấm cảnh: panel phải hiện prompt + chip trạng thái + meta.
- [ ] "Sửa trong Soạn brief": form nạp đúng dữ liệu cảnh, xuất xong cập nhật.
- [ ] "Xem trước": hiện đúng brief text.
- [ ] "Xuất brief": copy cả dự án, paste ra Notepad đủ số cảnh.
- [ ] Kéo-thả đổi thứ tự cảnh, tắt mở app vẫn giữ thứ tự.
- [ ] "Xóa cảnh" hỏi xác nhận trước khi xóa.

## Màn 4 — Thư viện (mailbox)
- [ ] Chưa cấu hình manifest: "Kiểm tra ngay" báo hướng dẫn vào Cài đặt.
- [ ] Nhập manifest URL hợp lệ ở Cài đặt, khởi động lại app:
      video mới tự tải về `D:/MuseVideoStudio/Output/<MÃ DỰ ÁN>/`.
- [ ] Tiến trình % chạy mượt; xong -> chip "Đã hoàn thành".
- [ ] Video lỗi URL: sau 3 lần thử -> "Đã thất bại" + lý do rõ.
- [ ] Poll lần 2 không tải trùng video cũ.
- [ ] "Tự động thêm vào hàng đợi" BẬT: video về là có mặt ở Lịch đăng.
- [ ] "Xem" mở trình phát video; "Mở thư mục" mở đúng folder.
- [ ] Tab "Đã hoàn thành (n)" / "Đã thất bại (n)" đếm đúng.

## Màn 5 — Lịch đăng
- [ ] Tab Lịch đăng: lịch tháng hiện đúng, chi tiết bài đăng bên phải.
- [ ] "Tạo lịch đăng": batch dialog mở được, thêm video + xếp lịch nhanh OK.
- [ ] Tab "Hàng đợi đăng": bảng hiện video, lọc trạng thái đúng.
- [ ] Chuột phải: Chi tiết / Sửa / Xóa / Đăng ngay đều chạy.
- [ ] Tab "Lịch sử đăng": chỉ hiện video đã xong.
- [ ] Thêm video YouTube/Facebook: upload ngay, trạng thái "Đã lên lịch"
      (native schedule) — đúng hành vi SocialUploader.
- [ ] TikTok đến giờ: video vào inbox + popup nhắc "Đã đăng / Nhắc lại 15'".

## Màn 6 — Tài khoản MXH
- [ ] Tài khoản đã nối ở SocialUploader cũ hiện "Đã kết nối" ngay,
      không phải nối lại (kiểm tra keyring migrate-on-read).
- [ ] "Kết nối tài khoản khác" mở dialog nối được.
- [ ] "Ngắt kết nối" hỏi xác nhận, xong mất khỏi danh sách.

## Màn 7 — Cài đặt
- [ ] Đổi thư mục lưu video, lưu, mở lại app vẫn nhớ.
- [ ] Đổi chu kỳ poll + toggle auto-insert, lưu báo "khởi động lại app".
- [ ] Khởi động lại: worker dùng cấu hình mới.

## Migration từ SocialUploader
- [ ] Cài đè khi SocialUploader đang chạy: installer tự tắt cả 2 app.
- [ ] Lần đầu mở: DB cũ (tài khoản, hàng đợi, lịch sử) còn nguyên.
- [ ] Token keyring cũ đọc được (không phải đăng nhập lại).
