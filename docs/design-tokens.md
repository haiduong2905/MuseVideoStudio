# Design Tokens — trích từ mockup "Muse Video Studio" của Khang

Mọi màn hình chỉ dùng token dưới đây. Không mã màu/font lẻ tẻ trong code.

## Màu sắc

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--bg-app` | `#0A0D16` | Nền toàn app |
| `--bg-sidebar` | `#0D1120` | Sidebar trái |
| `--bg-panel` | `#12172A` | Panel, thẻ, card |
| `--bg-panel-2` | `#161C33` | Card nổi hơn / input |
| `--bg-hover` | `#1B2340` | Hover item sidebar, nút phụ |
| `--border` | `#232B4D` | Viền card, divider |
| `--accent` | `#5B5BD6` | Màu chính (nút, tab active) |
| `--accent-2` | `#7C6CF5` | Gradient nút chính (#5B5BD6 → #7C6CF5) |
| `--text` | `#F1F3FA` | Chữ chính |
| `--text-dim` | `#9AA3C0` | Chữ phụ, placeholder |
| `--text-faint` | `#5D6685` | Chữ mờ (version, hint) |
| `--green` | `#34D399` | Thành công, "Đã kết nối", "Đã hoàn thành" |
| `--blue` | `#60A5FA` | Thông tin, "Đang xử lý", số liệu |
| `--amber` | `#FBBF24` | Cảnh báo, "Đang chờ" |
| `--pink` | `#F472B6` | Số liệu Dự án (mockup) |
| `--red` | `#F87171` | Lỗi, "Đã thất bại", nút xóa |
| `--chip-green-bg` | `rgba(52,211,153,.14)` | Nền chip xanh |
| `--chip-blue-bg` | `rgba(96,165,250,.14)` | Nền chip xanh dương |
| `--chip-amber-bg` | `rgba(251,191,36,.14)` | Nền chip vàng |
| `--chip-red-bg` | `rgba(248,113,113,.14)` | Nền chip đỏ |

## Typography

- Font: `Segoe UI` (Windows), fallback system sans. Không font chữ ngoài.
- Tiêu đề màn hình: 20px, weight 700.
- Tiêu đề khối/panel: 15px, weight 600.
- Chữ thường: 13px. Chữ phụ: 12px, màu `--text-dim`.
- Số liệu thống kê: 22px, weight 700, màu theo token.

## Spacing & Shape

- Sidebar rộng: 208px. Content padding: 24px.
- Bo góc: card/panel 12px, nút 8px, chip 999px (pill), input 8px.
- Khoảng cách giữa các card: 16px. Giữa các khối trong card: 12px.

## Components (theo mockup)

- **Sidebar**: logo "Muse Video Studio" trên cùng; item gồm icon + label; item active có nền
  `--bg-hover` bo 8px, chữ trắng; cuối sidebar: "Muse Video Studio v1.0.0" màu `--text-faint`.
- **Nút chính**: gradient `--accent` → `--accent-2`, chữ trắng, bo 8px, padding 10x18.
- **Nút phụ**: nền `--bg-panel-2`, viền `--border`, chữ `--text`.
- **Chip trạng thái**: pill, chữ 12px weight 600, màu chữ = màu token, nền = chip-bg tương ứng.
- **Thẻ thống kê**: nền `--bg-panel`, bo 12px, label 12px `--text-dim` trên, số 22px màu token dưới.
- **Toggle**: bật = `--accent`, tắt = `--border`.
- **Tab** (Hàng đợi/Đã hoàn thành/Đã thất bại...): tab active nền `--bg-hover` bo 8px chữ trắng.
- **Tiến trình**: thanh nền `--bg-panel-2`, phần đầy gradient accent, bo 999px.
- **Lịch tháng**: nền `--bg-panel` bo 12px; chip sự kiện nhỏ màu theo nền tảng.
- **Thumbnail video**: bo 8px, tỉ lệ 16:9 (dự án) hoặc 9:16 (thư viện, hiển thị crop).

## Quy tắc designer

1. Tiếng Việt toàn bộ UI. Không emoji trong UI (dùng icon vẽ tay/SVG tối giản).
2. Mọi màn hình mới vẽ xong phải qua **pixel-review**: đặt cạnh mockup, kiểm tra
   sidebar / màu / chip / toggle / spacing trước khi coi là xong.
3. Không thêm màn hình, nút, luồng mới ngoài design doc đã duyệt — muốn thêm phải
   hỏi Khang trước.
