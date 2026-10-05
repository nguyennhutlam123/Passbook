from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from books.category_taxonomy import BOOK_CATEGORIES
from books.models import BookRequest, BookWork, Category


class Command(BaseCommand):
    help = 'Reconcile active book categories to the supported seven-category taxonomy.'

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        canonical = {}

        for slug, name, description in BOOK_CATEGORIES:
            category = (
                Category.objects.filter(slug=slug).order_by('id').first()
                or Category.objects.filter(name=name).order_by('id').first()
            )
            if category is None:
                category = Category.objects.create(
                    name=name,
                    slug=slug,
                    description=description,
                    status='ACTIVE',
                    created_at=now,
                    updated_at=now,
                )
            else:
                category.name = name
                category.slug = slug
                category.description = description
                category.status = 'ACTIVE'
                category.updated_at = now
                category.save(update_fields=(
                    'name', 'slug', 'description', 'status', 'updated_at',
                ))
            canonical[name] = category

        canonical_ids = {category.id for category in canonical.values()}
        legacy_categories = Category.objects.exclude(id__in=canonical_ids).order_by('id')
        moved_references = 0
        retired_categories = 0
        textbook_target = canonical['Sách giáo khoa']
        course_target = canonical['Giáo trình']

        for legacy in legacy_categories:
            target = (
                textbook_target
                if legacy.name.strip().casefold() in {'textbook', 'textbooks', 'sách giáo khoa'}
                else course_target
            )
            moved_references += BookWork.objects.filter(
                category_id=legacy.id,
            ).update(category_id=target.id)
            BookRequest.objects.filter(category_id=legacy.id).update(
                category_id=target.id,
            )
            if legacy.status != 'INACTIVE':
                legacy.status = 'INACTIVE'
                legacy.updated_at = now
                legacy.save(update_fields=('status', 'updated_at'))
                retired_categories += 1

        self.stdout.write(self.style.SUCCESS(
            f'Reconciled {len(BOOK_CATEGORIES)} active categories; '
            f'moved {moved_references} book works; '
            f'retired {retired_categories} legacy categories.',
        ))
