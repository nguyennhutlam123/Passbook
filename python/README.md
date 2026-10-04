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

Đặt các biến môi trường theo `backend/.env.example` trong shell hiện tại hoặc công cụ quản lý môi trường. Với cấu hình local, có thể sao chép file mẫu thành `backend/.env`, điền Gmail App Password vào đó rồi nạp file khi chạy backend. Không commit file `.env`.

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
- **Books:** danh sách, chi tiết, tin đăng CRUD, ảnh và my-books.
- **Commerce:** cart, checkout, order, payment simulation, shipping/tracking, return/refund.
- **Requests:** dự định mua/bán, book requests, matching và interests.
- **Favorites:** thêm, xóa và danh sách sách yêu thích.
- **Messaging:** conversations và messages.
- **Notifications:** danh sách và đánh dấu đã đọc.
- **Reports:** tạo report và danh sách report của người dùng.
- **Profiles:** profile người dùng và seller profile công khai.

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
