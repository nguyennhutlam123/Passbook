"""Seed a small, synthetic, rerunnable dataset into the local Lite test DB."""

import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from books.models import (
    Book,
    BookEdition,
    BookIdentifier,
    BookImage,
    BookRequest,
    BookReservation,
    BookWork,
    BookWorkSubject,
    BorrowTerms,
    BorrowOrder,
    Cart,
    CartItem,
    Category,
    CheckoutGroup,
    Favorite,
    LendListing,
    Order,
    Payment,
    Refund,
    RequestInterest,
    RequestMatch,
    Return,
    Review,
    SaleListing,
    SaleOrderItem,
    Shipment,
    ShipmentTracking,
)
from messaging.models import Conversation, ConversationMember, Message
from notifications.models import Notification
from reports.models import Report
from users.models import (
    Faculty,
    Language,
    Major,
    OtpVerification,
    Subject,
    University,
    User,
    UserAddress,
    UserViolation,
)


PREFIX = 'acceptance-fixture-'
FIXTURE_PASSWORD = 'AcceptanceOnly-Pass-42!'


class Command(BaseCommand):
    help = 'Add synthetic Lite acceptance data to the isolated local XAMPP test DB.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm-local-test-db',
            action='store_true',
            help='Confirm the target is 127.0.0.1:3308/passbook_v12_lite_test.',
        )
        parser.add_argument(
            '--book-count',
            type=int,
            default=100,
            help='Number of synthetic books to seed (10-500).',
        )

    def handle(self, *args, **options):
        if not options['confirm_local_test_db']:
            raise CommandError('Pass --confirm-local-test-db to confirm the local target.')
        if not 10 <= options['book_count'] <= 500:
            raise CommandError('--book-count must be between 10 and 500.')

        database = settings.DATABASES['default']
        expected = {
            'NAME': 'passbook_v12_lite_test',
            'HOST': '127.0.0.1',
            'PORT': '3308',
            'USER': 'root',
        }
        if any(str(database.get(key, '')) != value for key, value in expected.items()):
            raise CommandError('Refusing to seed: Django is not configured for the approved local DB.')

        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), VERSION()')
            database_name, version = cursor.fetchone()
        if database_name != expected['NAME']:
            raise CommandError('Refusing to seed: the active SQL database is not passbook_v12_lite_test.')

        with transaction.atomic():
            counts = self._seed(book_count=options['book_count'])

        self.stdout.write(self.style.SUCCESS(
            f'Seeded synthetic fixtures in {database_name} ({version}): '
            + ', '.join(f'{name}={count}' for name, count in counts.items())
            + '. Fixture passwords use a documented local-only test value and Django hashing; OTPs are hashed. '
            + 'No payment is marked PAID.'
        ))

    @staticmethod
    def _once(model, lookup, defaults):
        return model.objects.get_or_create(**lookup, defaults=defaults)[0]

    def _seed(self, *, book_count=100):
        now = timezone.now()
        old = now - timedelta(days=3)
        later = now + timedelta(days=7)
        universities = [
            self._once(University, {'code': PREFIX + f'univ-{i}'}, {
                'name': f'Acceptance University {i}',
                'address': 'Synthetic address',
                'status': 'ACTIVE',
                'created_at': now,
            })
            for i in (1, 2)
        ]
        faculties = [
            self._once(Faculty, {'university': university, 'code': PREFIX + f'faculty-{i}'}, {
                'name': f'Acceptance Faculty {i}',
                'status': 'ACTIVE',
                'created_at': now,
            })
            for i, university in enumerate(universities, 1)
        ]
        majors = [
            self._once(Major, {'faculty': faculty, 'code': PREFIX + f'major-{i}'}, {
                'name': f'Acceptance Major {i}',
                'status': 'ACTIVE',
                'created_at': now,
            })
            for i, faculty in enumerate(faculties, 1)
        ]
        user_defaults = (
            ('seller_1', 'Synthetic Seller One', 'STUDENT', universities[0]),
            ('seller_2', 'Synthetic Seller Two', 'STUDENT', universities[1]),
            ('buyer_1', 'Synthetic Buyer One', 'STUDENT', universities[0]),
            ('buyer_2', 'Synthetic Buyer Two', 'STUDENT', universities[1]),
            ('admin', 'Synthetic Admin', 'ADMIN', universities[0]),
        )
        users = {}
        for key, name, role, university in user_defaults:
            users[key] = self._once(User, {'email': f'{PREFIX}{key}@example.invalid'}, {
                'full_name': name,
                'password_hash': make_password(FIXTURE_PASSWORD),
                'phone': f'+1555000{len(users) + 1:04d}',
                'role': role,
                'status': 'ACTIVE',
                'university': university,
                'created_at': now,
                'updated_at': now,
            })
            User.objects.filter(pk=users[key].pk).update(
                password_hash=make_password(FIXTURE_PASSWORD),
            )
        performance_users = []
        for index in range(45):
            user = self._once(User, {
                'email': f'{PREFIX}perf-user-{index + 1:03d}@example.invalid',
            }, {
                'full_name': f'Acceptance Performance User {index + 1}',
                'password_hash': make_password(FIXTURE_PASSWORD),
                'phone': f'+1555010{index + 1:04d}',
                'role': 'STUDENT',
                'status': 'ACTIVE',
                'university': universities[index % len(universities)],
                'created_at': now,
                'updated_at': now,
            })
            User.objects.filter(pk=user.pk).update(
                password_hash=make_password(FIXTURE_PASSWORD),
            )
            performance_users.append(user)

        subjects = [
            self._once(Subject, {'code': PREFIX + f'subject-{i}'}, {
                'name': f'Acceptance Subject {i}',
                'description': 'Synthetic acceptance fixture',
                'credits': 3,
                'status': 'ACTIVE',
                'created_at': now,
                'updated_at': now,
            })
            for i in range(1, 6)
        ]
        language = self._once(Language, {'code': 'acc-fixture-en'}, {
            'name': 'Acceptance English',
            'status': 'ACTIVE',
            'created_at': now,
        })
        category = self._once(Category, {'slug': PREFIX + 'books'}, {
            'name': 'Acceptance Books',
            'description': 'Synthetic category',
            'status': 'ACTIVE',
            'created_at': now,
            'updated_at': now,
        })

        books = []
        listings = []
        works = []
        for index in range(book_count):
            seller = users['seller_1'] if index < 5 else users['seller_2']
            title = (
                f'{PREFIX}book-{index + 1:02d}'
                if index < 10
                else f'{PREFIX}book-{index + 1:04d}'
            )
            work = self._once(BookWork, {'title': title}, {
                'description': 'Synthetic fixture description',
                'author_name': 'Acceptance Author',
                'category': category,
                'created_by': seller,
                'status': 'ACTIVE',
                'created_at': now,
                'updated_at': now,
            })
            works.append(work)
            BookWorkSubject.objects.get_or_create(
                book_work_id=work.id,
                subject_id=subjects[index % len(subjects)].id,
                defaults={'is_primary': True, 'created_at': now},
            )
            edition = self._once(BookEdition, {'book_work': work}, {
                'edition_name': 'Acceptance Edition',
                'edition_number': 1,
                'publisher_name': 'Synthetic Publisher',
                'publication_year': 2024,
                'page_count': 120,
                'format': 'PAPERBACK',
                'language': language,
                'description': 'Synthetic edition',
                'created_at': now,
                'updated_at': now,
            })
            BookIdentifier.objects.get_or_create(
                identifier_type='ACCEPTANCE',
                identifier_value=f'{PREFIX}identifier-{index + 1:02d}',
                defaults={
                    'book_edition': edition,
                    'created_at': now,
                },
            )
            book_status = (
                'RESERVED' if index in (0, 5, 2)
                else 'SOLD' if index == 8
                else 'AVAILABLE'
            )
            book = self._once(Book, {'book_edition': edition}, {
                'owner': seller,
                'condition_label': 'good',
                'condition_description': 'Synthetic condition',
                'acquisition_type': 'PURCHASED',
                'status': book_status,
                'created_at': now,
                'updated_at': now,
            })
            books.append(book)
            BookImage.objects.get_or_create(
                book=book,
                is_primary=True,
                defaults={
                    'image_url': f'https://example.invalid/{PREFIX}book-{index + 1}.jpg',
                    'cloudinary_public_id': None,
                    'sort_order': 0,
                    'created_at': now,
                },
            )
            listing_status = (
                'RESERVED' if index in (0, 5, 2)
                else 'SOLD' if index == 8
                else 'EXPIRED' if index == 9
                else 'PENDING' if index == 10
                else 'REJECTED' if index == 11
                else 'ACTIVE'
            )
            expires_at = old if index == 9 else None
            published_at = (
                old - timedelta(days=3)
                if index == 9
                else now
                if listing_status in ('ACTIVE', 'RESERVED', 'SOLD')
                else None
            )
            listing = self._once(SaleListing, {'book': book}, {
                'seller': seller,
                'title': title,
                'description': 'Synthetic listing description',
                'price': Decimal(100000 + index * 10000),
                'currency': 'VND',
                'status': listing_status,
                'published_at': published_at,
                'expires_at': expires_at,
                'created_at': old if index == 9 else now,
                'updated_at': now,
            })
            if (listing.status, listing.published_at, listing.expires_at) != (
                listing_status,
                published_at,
                expires_at,
            ):
                listing.status = listing_status
                listing.published_at = published_at
                listing.expires_at = expires_at
                listing.updated_at = now
                listing.save(update_fields=[
                    'status',
                    'published_at',
                    'expires_at',
                    'updated_at',
                ])
            listings.append(listing)

        addresses = []
        address_users = (users['buyer_1'], users['buyer_1'], users['buyer_2'])
        for index, user in enumerate(address_users, 1):
            addresses.append(self._once(UserAddress, {
                'user': user,
                'address_line': f'{PREFIX}address-{index}',
            }, {
                'recipient_name': user.full_name,
                'phone': user.phone,
                'ward': 'Synthetic Ward',
                'district': 'Synthetic District',
                'city': 'Synthetic City',
                'postal_code': '00000',
                'is_default': index in (1, 3),
                'created_at': now,
                'updated_at': now,
            }))

        for user, book_index in (
            (users['buyer_1'], 1),
            (users['buyer_1'], 3),
            (users['buyer_2'], 6),
        ):
            Favorite.objects.get_or_create(
                user=user,
                book=books[book_index],
                defaults={'sale_listing': listings[book_index], 'created_at': now},
            )
        for index, user in enumerate(performance_users):
            book_index = (10 + index) % len(books)
            Favorite.objects.get_or_create(
                user=user,
                book=books[book_index],
                defaults={
                    'sale_listing': listings[book_index],
                    'created_at': now,
                },
            )

        conversations = []
        for index, (buyer, seller) in enumerate((
            (users['buyer_1'], users['seller_1']),
            (users['buyer_2'], users['seller_2']),
        ), 1):
            conversation = None
            for candidate in Conversation.objects.filter(
                conversation_type='SALE',
            ).order_by('id'):
                member_ids = set(ConversationMember.objects.filter(
                    conversation_id=candidate.id,
                ).values_list('user_id', flat=True))
                if {buyer.id, seller.id} <= member_ids:
                    conversation = candidate
                    break
            if conversation is None:
                conversation = Conversation.objects.create(
                    conversation_type='SALE',
                    created_at=now,
                    updated_at=now,
                )
                ConversationMember.objects.bulk_create([
                    ConversationMember(
                        conversation=conversation,
                        user=buyer,
                        joined_at=now,
                        last_read_at=now,
                    ),
                    ConversationMember(
                        conversation=conversation,
                        user=seller,
                        joined_at=now + timedelta(microseconds=1),
                        last_read_at=None,
                    ),
                ])
            conversations.append(conversation)
            for message_index in range(5):
                sender = buyer if message_index % 2 == 0 else seller
                Message.objects.get_or_create(
                    conversation=conversation,
                    sender=sender,
                    content=f'{PREFIX}conversation-{index}-message-{message_index + 1}',
                    defaults={
                        'message_type': 'TEXT',
                        'sent_at': now + timedelta(seconds=message_index),
                    },
                )
        for message_index in range(100):
            sender = users['buyer_1'] if message_index % 2 == 0 else users['seller_1']
            Message.objects.get_or_create(
                conversation=conversations[0],
                sender=sender,
                content=f'{PREFIX}perf-message-{message_index + 1:03d}',
                defaults={
                    'message_type': 'TEXT',
                    'sent_at': now + timedelta(seconds=message_index + 10),
                },
            )

        reservations = []
        for index, (book_index, requester, reservation_status, expiry) in enumerate((
            (1, users['buyer_1'], 'PENDING', later),
            (2, users['buyer_2'], 'CONFIRMED', later),
            (4, users['buyer_1'], 'EXPIRED', old),
        ), 1):
            reservation = self._once(BookReservation, {
                'book': books[book_index],
                'requester': requester,
            }, {
                'owner_id': books[book_index].owner_id,
                'status': reservation_status,
                'created_at': (
                    old - timedelta(days=3)
                    if reservation_status == 'EXPIRED' else now
                ),
                'expires_at': expiry,
                'updated_at': now,
            })
            reservations.append(reservation)

        lend_listing = self._once(LendListing, {'book': books[7]}, {
            'lender': books[7].owner,
            'title': f'{PREFIX}lend-1',
            'description': 'Synthetic lending listing',
            'status': 'ACTIVE',
            'deposit_amount': Decimal('50000'),
            'rental_fee': Decimal('10000'),
            'currency': 'VND',
            'published_at': now,
            'expires_at': None,
            'created_at': now,
            'updated_at': now,
        })
        BorrowTerms.objects.get_or_create(
            lend_listing=lend_listing,
            defaults={
                'max_days': 14,
                'late_fee_per_day': Decimal('1000'),
                'deposit_required': True,
                'shipping_paid_by': 'BORROWER',
                'return_method': 'IN_PERSON',
                'notes': 'Synthetic terms',
                'created_at': now,
                'updated_at': now,
            },
        )
        violation = self._once(UserViolation, {
            'user': users['buyer_1'],
            'reason': PREFIX + 'synthetic-violation',
        }, {
            'violation_type': 'ACCEPTANCE_FIXTURE',
            'description': 'Synthetic acceptance fixture',
            'severity': 'LOW',
            'status': 'OPEN',
            'expires_at': None,
            'created_by': users['admin'],
            'created_at': now,
            'resolved_at': None,
        })

        carts = []
        for user in (users['buyer_1'], users['buyer_2']):
            carts.append(self._once(Cart, {'user': user, 'status': 'ACTIVE'}, {
                'created_at': now,
                'updated_at': now,
            }))
        for cart, listing in (
            (carts[0], listings[3]),
            (carts[0], listings[6]),
            (carts[1], listings[7]),
        ):
            CartItem.objects.get_or_create(
                cart=cart,
                sale_listing=listing,
                defaults={
                    'unit_price': listing.price,
                    'currency': 'VND',
                    'created_at': now,
                    'updated_at': now,
                },
            )

        checkout_groups = []
        for index, (cart, buyer) in enumerate(zip(carts, (
            users['buyer_1'], users['buyer_2'],
        )), 1):
            checkout_groups.append(self._once(CheckoutGroup, {
                'buyer': buyer,
                'idempotency_key': f'{PREFIX}checkout-{index}',
            }, {
                'checkout_code': f'CHK-{PREFIX}{index}',
                'cart': cart,
                'status': 'PENDING_PAYMENT',
                'currency': 'VND',
                'subtotal': Decimal('100000'),
                'shipping_total': Decimal('0'),
                'discount_total': Decimal('0'),
                'total_amount': Decimal('100000'),
                'shipping_address_snapshot': {'synthetic': True},
                'pricing_snapshot': {'subtotal': '100000', 'currency': 'VND'},
                'created_at': now,
                'updated_at': now,
            }))

        order_specs = (
            (0, 'seller_1', 0, 'PENDING_PAYMENT'),
            (0, 'seller_2', 5, 'PENDING_PAYMENT'),
            (1, 'seller_2', 8, 'COMPLETED'),
        )
        orders = []
        for index, (group_index, seller_key, listing_index, order_status) in enumerate(order_specs, 1):
            group = checkout_groups[group_index]
            order = self._once(Order, {'order_code': f'ORD-{PREFIX}{index}'}, {
                'checkout_group': group,
                'buyer': group.buyer,
                'seller': users[seller_key],
                'order_type': 'SALE',
                'status': order_status,
                'currency': 'VND',
                'subtotal': listings[listing_index].price,
                'shipping_fee': Decimal('0'),
                'discount_amount': Decimal('0'),
                'total_amount': listings[listing_index].price,
                'shipping_address_snapshot': {'synthetic': True},
                'pricing_snapshot': {
                    'subtotal': str(listings[listing_index].price),
                    'currency': 'VND',
                },
                'placed_at': now,
                'created_at': now,
                'updated_at': now,
                'completed_at': now if order_status == 'COMPLETED' else None,
            })
            orders.append(order)
            item = self._once(SaleOrderItem, {
                'order': order,
                'sale_listing': listings[listing_index],
            }, {
                'book': books[listing_index],
                'seller': users[seller_key],
                'title_snapshot': listings[listing_index].title,
                'condition_snapshot': books[listing_index].condition_label,
                'unit_price': listings[listing_index].price,
                'discount_allocated': Decimal('0'),
                'quantity': 1,
                'subtotal': listings[listing_index].price,
                'created_at': now,
            })
            if index <= 2:
                Payment.objects.get_or_create(
                    provider=PREFIX + 'no-provider',
                    idempotency_key=f'{PREFIX}payment-{index}',
                    defaults={
                        'checkout_group': group,
                        'order': order,
                        'payer': group.buyer,
                        'payment_method': 'UNCONFIGURED',
                        'payment_purpose': 'CHECKOUT',
                        'amount': listings[listing_index].price,
                        'platform_fee_rate': Decimal('0'),
                        'platform_fee': Decimal('0'),
                        'seller_amount': listings[listing_index].price,
                        'currency': 'VND',
                        'status': 'PENDING',
                        'created_at': now,
                        'updated_at': now,
                    },
                )
            if index == 3:
                Return.objects.get_or_create(
                    order=order,
                    sale_order_item=item,
                    status='REQUESTED',
                    defaults={
                        'reason': 'SYNTHETIC_TEST',
                        'description': 'Synthetic completed-order return fixture',
                        'requested_by': group.buyer,
                        'requested_at': now,
                    },
                )
                Return.objects.get_or_create(
                    order=order,
                    sale_order_item=item,
                    status='REJECTED',
                    defaults={
                        'reason': 'SYNTHETIC_TEST_REJECTED',
                        'description': 'Synthetic rejected return fixture',
                        'requested_by': group.buyer,
                        'requested_at': now,
                    },
                )
            if index <= 2:
                shipment = Shipment.objects.get_or_create(
                    order=order,
                    tracking_code=f'{PREFIX}tracking-{index}',
                    defaults={
                        'carrier': 'SYNTHETIC',
                        'shipping_fee': Decimal('0'),
                        'status': 'PENDING',
                        'currency': 'VND',
                        'created_at': now,
                        'updated_at': now,
                    },
                )[0]
                ShipmentTracking.objects.get_or_create(
                    shipment=shipment,
                    status='PENDING',
                    defaults={
                        'location': 'Synthetic location',
                        'description': 'Synthetic tracking fixture',
                        'created_at': now,
                    },
                )

        borrow_order = self._once(Order, {
            'order_code': f'BOR-{PREFIX}borrow-1',
        }, {
            'checkout_group': checkout_groups[1],
            'buyer': users['buyer_2'],
            'seller': lend_listing.lender,
            'order_type': 'BORROW',
            'status': 'PENDING_PAYMENT',
            'currency': 'VND',
            'subtotal': lend_listing.rental_fee + (lend_listing.deposit_amount or Decimal('0')),
            'shipping_fee': Decimal('0'),
            'discount_amount': Decimal('0'),
            'total_amount': lend_listing.rental_fee + (lend_listing.deposit_amount or Decimal('0')),
            'shipping_address_snapshot': {'synthetic': True},
            'pricing_snapshot': {
                'rental_fee': str(lend_listing.rental_fee),
                'deposit': str(lend_listing.deposit_amount or Decimal('0')),
                'currency': 'VND',
            },
            'placed_at': now,
            'created_at': now,
            'updated_at': now,
            'completed_at': None,
        })
        self._once(BorrowOrder, {'order': borrow_order}, {
            'checkout_group': checkout_groups[1],
            'lend_listing': lend_listing,
            'lender': lend_listing.lender,
            'borrower': users['buyer_2'],
            'status': 'PENDING',
            'borrow_terms_snapshot': {
                'max_days': 14,
                'deposit_required': True,
                'return_method': 'IN_PERSON',
            },
            'expected_start_at': later,
            'expected_return_at': later + timedelta(days=7),
            'actual_start_at': None,
            'actual_return_at': None,
            'rental_fee': lend_listing.rental_fee,
            'deposit_amount': lend_listing.deposit_amount or Decimal('0'),
            'deposit_refunded_amount': Decimal('0'),
            'deposit_forfeited_amount': Decimal('0'),
            'late_fee_amount': Decimal('0'),
            'return_requested_by': None,
            'return_status': None,
            'return_method': None,
            'return_tracking_code': None,
            'return_requested_at': None,
            'return_approved_at': None,
            'return_notes': None,
            'currency': 'VND',
            'created_at': now,
            'updated_at': now,
        })
        for index in range(20):
            order_code = f'ORD-{PREFIX}perf-{index + 1:03d}'
            performance_checkout = self._once(CheckoutGroup, {
                'buyer': users['buyer_2'],
                'idempotency_key': f'{PREFIX}perf-checkout-{index + 1:03d}',
            }, {
                'checkout_code': f'CHK-{PREFIX}perf-{index + 1:03d}',
                'cart': carts[1],
                'status': 'PENDING_PAYMENT',
                'currency': 'VND',
                'subtotal': Decimal(10000 + index),
                'shipping_total': Decimal('0'),
                'discount_total': Decimal('0'),
                'total_amount': Decimal(10000 + index),
                'shipping_address_snapshot': {'synthetic': True},
                'pricing_snapshot': {'currency': 'VND'},
                'created_at': now,
                'updated_at': now,
            })
            Order.objects.get_or_create(
                order_code=order_code,
                defaults={
                    'checkout_group': performance_checkout,
                    'buyer': users['buyer_2'],
                    'seller': users['seller_1'],
                    'order_type': 'SALE',
                    'status': 'PENDING_PAYMENT',
                    'currency': 'VND',
                    'subtotal': Decimal(10000 + index),
                    'shipping_fee': Decimal('0'),
                    'discount_amount': Decimal('0'),
                    'total_amount': Decimal(10000 + index),
                    'shipping_address_snapshot': {'synthetic': True},
                    'pricing_snapshot': {'currency': 'VND'},
                    'placed_at': now,
                    'created_at': now,
                    'updated_at': now,
                    'completed_at': None,
                },
            )

        review_specs = (
            (orders[2], users['buyer_2'], listings[8], 5),
            (orders[2], users['seller_2'], listings[8], 4),
        )
        for order, reviewer, listing, rating in review_specs:
            Review.objects.get_or_create(
                order=order,
                reviewer=reviewer,
                defaults={
                    'sale_listing': listing,
                    'rating': rating,
                    'comment': 'Synthetic acceptance review',
                    'created_at': now,
                    'updated_at': now,
                },
            )

        refund_payment = Payment.objects.filter(
            provider=PREFIX + 'no-provider',
            idempotency_key=PREFIX + 'payment-1',
        ).first()
        if refund_payment:
            for suffix in ('rejected-1', 'rejected-2'):
                Refund.objects.get_or_create(
                    provider=refund_payment.provider,
                    idempotency_key=f'{PREFIX}refund-{suffix}',
                    defaults={
                        'order': refund_payment.order,
                        'payment': refund_payment,
                        'sale_order_item': refund_payment.order.sale_items.first(),
                        'requested_by': refund_payment.payer,
                        'reason': 'SYNTHETIC_TEST',
                        'amount': Decimal('1'),
                        'currency': 'VND',
                        'status': 'REJECTED',
                        'requested_at': now,
                        'created_at': now,
                        'updated_at': now,
                    },
                )

        request_item = self._once(BookRequest, {
            'user': users['buyer_1'],
            'request_type': 'BUY',
            'title_keyword': PREFIX + 'book',
        }, {
            'book_work': works[3],
            'category': category,
            'description': 'Synthetic buy request',
            'budget_max': Decimal('500000'),
            'asking_price': None,
            'currency': 'VND',
            'condition_preference': 'good',
            'status': 'OPEN',
            'expires_at': later,
            'created_at': now,
            'updated_at': now,
        })
        RequestInterest.objects.get_or_create(
            request=request_item,
            user=users['buyer_2'],
            defaults={
                'note': 'Synthetic interest',
                'status': 'ACTIVE',
                'created_at': now,
            },
        )
        RequestMatch.objects.get_or_create(
            request=request_item,
            sale_listing=listings[4],
            lend_listing=None,
            defaults={
                'match_type': 'SALE',
                'score': Decimal('0.90000'),
                'status': 'SUGGESTED',
                'created_at': now,
            },
        )

        for index, (user, reservation) in enumerate((
            (users['buyer_1'], reservations[0]),
            (users['seller_1'], reservations[1]),
            (users['buyer_2'], reservations[2]),
        ), 1):
            Notification.objects.get_or_create(
                user=user,
                notification_type='ACCEPTANCE_FIXTURE',
                title=f'{PREFIX}notification-{index}',
                defaults={
                    'content': 'Synthetic notification',
                    'entity_type': 'BOOK_RESERVATION',
                    'entity_id': reservation.id,
                    'is_read': index == 3,
                    'created_at': now,
                },
            )

        report_specs = (
            (users['buyer_1'], users['seller_1'], listings[0], 'OPEN'),
            (users['buyer_2'], users['seller_2'], listings[5], 'IN_REVIEW'),
            (users['seller_1'], users['buyer_1'], listings[8], 'RESOLVED'),
        )
        for reporter, reported, listing, report_status in report_specs:
            Report.objects.get_or_create(
                reporter=reporter,
                sale_listing=listing,
                reason='SYNTHETIC_TEST',
                defaults={
                    'reported_user': reported,
                    'description': 'Synthetic report fixture',
                    'status': report_status,
                    'handled_by': users['admin'] if report_status != 'OPEN' else None,
                    'resolution_note': 'Synthetic fixture' if report_status == 'RESOLVED' else None,
                    'created_at': now,
                    'resolved_at': now if report_status == 'RESOLVED' else None,
                },
            )

        for index, (purpose, status_value, expires_at) in enumerate((
            ('REGISTER', 'PENDING', later),
            ('LOGIN', 'VERIFIED', later),
            ('FORGOT_PASSWORD', 'EXPIRED', old),
        ), 1):
            OtpVerification.objects.get_or_create(
                target=f'{PREFIX}otp-{index}@example.invalid',
                purpose=purpose,
                defaults={
                    'user': users['buyer_1'],
                    'channel': 'EMAIL',
                    'otp_hash': make_password(f'{secrets.randbelow(1000000):06d}'),
                    'expires_at': expires_at,
                    'verified_at': now if status_value == 'VERIFIED' else None,
                    'attempt_count': 1 if index == 3 else 0,
                    'resend_count': 0,
                    'status': status_value,
                    'created_at': old if status_value == 'EXPIRED' else now,
                    'updated_at': now,
                },
            )

        table_counts = {
            'universities': University.objects.filter(code__startswith=PREFIX).count(),
            'faculties': Faculty.objects.filter(code__startswith=PREFIX).count(),
            'majors': Major.objects.filter(code__startswith=PREFIX).count(),
            'users': User.objects.filter(email__startswith=PREFIX).count(),
            'otp_verifications': OtpVerification.objects.filter(target__startswith=PREFIX).count(),
            'user_addresses': UserAddress.objects.filter(address_line__startswith=PREFIX).count(),
            'user_violations': UserViolation.objects.filter(user__email__startswith=PREFIX).count(),
            'subjects': Subject.objects.filter(code__startswith=PREFIX).count(),
            'languages': Language.objects.filter(code='acc-fixture-en').count(),
            'categories': Category.objects.filter(slug__startswith=PREFIX).count(),
            'book_works': BookWork.objects.filter(title__startswith=PREFIX).count(),
            'book_work_subjects': BookWorkSubject.objects.filter(book_work__title__startswith=PREFIX).count(),
            'book_editions': BookEdition.objects.filter(book_work__title__startswith=PREFIX).count(),
            'book_identifiers': BookIdentifier.objects.filter(identifier_value__startswith=PREFIX).count(),
            'books': Book.objects.filter(book_edition__book_work__title__startswith=PREFIX).count(),
            'book_images': BookImage.objects.filter(book__book_edition__book_work__title__startswith=PREFIX).count(),
            'sale_listings': SaleListing.objects.filter(title__startswith=PREFIX).count(),
            'lend_listings': LendListing.objects.filter(title__startswith=PREFIX).count(),
            'borrow_terms': BorrowTerms.objects.filter(lend_listing__title__startswith=PREFIX).count(),
            'book_requests': BookRequest.objects.filter(title_keyword__startswith=PREFIX).count(),
            'request_interests': RequestInterest.objects.filter(request__title_keyword__startswith=PREFIX).count(),
            'request_matches': RequestMatch.objects.filter(request__title_keyword__startswith=PREFIX).count(),
            'carts': Cart.objects.filter(user__email__startswith=PREFIX).count(),
            'cart_items': CartItem.objects.filter(cart__user__email__startswith=PREFIX).count(),
            'checkout_groups': CheckoutGroup.objects.filter(idempotency_key__startswith=PREFIX).count(),
            'orders': Order.objects.filter(order_code__startswith=('ORD-' + PREFIX)).count()
            + Order.objects.filter(order_code__startswith=('BOR-' + PREFIX)).count(),
            'sale_order_items': SaleOrderItem.objects.filter(order__order_code__startswith='ORD-' + PREFIX).count(),
            'borrow_orders': BorrowOrder.objects.filter(order__order_code__startswith='BOR-' + PREFIX).count(),
            'payments': Payment.objects.filter(provider=PREFIX + 'no-provider').count(),
            'shipments': Shipment.objects.filter(tracking_code__startswith=PREFIX).count(),
            'shipment_tracking': ShipmentTracking.objects.filter(description='Synthetic tracking fixture').count(),
            'returns': Return.objects.filter(requested_by__email__startswith=PREFIX).count(),
            'refunds': Refund.objects.filter(provider=PREFIX + 'no-provider').count(),
            'favorites': Favorite.objects.filter(user__email__startswith=PREFIX).count(),
            'conversations': Conversation.objects.filter(members__user__email__startswith=PREFIX).distinct().count(),
            'conversation_members': ConversationMember.objects.filter(user__email__startswith=PREFIX).count(),
            'messages': Message.objects.filter(content__startswith=PREFIX).count(),
            'notifications': Notification.objects.filter(title__startswith=PREFIX).count(),
            'reviews': Review.objects.filter(comment='Synthetic acceptance review').count(),
            'reports': Report.objects.filter(reason='SYNTHETIC_TEST').count(),
            'book_reservations': BookReservation.objects.filter(requester__email__startswith=PREFIX).count(),
        }
        empty_tables = [table for table, count in table_counts.items() if count == 0]
        if len(table_counts) != 41 or empty_tables:
            raise CommandError(
                'Acceptance seed did not populate all 41 Lite tables: '
                + ', '.join(empty_tables or table_counts.keys()),
            )

        return {
            'tables_covered': f'{len(table_counts)}/41',
            'fixture_rows': sum(table_counts.values()),
            'universities': table_counts['universities'],
            'faculties': table_counts['faculties'],
            'majors': table_counts['majors'],
            'users': table_counts['users'],
            'subjects': table_counts['subjects'],
            'books': table_counts['books'],
            'sale_listings': table_counts['sale_listings'],
            'book_images': table_counts['book_images'],
            'addresses': len(addresses),
            'favorites': Favorite.objects.filter(user__email__startswith=PREFIX).count(),
            'conversations': len(conversations),
            'messages': Message.objects.filter(content__startswith=PREFIX).count(),
            'reservations': len(reservations),
            'carts': len(carts),
            'cart_items': CartItem.objects.filter(cart__user__email__startswith=PREFIX).count(),
            'orders': table_counts['orders'],
            'payments': Payment.objects.filter(provider=PREFIX + 'no-provider').count(),
            'shipments': Shipment.objects.filter(tracking_code__startswith=PREFIX).count(),
            'tracking': ShipmentTracking.objects.filter(
                description='Synthetic tracking fixture',
            ).count(),
            'returns': Return.objects.filter(reason__startswith='SYNTHETIC_TEST').count(),
            'refunds': Refund.objects.filter(provider=PREFIX + 'no-provider').count(),
            'reviews': Review.objects.filter(comment='Synthetic acceptance review').count(),
            'reports': Report.objects.filter(reason='SYNTHETIC_TEST').count(),
            'otp': OtpVerification.objects.filter(target__startswith=PREFIX).count(),
            'requests': BookRequest.objects.filter(title_keyword=PREFIX + 'book').count(),
            'request_interests': RequestInterest.objects.filter(
                request__title_keyword=PREFIX + 'book',
            ).count(),
            'notifications': Notification.objects.filter(title__startswith=PREFIX).count(),
            'lend_listings': LendListing.objects.filter(title=PREFIX + 'lend-1').count(),
            'borrow_terms': BorrowTerms.objects.filter(lend_listing=lend_listing).count(),
            'borrow_orders': table_counts['borrow_orders'],
            'request_matches': table_counts['request_matches'],
            'book_identifiers': table_counts['book_identifiers'],
            'user_violations': table_counts['user_violations'],
            'performance_users': User.objects.filter(email__startswith=PREFIX + 'perf-user-').count(),
            'performance_favorites': Favorite.objects.filter(
                user__email__startswith=PREFIX + 'perf-user-',
            ).count(),
            'performance_messages': Message.objects.filter(
                content__startswith=PREFIX + 'perf-message-',
            ).count(),
        }
