from django.db.models import Case, IntegerField, Value, When


BOOK_CATEGORIES = (
    ('tieu-thuyet', 'Tiểu thuyết', 'Tác phẩm văn học dài và truyện hư cấu'),
    ('tho', 'Thơ', 'Tập thơ và tuyển thơ'),
    ('kich', 'Kịch', 'Kịch bản sân khấu và tác phẩm kịch'),
    ('sach-giao-khoa', 'Sách giáo khoa', 'Sách theo chương trình giáo dục'),
    ('giao-trinh', 'Giáo trình', 'Giáo trình đại học và sách chuyên ngành'),
    ('tai-lieu', 'Tài liệu', 'Tài liệu học tập và tham khảo'),
    ('truyen-tranh', 'Truyện tranh', 'Truyện tranh cho nhiều lứa tuổi'),
)
BOOK_CATEGORY_SLUGS = tuple(slug for slug, _name, _description in BOOK_CATEGORIES)


def is_supported_book_category(category):
    return (
        category is None
        or (
            category.status == 'ACTIVE'
            and category.slug in BOOK_CATEGORY_SLUGS
        )
    )


def category_order_expression():
    return Case(
        *[
            When(name=name, then=Value(index))
            for index, (_slug, name, _description) in enumerate(BOOK_CATEGORIES)
        ],
        default=Value(len(BOOK_CATEGORIES)),
        output_field=IntegerField(),
    )
