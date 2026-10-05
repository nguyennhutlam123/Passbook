from django.core.management.base import BaseCommand

from books.services import mark_overdue_borrow_orders


class Command(BaseCommand):
    help = 'Mark active borrow orders past their expected return time as overdue.'

    def handle(self, *args, **options):
        count = mark_overdue_borrow_orders()
        self.stdout.write(self.style.SUCCESS(
            f'Marked {count} borrow order(s) overdue.',
        ))
