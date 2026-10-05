# PASSBOOK

PASSBOOK là marketplace MVP giúp sinh viên tìm, mua bán và trao đổi giáo trình trong cùng trường. MVP tập trung vào tìm kiếm sách, tin đăng, yêu thích, nhắn tin, thông báo và báo cáo.

## Kiến trúc

```text
Frontend HTML/CSS/JavaScript
        ↓
Django REST Framework
        ↓
MySQL
```

## Công nghệ

- HTML, CSS, JavaScript
- Django 4.2
- Django REST Framework
- MySQL
- JWT (SimpleJWT)

## Cấu trúc chính

- `frontend/`: các trang HTML, CSS và JavaScript client.
- `backend/config/`: settings và URL API.
- `backend/users/`: người dùng, OTP, profile, địa chỉ, trường/khoa/ngành và JWT.
- `backend/books/`: catalog, tin bán/mượn, ảnh, favorites, dự định mua/bán, đặt giữ và giao dịch.
- `backend/messaging/`: conversations và messages.
- `backend/notifications/`: notifications.
- `backend/reports/`: reports.
- `frontend/workspace.html`: giỏ hàng, checkout, orders, reservation và borrow workflow.
- `frontend/requests.html`: book requests, matching và interests.
- `frontend/admin/`: dashboard, moderation và quản lý người dùng.

## Yêu cầu

- Python 3.9 trở lên
- MariaDB/XAMPP đang chạy database local/test `passbook_v12_lite_test` trên `127.0.0.1:3308`
- Trình duyệt hiện đại

## Cài đặt backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Đặt các biến môi trường theo `backend/.env.example` trong shell hiện tại hoặc công cụ quản lý môi trường. Khi bật OTP, email OTP và email thông báo dùng Django SMTP qua Gmail (`smtp.gmail.com:587`, TLS). Cấu hình SMTP bằng `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL`; cần Google App Password (không dùng mật khẩu đăng nhập Gmail) và không commit file `.env`. `EMAIL_TIMEOUT` (mặc định 10 giây) giới hạn thời gian chờ.

`OTP_ENABLED` mặc định là `false`. Khi tắt, đăng ký không yêu cầu OTP, đăng nhập chỉ dựa trên mật khẩu hợp lệ, đổi email/số điện thoại vẫn yêu cầu đăng nhập nhưng không yêu cầu OTP; forgot/reset password tạm thời bị khóa cho đến khi có cơ chế xác minh an toàn khác. Các API OTP vẫn có trong backend nhưng trả 503 khi OTP bị tắt. Đặt `OTP_ENABLED=true` để bật lại OTP cùng email/SMS delivery hiện có.

## Tạo tài khoản kiểm thử

`python manage.py create_test_accounts` tạo tối thiểu hai Buyer; có thể thêm một Admin bằng `--admin-email`. Tài khoản mới ở trạng thái `ACTIVE`, vì vậy chỉ dùng email test và không dùng mật khẩu thật. Mật khẩu được nhập tương tác (không truyền trong command line), xác nhận hai lần và lưu bằng Django password hasher. Email đã tồn tại sẽ bị bỏ qua, không bị cập nhật. Command chỉ chạy mặc định với `PASSBOOK_ENVIRONMENT=local/dev/test` và database host loopback; database khác cần cờ opt-in `--allow-production`. Kiểm tra mục tiêu bằng `--dry-run` trước khi ghi dữ liệu.

```bash
PASSBOOK_ENVIRONMENT=local python manage.py create_test_accounts \
  --buyer-email buyer1@example.test \
  --buyer-email buyer2@example.test \
  --admin-email admin@example.test \
  --dry-run
```

## Chạy backend

```bash
cd backend
source .venv/bin/activate
set -a
. ./.env
set +a
python manage.py runserver 127.0.0.1:8000
```

## Chạy frontend

Từ thư mục gốc:

```bash
python3 -m http.server 5500 --directory frontend
```

Mở `http://127.0.0.1:5500`. Frontend local gọi Django tại `http://127.0.0.1:8000/api`.

## Database

- Database source-of-truth cho local acceptance: `passbook_v12_lite_test`.
- MariaDB local được xác minh là phiên bản 10.4.28 trên port 3308.
- Schema Lite gồm 41 bảng nghiệp vụ (ngoài các bảng Django framework).
- Không sử dụng các bảng Django `auth_user` hoặc `authtoken_token`.
- Các model nghiệp vụ là unmanaged; không chạy migrations để tạo hoặc thay đổi schema hiện tại.
- Không đổi sang `passbook_db`, không reset/drop hoặc merge dữ liệu giữa hai database.

## API overview

- **Auth:** register/OTP, login/OTP tùy chọn, refresh/logout, password reset và profile.
- **Catalog:** danh sách phân trang, keyword, trường/khoa/ngành, môn/mã môn, ISBN/tác giả,
  phiên bản/năm/ngôn ngữ, condition, khoảng giá và sort. Các lựa chọn filter lấy từ API.
- **Books:** marketplace Mua dùng `sale_listings`; marketplace Mượn dùng `lend_listings`
  và `borrow_terms`. Form đăng tin mặc định BUY cho client/dữ liệu legacy không gửi type.
  Mỗi tin hỗ trợ tối đa 10 ảnh JPG/PNG/WebP/GIF (10 MB/ảnh); backend xác minh định dạng,
  dung lượng và URL với Cloudinary trước khi lưu `BookImage`. Cloudinary cần được cấu hình
  qua `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` và `CLOUDINARY_API_SECRET` trong môi trường.
- **Commerce:** cart, checkout, order, payment simulation, shipping/tracking, return/refund.
- **Borrow:** đăng ký qua `book_reservations`, không qua Cart/Checkout/Order. Với schema Lite
  hiện tại, reservation `CONFIRMED` biểu diễn sách đang được mượn; `COMPLETED` biểu diễn đã trả.
  `expires_at` chỉ là hạn phản hồi request đang `PENDING`, không phải ngày bắt đầu/kết thúc mượn.
- **Requests:** dự định mua/bán, book requests, matching và interests.
- **Favorites:** thêm, xóa và danh sách sách yêu thích.
- **Messaging:** conversations và messages.
- **Notifications:** danh sách và đánh dấu đã đọc.
- **Reports:** tạo report và danh sách report của người dùng.
- **Profiles:** profile người dùng và seller profile công khai.

Cart bán sách coi mỗi listing là một bản duy nhất: API chặn item trùng, báo giá lại từ listing
trong database và không nhận giá/tổng tiền từ frontend. Checkout chỉ tạo Order/Payment, đánh dấu
listing đã bán và xóa cart item sau Fake Payment SUCCESS; FAILURE/CANCEL giữ nguyên Cart. Fake
checkout chỉ hoạt động khi cấu hình `PASSBOOK_ENVIRONMENT=local` (hoặc `test`) và
`PASSBOOK_FAKE_PAYMENTS_ENABLED=true`. Phí vận chuyển hiện là 0 vì Lite schema/project chưa có
quy tắc tính phí giao hàng.

BUY và BORROW là hai listing model riêng đã có trong Lite schema; không thêm cột hay migration.
BORROW listing không xuất hiện trong trang Mua và bị từ chối tại Cart/Checkout. Khi gửi yêu cầu
mượn, backend khóa Book, chuyển listing sang `RESERVED`, rồi khi chủ sách duyệt sẽ chuyển listing
và Book sang `ON_LOAN`. Hoàn tất reservation trả listing về `ACTIVE` và Book về `AVAILABLE`.

## Demo data

Ứng dụng dùng synthetic acceptance fixtures trong `passbook_v12_lite_test` khi kiểm thử local.
Lệnh `seed_lite_acceptance_data --confirm-local-test-db` được khóa vào đúng local database này;
không chạy trên môi trường production.

Ảnh listing được chọn từ máy người dùng, preview cục bộ, upload qua signed Cloudinary flow,
rồi lưu HTTPS image reference qua API. Upload yêu cầu cấu hình Cloudinary cho môi trường chạy.

Để thêm dữ liệu demo phong phú (an toàn khi chạy lặp lại), chạy lệnh sau từ thư mục `backend/`:

```bash
python manage.py seed_demo_data
```

Lệnh chỉ tạo các bản ghi còn thiếu (6 trường, 40 người dùng, 30 môn học, 6 danh mục,
12 địa điểm, 120 sách, 240 ảnh, 120 yêu thích, 36 cuộc trò chuyện, 108 tin nhắn,
60 thông báo và 12 báo cáo). Lệnh không chạy migrations, không xóa hoặc reset dữ liệu
hiện có. Tài khoản demo dùng mật khẩu `PassbookDemo123!`; chỉ dùng trong môi trường demo.

Để tạo riêng năm sách đa dạng phục vụ acceptance test Search/Filter, chạy lệnh sau
từ thư mục `backend/`:

```bash
python manage.py seed_search_sample_data --confirm-local-test-db
```

Lệnh an toàn khi chạy lặp lại, chỉ tạo fixture thiếu và chỉ chạy khi database đích là
`passbook_v12_lite_test` trên `127.0.0.1:3308`. Fixture gồm sách Toán, Vật lý và Công nghệ
thông tin; không xóa hoặc ghi đè dữ liệu hiện có. Schema Lite không liên kết địa điểm với
sách hoặc tin đăng nên fixture không tạo bộ lọc địa điểm giả.
