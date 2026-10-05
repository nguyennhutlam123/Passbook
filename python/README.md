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
- `frontend/workspace.html`: giỏ hàng, checkout, orders và phiếu mượn.
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

Đặt các biến môi trường theo `backend/.env.example` trong shell hiện tại hoặc công cụ quản lý môi trường. Với cấu hình local, có thể sao chép file mẫu thành `backend/.env`, điền Gmail App Password vào đó rồi nạp file khi chạy backend. Không commit file `.env`.

Email xác nhận đơn hàng và email khi quản trị viên đổi trạng thái đơn dùng SMTP hiện có. Cần cấu hình `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL`; nếu thiếu thông tin SMTP, thông báo trong ứng dụng vẫn được tạo nhưng backend ghi rõ lỗi gửi email vào log.

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
- Schema hiện hữu cần áp dụng một lần `../docs/database/passbook_v1.2_lite_request_planned_at_upgrade.sql`
  để lưu ngày dự định mua/mượn/bán trên yêu cầu sách; không nhầm trường này với ngày hết hạn.
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
- **Commerce:** cart, checkout, sale/borrow orders, payment simulation, shipping/tracking,
  return/refund.
- **Borrow:** tin cho mượn mới ở trạng thái `PENDING` và chỉ công khai sau khi Admin duyệt.
  Người mượn thêm tin đang hoạt động vào cart, chọn ngày bắt đầu/ngày trả và checkout để tạo
  `Order` cùng `BorrowOrder`. Phiếu mượn dùng COD khi giao; backend khóa listing và Book, tự
  tạo Shipment và giữ phiếu ở `PENDING`. Chỉ khi Admin cập nhật giao thành công (xác nhận đã
  thu COD), phiếu mới chuyển sang `ACTIVE` và sách sang `ON_LOAN`. Người mượn gửi yêu cầu trả,
  tạo Shipment chiều về; Admin quản lý vận chuyển. Khi Admin xác nhận đã nhận sách, phiếu/Order
  hoàn tất, sách được mở bán/cho mượn lại và phí trễ được chốt theo số chu kỳ 24 giờ hoàn tất.
  Phiếu quá hạn được chuyển sang `OVERDUE` khi danh sách phiếu được truy cập và bằng command
  `python manage.py mark_overdue_borrow_orders`; production nên chạy command định kỳ (ví dụ mỗi
  giờ). Phí trễ ước tính theo mức/ngày trong snapshot và được chốt khi Admin xác nhận trả sách.
  Reservation cũ không còn dùng để tạo yêu cầu mượn mới.
- **Requests:** dự định mua/bán, book requests, matching và interests.
- **Favorites:** thêm, xóa và danh sách sách yêu thích.
- **Messaging:** conversations và messages.
- **Notifications:** danh sách và đánh dấu đã đọc.
- **Reports:** tạo report và danh sách report của người dùng.
- **Profiles:** profile người dùng và seller profile công khai.

Cart coi mỗi listing là một bản duy nhất: API chặn item trùng, báo giá lại từ listing trong
database và không nhận giá/tổng tiền từ frontend. Cart dùng chung cho cả BUY và BORROW; checkout
BUY giữ nguyên phương thức thanh toán đã chọn, còn checkout chỉ gồm BORROW dùng COD để yêu cầu
được tạo mà không phụ thuộc Fake/Online payment. Shipment BORROW được tạo tự động và chỉ Admin
cập nhật trạng thái giao hàng. Fake checkout chỉ hoạt động khi cấu hình
`PASSBOOK_ENVIRONMENT=local` (hoặc `test`) và `PASSBOOK_FAKE_PAYMENTS_ENABLED=true`. Phí vận
chuyển hiện là 0 vì Lite schema/project chưa có quy tắc tính phí giao hàng.

BUY và BORROW là hai listing model riêng đã có trong Lite schema; không thêm cột hay migration.
Tin BUY và BORROW đều cần Admin duyệt trước khi xuất hiện công khai. BORROW listing không xuất
hiện trong trang Mua; sau checkout, Admin tiếp nhận và điều phối cả lượt giao lẫn lượt trả sách.

Admin duyệt hoặc từ chối tin BUY và BORROW trong `Admin Dashboard > Kiểm duyệt tin`; hai loại
tin có danh sách riêng và chỉ listing `PENDING` mới có thể được xử lý. Khi người đăng sửa một tin
đang công khai, tin trở lại `PENDING` và cần Admin duyệt lại trước khi xuất hiện công khai. Tiền
đặt cọc của tin BORROW là tùy chọn, không có cờ bắt buộc đặt cọc.

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
