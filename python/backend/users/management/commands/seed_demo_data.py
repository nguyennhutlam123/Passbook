"""Create a repeatable, additive dataset for local/demo environments."""

from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from books.models import (
    Book,
    BookEdition,
    BookImage,
    BookWork,
    BookWorkSubject,
    Category,
    Favorite,
    SaleListing,
)
from books.category_taxonomy import BOOK_CATEGORIES
from messaging.models import Conversation, ConversationMember, Message
from notifications.models import Notification
from reports.models import Report
from users.models import Subject, University, User


MARKER = '[PASSBOOK DEMO]'
PASSWORD = 'PassbookDemo123!'


class Command(BaseCommand):
    help = 'Add rerunnable demo data without deleting rows or running migrations.'

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        universities = self._universities(now)
        users = self._users(universities, now)
        subjects = self._subjects(now)
        categories = self._categories(now)
        books = self._books(users, subjects, categories, now)
        images = self._images(books, now)
        favorites = self._favorites(users, books, now)
        conversations = self._conversations(books, users, now)
        messages = self._messages(conversations, users, now)
        notifications = self._notifications(users, books, now)
        reports = self._reports(users, books, now)
        self.stdout.write(self.style.SUCCESS(
            'Demo seed complete: '
            f'{len(universities)} universities, {len(users)} users, '
            f'{len(subjects)} subjects, {len(categories)} categories, '
            f'{len(books)} books, {len(images)} images, '
            f'{len(favorites)} favorites, {len(conversations)} conversations, '
            f'{len(messages)} messages, {len(notifications)} notifications, '
            f'{len(reports)} reports.'
        ))

    @staticmethod
    def _get_or_create(model, lookup, defaults):
        obj, _ = model.objects.get_or_create(defaults=defaults, **lookup)
        return obj

    def _universities(self, now):
        data = [
            ('Đại học Bách khoa Hà Nội', 'HUST-DEMO'),
            ('Đại học Quốc gia Hà Nội', 'VNU-DEMO'),
            ('Đại học Kinh tế Quốc dân', 'NEU-DEMO'),
            ('Đại học Sư phạm Kỹ thuật TP. Hồ Chí Minh', 'HCMUTE-DEMO'),
            ('Đại học Khoa học Tự nhiên TP. Hồ Chí Minh', 'HCMUS-DEMO'),
            ('Đại học Công nghệ Thông tin TP. Hồ Chí Minh', 'UIT-DEMO'),
        ]
        return [
            self._get_or_create(
                University,
                {'code': code},
                {
                    'name': name,
                    'address': f'Cơ sở đào tạo số {index}, Việt Nam',
                    'status': 'ACTIVE',
                    'created_at': now,
                },
            )
            for index, (name, code) in enumerate(data, 1)
        ]

    def _users(self, universities, now):
        names = [
            'Nguyễn Minh Anh', 'Trần Hoàng Nam', 'Lê Thùy Linh',
            'Phạm Đức Long', 'Võ Gia Hân', 'Đặng Quang Huy',
            'Bùi Khánh Vy', 'Đỗ Nhật Minh', 'Ngô Hải Yến',
            'Huỳnh Tuấn Kiệt',
        ]
        return [
            self._get_or_create(
                User,
                {'email': f'demo.user{index:02d}@passbook.example'},
                {
                    'university': universities[(index - 1) % len(universities)],
                    'full_name': f'{names[(index - 1) % len(names)]} {index}',
                    'password_hash': make_password(PASSWORD),
                    'phone': f'090000{index:04d}',
                    'role': 'STUDENT',
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            for index in range(1, 41)
        ]

    def _subjects(self, now):
        data = [
            ('Cơ học', 'MECH'), ('Giải tích 1', 'CALC1'),
            ('Giải tích 2', 'CALC2'), ('Đại số tuyến tính', 'LINALG'),
            ('Xác suất thống kê', 'PROB'), ('Vật lý đại cương', 'PHYS'),
            ('Hóa đại cương', 'CHEM'), ('Lập trình C++', 'CPP'),
            ('Cấu trúc dữ liệu', 'DS'), ('Giải thuật', 'ALG'),
            ('Cơ sở dữ liệu', 'DB'), ('Mạng máy tính', 'NET'),
            ('Hệ điều hành', 'OS'), ('Kỹ thuật lập trình', 'SE'),
            ('Trí tuệ nhân tạo', 'AI'), ('Kiến trúc máy tính', 'ARCH'),
            ('Toán rời rạc', 'DISCRETE'), ('Phương trình vi phân', 'ODE'),
            ('Kinh tế vi mô', 'MICRO'), ('Nguyên lý kế toán', 'ACCOUNT'),
        ]
        result = []
        for index in range(1, 31):
            name, code = data[(index - 1) % len(data)]
            result.append(self._get_or_create(
                Subject,
                {'code': f'{code}-{index:02d}'},
                {
                    'name': name,
                    'description': f'Môn học nền tảng: {name}.',
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            ))
        return result

    def _categories(self, now):
        data = [(name, description) for _slug, name, description in BOOK_CATEGORIES]
        return [
            self._get_or_create(
                Category,
                {'slug': slugify(name)},
                {
                    'name': name,
                    'description': description,
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            for name, description in data
        ]

    def _books(self, users, subjects, categories, now):
        titles = [
            'Cơ học - Giáo trình cơ bản', 'Bài tập Cơ học có lời giải',
            'Giải tích 1 - Lý thuyết và bài tập', 'Giải tích 2 nâng cao',
            'Đại số tuyến tính ứng dụng', 'Bài tập Đại số đại cương',
            'Lập trình C++ từ cơ bản đến nâng cao', 'Thực hành Lập trình C++',
            'Cấu trúc dữ liệu và Giải thuật', 'Bài tập Cấu trúc dữ liệu',
            'Xác suất thống kê cho kỹ sư', 'Vật lý đại cương A1',
            'Cơ sở dữ liệu thực hành', 'Mạng máy tính căn bản',
            'Kinh tế vi mô - Giáo trình tham khảo', 'Toán rời rạc',
            'Phương trình vi phân', 'Kỹ thuật lập trình hiện đại',
            'Nhập môn Trí tuệ nhân tạo', 'Sổ tay ôn thi đại học',
        ]
        result = []
        for index in range(1, 121):
            title = f'{titles[(index - 1) % len(titles)]} - Quyển {index}'
            description = (
                f'Sách {title.lower()}, có ghi chú và ví dụ minh họa; '
                'phù hợp cho sinh viên ôn tập và học theo giáo trình.'
            )
            owner = users[(index - 1) % len(users)]
            work, _ = BookWork.objects.get_or_create(
                title=title,
                created_by=owner,
                defaults={
                    'description': description,
                    'category': categories[(index - 1) % len(categories)],
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            BookWorkSubject.objects.get_or_create(
                book_work=work,
                subject=subjects[(index - 1) % len(subjects)],
                defaults={'is_primary': True, 'created_at': now},
            )
            edition, _ = BookEdition.objects.get_or_create(
                book_work=work,
                edition_name=f'Lần xuất bản {1 + index % 5}',
                defaults={
                    'publication_year': 2015 + index % 11,
                    'created_at': now,
                    'updated_at': now,
                },
            )
            remainder = index % 10
            book_status = (
                'RESERVED' if remainder == 7 else
                'SOLD' if remainder == 8 else
                'UNAVAILABLE' if remainder in (0, 9) else
                'AVAILABLE'
            )
            book, _ = Book.objects.get_or_create(
                book_edition=edition,
                owner=owner,
                defaults={
                    'condition_label': ('NEW', 'LIKE_NEW', 'GOOD', 'USED')[index % 4],
                    'condition_description': None,
                    'status': book_status,
                    'created_at': now,
                    'updated_at': now,
                },
            )
            listing_status = {
                'AVAILABLE': 'ACTIVE',
                'RESERVED': 'RESERVED',
                'SOLD': 'SOLD',
                'UNAVAILABLE': 'CLOSED',
            }[book_status]
            SaleListing.objects.get_or_create(
                book=book,
                defaults={
                    'seller': owner,
                    'title': title,
                    'description': description,
                    'price': Decimal(35000 + ((index * 137000) % 2450000)),
                    'status': listing_status,
                    'published_at': now,
                    'created_at': now,
                    'updated_at': now,
                },
            )
            result.append(book)
        return result

    def _images(self, books, now):
        images = []
        for index in range(1, 241):
            book = books[(index - 1) % len(books)]
            image, _ = BookImage.objects.get_or_create(
                book=book,
                image_url=f'https://placehold.co/640x480/eef4ff/1e3a8a?text=PASSBOOK+{index}',
                defaults={
                    'is_primary': index <= len(books),
                    'sort_order': index % 3,
                    'created_at': now,
                },
            )
            images.append(image)
        return images

    def _favorites(self, users, books, now):
        return [
            self._get_or_create(
                Favorite,
                {
                    'user': users[(index - 1) % len(users)],
                    'book': books[(index * 7 - 1) % len(books)],
                },
                {'created_at': now},
            )
            for index in range(1, 121)
        ]

    def _conversations(self, books, users, now):
        result = []
        for index in range(1, 37):
            book = books[(index - 1) % len(books)]
            owner = book.owner
            requester = users[(index + 10) % len(users)]
            if requester.id == owner.id:
                requester = users[(index + 11) % len(users)]
            conversation = (
                Conversation.objects
                .filter(conversation_type='SALE')
                .filter(members__user=requester)
                .filter(members__user=owner)
                .first()
            )
            if conversation is None:
                conversation = Conversation.objects.create(
                    conversation_type='SALE',
                    created_at=now,
                    updated_at=now,
                )
                ConversationMember.objects.bulk_create([
                    ConversationMember(
                        conversation=conversation,
                        user=requester,
                        joined_at=now,
                    ),
                    ConversationMember(
                        conversation=conversation,
                        user=owner,
                        joined_at=now,
                    ),
                ])
            result.append(conversation)
        return result

    def _messages(self, conversations, users, now):
        result = []
        for index, conversation in enumerate(conversations):
            members = list(
                ConversationMember.objects.filter(
                    conversation=conversation,
                ).select_related('user').order_by('user_id')
            )
            if len(members) < 2:
                continue
            for part in range(1, 4):
                result.append(self._get_or_create(
                    Message,
                    {
                        'conversation': conversation,
                        'content': f'{MARKER} message {index + 1}-{part}',
                    },
                    {
                        'sender': members[(part - 1) % 2].user,
                        'message_type': 'TEXT',
                        'sent_at': now,
                    },
                ))
        return result

    def _notifications(self, users, books, now):
        return [
            self._get_or_create(
                Notification,
                {
                    'user': users[(index - 1) % len(users)],
                    'title': f'{MARKER} Notification {index}',
                },
                {
                    'notification_type': 'DEMO',
                    'content': 'Seeded demo notification',
                    'entity_type': 'BOOK',
                    'entity_id': books[(index - 1) % len(books)].id,
                    'is_read': index % 3 == 0,
                    'created_at': now,
                },
            )
            for index in range(1, 61)
        ]

    def _reports(self, users, books, now):
        result = []
        for index in range(1, 13):
            result.append(self._get_or_create(
                Report,
                {
                    'reporter': users[(index - 1) % len(users)],
                    'book': books[(index * 5 - 1) % len(books)],
                    'description': f'{MARKER} report {index}',
                },
                {
                    'reason': 'Demo report',
                    'status': 'OPEN',
                    'created_at': now,
                },
            ))
        return result
