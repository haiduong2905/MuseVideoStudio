# Hướng dẫn sử dụng Muse Video Studio

App desktop giúp anh quản lý toàn bộ vòng đời video: soạn brief → nhận video
tự động về máy → lên lịch đăng YouTube / Facebook / TikTok — tất cả trong 1 app.

## 1. Luồng làm việc chuẩn

1. **Soạn brief** (màn *Soạn brief*): điền mô tả video, chọn tỉ lệ/thời lượng,
   thêm ảnh tham chiếu → bấm **Xuất brief**.
2. Brief chuẩn được **copy vào clipboard** → anh **dán vào khung chat**
   với trợ lý để dựng video.
3. Trợ lý dựng xong sẽ đưa video lên **mailbox** → app **tự tải về máy**,
   phân loại theo dự án (màn *Thư viện*).
4. Video mới tự vào **hàng đợi đăng** → app đăng đúng giờ (màn *Lịch đăng*).

## 2. Các màn hình

### Dashboard
Tổng quan: số dự án, tổng video, đang xử lý, đã hoàn thành; nút tạo nhanh;
dự án gần đây.

### Soạn brief
- Chọn **dự án** (hoặc tạo mới bằng nút *＋ Dự án mới*), đặt **tên cảnh**.
- 4 tab: Từ văn bản / Từ ảnh / Từ video / Template.
- **Mô tả video (Prompt)**: viết chi tiết cảnh, tối đa 2000 ký tự.
- **Ảnh tham chiếu**: tối đa 9 ảnh.
- **Điểm chuẩn**: 16:9 / 9:16 / 1:1 (mặc định 9:16).
- **Duration**: 5 / 10 / 15 giây. **Style**: Cinematic, Tự nhiên...
- **Xuất brief**: copy brief chuẩn + lưu vào dự án với trạng thái "đã gửi".

### Dự án
Quản lý các cảnh (brief) theo từng dự án:
- **Thêm cảnh**: sang màn Soạn brief.
- Bấm vào cảnh để xem chi tiết: prompt, trạng thái
  (nháp → đã gửi → đang dựng → đã về kho).
- **Kéo-thả** để sắp xếp lại thứ tự cảnh.
- **Xem trước**: xem lại brief đã xuất. **Xuất brief**: copy toàn bộ
  brief của dự án 1 lần.

### Thư viện (nhận video tự động)
- App tự kiểm tra **mailbox** mỗi 15 phút (đổi được ở Cài đặt).
- Video mới tự tải về `D:/MuseVideoStudio/Output/<Mã dự án>/`.
- 3 tab: **Hàng đợi** (đang tải/đang chờ), **Đã hoàn thành**, **Đã thất bại**.
- **🔄 Kiểm tra ngay**: kiểm tra mailbox ngay, không chờ hết chu kỳ.
- **👁 Xem**: mở video bằng trình phát mặc định.
- **📁 Mở thư mục**: mở folder chứa file.

### Lịch đăng
- **Lịch đăng**: lịch tháng + chi tiết bài đăng (tiêu đề, giờ đăng,
  trạng thái từng nền tảng).
- **Hàng đợi đăng**: danh sách video chờ; lọc theo trạng thái;
  chuột phải: Chi tiết / Sửa / Xóa / Đăng ngay.
- **Lịch sử đăng**: video đã đăng xong.
- **＋ Tạo lịch đăng**: thêm nhiều video 1 lúc + xếp lịch nhanh.
- Lưu ý (giữ nguyên từ bản cũ): YouTube/Facebook **upload ngay khi thêm**,
  giờ hẹn là giờ **công chiếu**; TikTok upload **đúng giờ hẹn** vào hộp thư,
  app sẽ **nhắc anh đăng tay** (có nút *Nhắc lại sau 15 phút*).

### Tài khoản MXH
Danh sách tài khoản đã kết nối. Tài khoản nối ở bản cũ được mang sang,
không cần nối lại. **Ngắt kết nối** sẽ hỏi xác nhận trước.

### Cài đặt
- **Chung**: thư mục lưu video, ngôn ngữ, các toggle tự động.
- **Tự động đăng** (quan trọng):
  - **Manifest URL**: link tới file `manifest.json` của mailbox
    (trợ lý sẽ cấp khi anh nối GitHub xong).
  - **Chu kỳ kiểm tra**: mỗi bao nhiêu phút poll 1 lần.
  - **Tự động thêm video mới vào hàng đợi đăng**: bật/tắt.
  - **Đăng sau khi video về**: video mới sẽ được hẹn đăng sau X phút.
- Đổi Manifest URL / chu kỳ poll có hiệu lực sau khi **khởi động lại app**.

## 3. Đóng cửa sổ

Bấm X sẽ hỏi: **Thu nhỏ xuống khay** (app vẫn chạy nền để tải video
và đăng đúng giờ) hoặc **Thoát hẳn**. Nên chọn thu nhỏ xuống khay.

## 4. Gỡ bản cũ

Sau khi Muse Video Studio chạy ổn ~1 tuần, anh có thể gỡ SocialUploader cũ
trong *Settings → Apps*. Dữ liệu (tài khoản, hàng đợi, lịch sử) đã được
mang sang đầy đủ.
