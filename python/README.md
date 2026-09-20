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
- `backend/users/`: người dùng, đăng ký, đăng nhập, profile và JWT.
- `backend/books/`: sách, ảnh, tìm kiếm, favorites và my-books.
- `backend/messaging/`: conversations và messages.
- `backend/notifications/`: notifications.
- `backend/reports/`: reports.

## Yêu cầu

- Python 3.9 trở lên
- MySQL/XAMPP đang chạy database `passbook_db`
- Trình duyệt hiện đại

## Cài đặt backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Đặt các biến môi trường theo `backend/.env.example` (shell hiện tại hoặc công cụ quản lý môi trường). Không commit file `.env`.

## Chạy backend

```bash
cd backend
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8000
```

## Chạy frontend

Từ thư mục gốc:

```bash
python3 -m http.server 3000 --directory frontend
```

Mở `http://127.0.0.1:3000`.

## Database

- Database: `passbook_db`
- Schema hiện tại gồm 12 bảng nghiệp vụ.
- Không sử dụng các bảng Django `auth_user` hoặc `authtoken_token`.
- Các model nghiệp vụ là unmanaged; không chạy migrations để tạo hoặc thay đổi schema hiện tại.

## API overview

- **Auth:** register, login, authenticated user, profile, change password.
- **Books:** danh sách, chi tiết, CRUD, tìm kiếm/lọc/sắp xếp, ảnh và my-books.
- **Favorites:** thêm, xóa và danh sách sách yêu thích.
- **Messaging:** conversations và messages.
- **Notifications:** danh sách và đánh dấu đã đọc.
- **Reports:** tạo report và danh sách report của người dùng.
- **Profiles:** profile người dùng và seller profile công khai.

## Demo data

Ứng dụng dùng dữ liệu hiện có trong `passbook_db`. Tài khoản test tạm thời được tạo trong quá trình kiểm thử và không được giữ lại trong database.

Ảnh sách hiện được thêm bằng URL vì API backend không hỗ trợ multipart upload.

Để thêm dữ liệu demo phong phú (an toàn khi chạy lặp lại), chạy lệnh sau từ thư mục `backend/`:

```bash
python manage.py seed_demo_data
```

Lệnh chỉ tạo các bản ghi còn thiếu (6 trường, 40 người dùng, 30 môn học, 6 danh mục,
12 địa điểm, 120 sách, 240 ảnh, 120 yêu thích, 36 cuộc trò chuyện, 108 tin nhắn,
60 thông báo và 12 báo cáo). Lệnh không chạy migrations, không xóa hoặc reset dữ liệu
hiện có. Tài khoản demo dùng mật khẩu `PassbookDemo123!`; chỉ dùng trong môi trường demo.
