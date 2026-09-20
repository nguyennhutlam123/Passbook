"""Create a repeatable, additive dataset for local/demo environments."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from books.models import Book, BookImage, Category, Favorite, Location
from messaging.models import Conversation, Message
from notifications.models import Notification
from reports.models import Report
from users.models import Subject, University, User


MARKER = "[PASSBOOK DEMO]"
PASSWORD = "PassbookDemo123!"


class Command(BaseCommand):
    help = "Add rerunnable demo data without deleting rows or running migrations."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        universities = self._universities(now)
        users = self._users(universities, now)
        subjects = self._subjects(universities, now)
        categories = self._categories(now)
        locations = self._locations(universities, now)
        books = self._books(users, subjects, categories, locations, now)
        images = self._images(books, now)
        favorites = self._favorites(users, books, now)
        conversations = self._conversations(books, users, now)
        messages = self._messages(conversations, users, now)
        notifications = self._notifications(users, books, now)
        reports = self._reports(users, books, now)
        self.stdout.write(self.style.SUCCESS(
            "Demo seed complete: "
            f"{len(universities)} universities, {len(users)} users, "
            f"{len(subjects)} subjects, {len(categories)} categories, "
            f"{len(locations)} locations, {len(books)} books, "
            f"{len(images)} images, {len(favorites)} favorites, "
            f"{len(conversations)} conversations, {len(messages)} messages, "
            f"{len(notifications)} notifications, {len(reports)} reports."
        ))

    def _get_or_create(self, model, lookup, defaults):
        obj, _ = model.objects.get_or_create(defaults=defaults, **lookup)
        return obj

    def _universities(self, now):
        names = [
            ("Đại học Bách khoa Hà Nội", "HUST-DEMO"),
            ("Đại học Quốc gia Hà Nội", "VNU-DEMO"),
            ("Đại học Kinh tế Quốc dân", "NEU-DEMO"),
            ("Đại học Sư phạm Kỹ thuật TP. Hồ Chí Minh", "HCMUTE-DEMO"),
            ("Đại học Khoa học Tự nhiên TP. Hồ Chí Minh", "HCMUS-DEMO"),
            ("Đại học Công nghệ Thông tin TP. Hồ Chí Minh", "UIT-DEMO"),
        ]
        result = []
        for i, (name, code) in enumerate(names, 1):
            result.append(self._get_or_create(
                University, {"code": code},
                {"name": name, "address": f"Cơ sở đào tạo số {i}, Việt Nam",
                 "logo": f"https://example.com/demo/university-{i}.png", "created_at": now},
            ))
        return result

    def _users(self, universities, now):
        result = []
        names = [
            "Nguyễn Minh Anh", "Trần Hoàng Nam", "Lê Thùy Linh", "Phạm Đức Long",
            "Võ Gia Hân", "Đặng Quang Huy", "Bùi Khánh Vy", "Đỗ Nhật Minh",
            "Ngô Hải Yến", "Huỳnh Tuấn Kiệt",
        ]
        for i in range(1, 41):
            result.append(self._get_or_create(
                User, {"email": f"demo.user{i:02d}@passbook.example"},
                {"university": universities[(i - 1) % len(universities)],
                 "name": f"{names[(i - 1) % len(names)]} {i}", "password_hash": make_password(PASSWORD),
                 "phone": f"090000{i:04d}", "role": "student", "is_verified": True,
                 "status": "active", "created_at": now, "updated_at": now},
            ))
        return result

    def _subjects(self, universities, now):
        subjects = [
            ("Cơ học", "MECH"), ("Giải tích 1", "CALC1"), ("Giải tích 2", "CALC2"),
            ("Đại số tuyến tính", "LINALG"), ("Xác suất thống kê", "PROB"),
            ("Vật lý đại cương", "PHYS"), ("Hóa đại cương", "CHEM"),
            ("Lập trình C++", "CPP"), ("Cấu trúc dữ liệu", "DS"),
            ("Giải thuật", "ALG"), ("Cơ sở dữ liệu", "DB"),
            ("Mạng máy tính", "NET"), ("Hệ điều hành", "OS"),
            ("Kỹ thuật lập trình", "SE"), ("Trí tuệ nhân tạo", "AI"),
            ("Kiến trúc máy tính", "ARCH"), ("Toán rời rạc", "DISCRETE"),
            ("Phương trình vi phân", "ODE"), ("Kinh tế vi mô", "MICRO"),
            ("Nguyên lý kế toán", "ACCOUNT"),
        ]
        result = []
        for i in range(1, 31):
            name, code = subjects[(i - 1) % len(subjects)]
            result.append(self._get_or_create(
                Subject, {"university": universities[(i - 1) % len(universities)],
                          "code": f"{code}-{i:02d}"},
                {"name": name, "description": f"Môn học nền tảng: {name}. Tài liệu tham khảo học kỳ.",
                 "created_at": now},
            ))
        return result

    def _categories(self, now):
        categories = [
            ("Giáo trình đại cương", "Toán, lý, hóa và các môn nền tảng"),
            ("Công nghệ thông tin", "Lập trình, dữ liệu và hệ thống"),
            ("Kỹ thuật", "Cơ khí, điện và kỹ thuật ứng dụng"),
            ("Kinh tế - Quản trị", "Kinh tế, tài chính và quản trị"),
            ("Ngoại ngữ", "Tiếng Anh chuyên ngành và giao tiếp"),
            ("Kỹ năng học tập", "Phương pháp học và tài liệu tham khảo"),
        ]
        return [self._get_or_create(
            Category, {"name": name},
            {"description": description, "created_at": now},
        ) for name, description in categories]

    def _locations(self, universities, now):
        names = [
            "Thư viện trung tâm", "Sảnh tòa A", "Cổng chính", "Ký túc xá khu A",
            "Căng tin sinh viên", "Tòa nhà thực hành", "Phòng công tác sinh viên",
            "Sảnh thư viện số", "Nhà đa năng", "Bãi xe phía Đông",
            "Khu giảng đường B", "Trung tâm học liệu",
        ]
        result = []
        for i, name in enumerate(names, 1):
            result.append(self._get_or_create(
                Location, {"university": universities[(i - 1) % len(universities)],
                           "name": name},
                {"description": f"Điểm nhận sách thuận tiện tại cơ sở {i}", "created_at": now},
            ))
        return result

    def _books(self, users, subjects, categories, locations, now):
        titles = [
            "Cơ học - Giáo trình cơ bản", "Bài tập Cơ học có lời giải",
            "Giải tích 1 - Lý thuyết và bài tập", "Giải tích 2 nâng cao",
            "Đại số tuyến tính ứng dụng", "Bài tập Đại số đại cương",
            "Lập trình C++ từ cơ bản đến nâng cao", "Thực hành Lập trình C++",
            "Cấu trúc dữ liệu và Giải thuật", "Bài tập Cấu trúc dữ liệu",
            "Xác suất thống kê cho kỹ sư", "Vật lý đại cương A1",
            "Cơ sở dữ liệu thực hành", "Mạng máy tính căn bản",
            "Kinh tế vi mô - Giáo trình tham khảo", "Toán rời rạc",
            "Phương trình vi phân", "Kỹ thuật lập trình hiện đại",
            "Nhập môn Trí tuệ nhân tạo", "Sổ tay ôn thi đại học",
        ]
        result = []
        for i in range(1, 121):
            title = f"{titles[(i - 1) % len(titles)]} - Quyển {i}"
            remainder = i % 10
            status = ("deleted" if remainder == 0 else
                      "reserved" if remainder == 7 else
                      "sold" if remainder == 8 else
                      "hidden" if remainder == 9 else "available")
            book = self._get_or_create(
                Book, {"title": title},
                {"seller": users[(i - 1) % len(users)],
                 "subject": subjects[(i - 1) % len(subjects)],
                 "category": categories[(i - 1) % len(categories)],
                 "pickup_location": locations[(i - 1) % len(locations)],
                 "description": (
                     f"Sách {title.lower()}, có ghi chú và ví dụ minh họa; "
                     "phù hợp cho sinh viên ôn tập và học theo giáo trình."
                 ),
                 "price": Decimal(35000 + ((i * 137000) % 2450000)),
                 "condition_status": ("new", "like_new", "good", "used")[i % 4],
                 "edition": f"Lần xuất bản {1 + i % 5}",
                 "publication_year": 2015 + i % 11,
                 "status": status, "pickup_note": "Hẹn nhận tại điểm đã chọn trong giờ hành chính",
                 "created_at": now, "updated_at": now},
            )
            if book.status != status:
               book.status = status
               book.save(update_fields=["status"])
            result.append(book)
        return result

    def _images(self, books, now):
        result = []
        for i in range(1, 241):
            book = books[(i - 1) % len(books)]
            image = self._get_or_create(
                BookImage,                 {"book": book, "image_url": (
                    f"https://placehold.co/640x480/eef4ff/1e3a8a"
                    f"?text=PASSBOOK+{i}"
                )},
                {"is_primary": i % 2 == 1, "sort_order": i % 3, "created_at": now},
            )
            result.append(image)
        return result

    def _favorites(self, users, books, now):
        result = []
        for i in range(1, 121):
            result.append(self._get_or_create(
                Favorite, {"user": users[(i - 1) % len(users)],
                           "book": books[(i * 7 - 1) % len(books)]},
                {"created_at": now},
            ))
        return result

    def _conversations(self, books, users, now):
        result = []
        for i in range(1, 37):
            book = books[(i - 1) % len(books)]
            seller = book.seller
            buyer = users[(i + 10) % len(users)]
            if buyer == seller:
                buyer = users[(i + 11) % len(users)]
            result.append(self._get_or_create(
                Conversation, {"book": book, "buyer": buyer, "seller": seller},
                {"created_at": now, "updated_at": now},
            ))
        return result

    def _messages(self, conversations, users, now):
        result = []
        for i, conversation in enumerate(conversations):
            for part in range(1, 4):
                sender = conversation.buyer if part % 2 else conversation.seller
                result.append(self._get_or_create(
                    Message, {"conversation": conversation,
                             "content": f"{MARKER} message {i + 1}-{part}"},
                    {"sender": sender, "is_read": part != 3, "created_at": now},
                ))
        return result

    def _notifications(self, users, books, now):
        result = []
        for i in range(1, 61):
            result.append(self._get_or_create(
                Notification, {"user": users[(i - 1) % len(users)],
                                "title": f"{MARKER} Notification {i}"},
                {"type": "demo", "content": "Seeded demo notification",
                 "reference_id": books[(i - 1) % len(books)].id,
                 "is_read": i % 3 == 0, "created_at": now},
            ))
        return result

    def _reports(self, users, books, now):
        result = []
        for i in range(1, 13):
            result.append(self._get_or_create(
                Report, {"reporter": users[(i - 1) % len(users)],
                         "book": books[(i * 5 - 1) % len(books)],
                         "description": f"{MARKER} report {i}"},
                {"reason": "Demo report", "status": "pending", "created_at": now},
            ))
        return result
