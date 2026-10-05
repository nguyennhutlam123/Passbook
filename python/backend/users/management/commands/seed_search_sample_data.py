from datetime import date
from decimal import Decimal
import secrets

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from books.models import (
    Book,
    BookEdition,
    BookIdentifier,
    BookWork,
    BookWorkSubject,
    Category,
    SaleListing,
)
from users.models import Faculty, Major, Subject, University, User


PREFIX = 'search-sample-'
UNIVERSITIES = (
    {
        'name': 'Đại học Sư phạm Thành phố Hồ Chí Minh',
        'code': PREFIX + 'hcmue',
        'faculty': 'Khoa Toán - Tin học',
        'faculty_code': PREFIX + 'mathematics',
        'major': 'Sư phạm Toán',
        'major_code': PREFIX + 'mathematics-education',
    },
    {
        'name': 'Đại học Sư phạm Thành phố Hồ Chí Minh',
        'code': PREFIX + 'hcmue',
        'faculty': 'Khoa Vật lý',
        'faculty_code': PREFIX + 'physics',
        'major': 'Sư phạm Vật lý',
        'major_code': PREFIX + 'physics-education',
    },
    {
        'name': 'Đại học Bách khoa Thành phố Hồ Chí Minh',
        'code': PREFIX + 'hcmut',
        'faculty': 'Khoa Khoa học và Kỹ thuật Máy tính',
        'faculty_code': PREFIX + 'computer-science',
        'major': 'Khoa học Máy tính',
        'major_code': PREFIX + 'computer-science-major',
    },
    {
        'name': 'Đại học Bách khoa Thành phố Hồ Chí Minh',
        'code': PREFIX + 'hcmut',
        'faculty': 'Khoa Khoa học và Kỹ thuật Máy tính',
        'faculty_code': PREFIX + 'computer-science',
        'major': 'Kỹ thuật Phần mềm',
        'major_code': PREFIX + 'software-engineering',
    },
    {
        'name': 'Đại học Sư phạm Thành phố Hồ Chí Minh',
        'code': PREFIX + 'hcmue',
        'faculty': 'Khoa Toán - Tin học',
        'faculty_code': PREFIX + 'mathematics',
        'major': 'Toán ứng dụng',
        'major_code': PREFIX + 'applied-mathematics',
    },
)

SAMPLES = (
    {
        'title': 'Đại số tuyến tính cơ bản',
        'description': 'Giáo trình ma trận, định thức và không gian vector cho sinh viên năm nhất.',
        'subject': 'Đại số tuyến tính',
        'subject_code': 'MAT201',
        'category': 'Giáo trình',
        'category_slug': 'giao-trinh',
        'price': Decimal('45000'),
        'condition': 'like_new',
        'year': 2023,
        'edition': 'Tái bản lần thứ hai',
        'isbn': PREFIX + 'isbn-mat201',
        'seller_key': 'math',
    },
    {
        'title': 'Cơ học đại cương',
        'description': 'Tài liệu ôn tập động học, động lực học và các định luật bảo toàn.',
        'subject': 'Cơ học',
        'subject_code': 'PHY101',
        'category': 'Giáo trình',
        'category_slug': 'giao-trinh',
        'price': Decimal('60000'),
        'condition': 'good',
        'year': 2022,
        'edition': 'Ấn bản sinh viên 2022',
        'isbn': PREFIX + 'isbn-phy101',
        'seller_key': 'physics',
    },
    {
        'title': 'Lập trình C++ thực hành',
        'description': 'Bài tập C++ về biến, hàm, lớp, kế thừa và cấu trúc dữ liệu.',
        'subject': 'Lập trình C++',
        'subject_code': 'CPP201',
        'category': 'Giáo trình',
        'category_slug': 'giao-trinh',
        'price': Decimal('95000'),
        'condition': 'used',
        'year': 2024,
        'edition': 'Phiên bản thực hành 2024',
        'isbn': PREFIX + 'isbn-cpp201',
        'seller_key': 'programming',
    },
    {
        'title': 'Cơ sở dữ liệu và SQL',
        'description': 'Thiết kế ERD, chuẩn hóa dữ liệu và truy vấn SQL.',
        'subject': 'Cơ sở dữ liệu',
        'subject_code': 'DB202',
        'category': 'Giáo trình',
        'category_slug': 'giao-trinh',
        'price': Decimal('120000'),
        'condition': 'new',
        'year': 2025,
        'edition': 'Ấn bản thứ ba',
        'isbn': PREFIX + 'isbn-db202',
        'seller_key': 'database',
    },
    {
        'title': 'Xác suất thống kê ứng dụng',
        'description': 'Các phân phối xác suất, ước lượng và kiểm định giả thuyết.',
        'subject': 'Xác suất thống kê',
        'subject_code': 'STA203',
        'category': 'Giáo trình',
        'category_slug': 'giao-trinh',
        'price': Decimal('80000'),
        'condition': 'like_new',
        'year': 2025,
        'edition': 'Bản cập nhật 2025',
        'isbn': PREFIX + 'isbn-sta203',
        'seller_key': 'statistics',
    },
)


class Command(BaseCommand):
    help = 'Create five rerunnable catalog search/filter fixtures in the local test database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm-local-test-db',
            action='store_true',
            help='Confirm the target is 127.0.0.1:3308/passbook_v12_lite_test.',
        )

    def handle(self, *args, **options):
        if not options['confirm_local_test_db']:
            raise CommandError('Pass --confirm-local-test-db to confirm the local target.')

        database = connection.settings_dict
        expected = {
            'NAME': 'passbook_v12_lite_test',
            'HOST': '127.0.0.1',
            'PORT': '3308',
            'USER': 'root',
        }
        if any(str(database.get(key, '')) != value for key, value in expected.items()):
            raise CommandError(
                'Refusing to seed: Django is not configured for the approved local DB.',
            )

        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            database_name = cursor.fetchone()[0]
        if database_name != expected['NAME']:
            raise CommandError(
                'Refusing to seed: the active SQL database is not passbook_v12_lite_test.',
            )

        with transaction.atomic():
            created = self._seed()

        self.stdout.write(self.style.SUCCESS(
            f'Created or reused {created} search sample books in {database_name}. '
            'No existing records were deleted or overwritten; the Lite schema has no '
            'book-level location field.',
        ))

    def _seed(self):
        now = timezone.now()
        universities = {}
        faculties = {}
        majors = {}
        for row in UNIVERSITIES:
            university = self._get_or_create(
                University,
                {'code': row['code']},
                {
                    'name': row['name'],
                    'status': 'ACTIVE',
                    'created_at': now,
                },
            )
            self._assert_value(university, 'name', row['name'])
            universities[row['code']] = university

            faculty = self._get_or_create(
                Faculty,
                {
                    'university': university,
                    'code': row['faculty_code'],
                },
                {
                    'name': row['faculty'],
                    'status': 'ACTIVE',
                    'created_at': now,
                },
            )
            self._assert_value(faculty, 'name', row['faculty'])
            faculties[row['faculty_code']] = faculty

            major = self._get_or_create(
                Major,
                {
                    'faculty': faculty,
                    'code': row['major_code'],
                },
                {
                    'name': row['major'],
                    'status': 'ACTIVE',
                    'created_at': now,
                },
            )
            self._assert_value(major, 'name', row['major'])
            majors[row['major_code']] = major

        sellers = {}
        for index, row in enumerate(UNIVERSITIES):
            seller_key = SAMPLES[index]['seller_key']
            email = f'{PREFIX}{seller_key}@example.invalid'
            expected_name = f'Người bán mẫu {SAMPLES[index]["title"]}'
            seller, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'password_hash': make_password(secrets.token_urlsafe(32)),
                    'full_name': expected_name,
                    'role': 'STUDENT',
                    'status': 'ACTIVE',
                    'university': universities[row['code']],
                    'faculty': faculties[row['faculty_code']],
                    'major': majors[row['major_code']],
                    'created_at': now,
                    'updated_at': now,
                },
            )
            if not created:
                self._assert_value(seller, 'full_name', expected_name)
                self._assert_value(seller, 'role', 'STUDENT')
                self._assert_value(seller, 'status', 'ACTIVE')
                if (
                    seller.university_id != universities[row['code']].id
                    or seller.faculty_id != faculties[row['faculty_code']].id
                    or seller.major_id != majors[row['major_code']].id
                ):
                    User.objects.filter(pk=seller.pk).update(
                        university=universities[row['code']],
                        faculty=faculties[row['faculty_code']],
                        major=majors[row['major_code']],
                        updated_at=now,
                    )
                    seller.refresh_from_db()
            sellers[seller_key] = seller

        for index, sample in enumerate(SAMPLES):
            row = UNIVERSITIES[index]
            seller = sellers[sample['seller_key']]
            subject = self._get_or_create(
                Subject,
                {'code': sample['subject_code']},
                {
                    'name': sample['subject'],
                    'description': f'Môn học mẫu cho tìm kiếm: {sample["subject"]}.',
                    'credits': 3,
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            self._assert_value(subject, 'name', sample['subject'])
            category = self._get_or_create(
                Category,
                {'slug': sample['category_slug']},
                {
                    'name': sample['category'],
                    'description': 'Danh mục synthetic phục vụ acceptance test.',
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            self._assert_value(category, 'name', sample['category'])
            work = self._get_or_create(
                BookWork,
                {'title': sample['title'], 'created_by': seller},
                {
                    'description': sample['description'],
                    'author_name': 'Nhóm biên soạn giáo trình',
                    'category': category,
                    'status': 'ACTIVE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            self._assert_value(work, 'description', sample['description'])
            BookWorkSubject.objects.get_or_create(
                book_work=work,
                subject=subject,
                defaults={'is_primary': True, 'created_at': now},
            )
            edition = self._get_or_create(
                BookEdition,
                {'book_work': work, 'edition_name': sample['edition']},
                {
                    'edition_number': 1,
                    'publisher_name': 'Nhà xuất bản Giáo dục',
                    'publication_year': sample['year'],
                    'publication_date': date(sample['year'], 1, 1),
                    'page_count': 240 + index * 24,
                    'format': 'PAPERBACK',
                    'description': sample['description'],
                    'created_at': now,
                    'updated_at': now,
                },
            )
            self._assert_value(edition, 'publication_year', sample['year'])
            BookIdentifier.objects.get_or_create(
                identifier_type='SAMPLE',
                identifier_value=sample['isbn'],
                defaults={'book_edition': edition, 'created_at': now},
            )
            book = self._get_or_create(
                Book,
                {'book_edition': edition, 'owner': seller},
                {
                    'condition_label': sample['condition'].upper(),
                    'condition_description': f'Tình trạng: {sample["condition"]}.',
                    'acquisition_type': 'PURCHASED',
                    'status': 'AVAILABLE',
                    'created_at': now,
                    'updated_at': now,
                },
            )
            self._assert_value(book, 'status', 'AVAILABLE')
            listing = self._get_or_create(
                SaleListing,
                {'book': book},
                {
                    'seller': seller,
                    'title': sample['title'],
                    'description': sample['description'],
                    'price': sample['price'],
                    'currency': 'VND',
                    'status': 'ACTIVE',
                    'published_at': now,
                    'expires_at': None,
                    'created_at': now,
                    'updated_at': now,
                },
            )
            self._assert_value(listing, 'title', sample['title'])
            self._assert_value(listing, 'status', 'ACTIVE')

        return len(SAMPLES)

    @staticmethod
    def _get_or_create(model, lookup, defaults):
        instance, _created = model.objects.get_or_create(**lookup, defaults=defaults)
        return instance

    @staticmethod
    def _assert_value(instance, field, expected):
        if getattr(instance, field) != expected:
            raise CommandError(
                f'Existing search fixture conflicts at {instance._meta.label}.{field}; '
                'no conflicting record was overwritten.',
            )
