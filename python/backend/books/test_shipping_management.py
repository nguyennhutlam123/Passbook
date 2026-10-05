from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from .admin_dashboard_views import (
    AdminShipmentDetailView,
    AdminShipmentListView,
    AdminShipmentStatusView,
)
from .commerce_api_views import ShipmentTrackingCreateView
from .shipment_services import (
    SHIPMENT_TRANSITIONS,
    create_pending_shipment,
    update_shipment_status,
    validate_shipment_transition,
)
from .services import calculate_borrow_late_fee, mark_overdue_borrow_orders


class ShipmentStateMachineTests(SimpleTestCase):
    def test_create_pending_shipment_records_initial_system_event(self):
        now = Mock(name='now')
        order = SimpleNamespace(id=9, currency='VND')
        shipment = SimpleNamespace(id=5)
        shipment_manager = Mock()
        shipment_manager.create.return_value = shipment
        tracking_manager = Mock()
        actor = SimpleNamespace(id=76)

        with patch(
            'books.shipment_services.Shipment.objects',
            shipment_manager,
        ), patch(
            'books.shipment_services.ShipmentTracking.objects',
            tracking_manager,
        ):
            result = create_pending_shipment(
                order,
                changed_by=actor,
                carrier='Acceptance carrier',
                tracking_code='ACCEPT-5',
                location='Local test',
                created_at=now,
            )

        self.assertIs(result, shipment)
        self.assertEqual(
            shipment_manager.create.call_args.kwargs,
            {
                'order': order,
                'carrier': 'Acceptance carrier',
                'tracking_code': 'ACCEPT-5',
                'shipping_fee': Decimal('0'),
                'status': 'PENDING',
                'shipped_at': None,
                'currency': 'VND',
                'created_at': now,
                'updated_at': now,
            },
        )
        tracking_manager.create.assert_called_once_with(
            shipment=shipment,
            status='PENDING',
            source='SYSTEM',
            changed_by_id=76,
            location='Local test',
            description='Đã tạo thông tin vận chuyển; chờ PassBook tiếp nhận xử lý.',
            occurred_at=now,
            created_at=now,
        )

    def test_standard_shipment_transitions_follow_forward_order(self):
        for old_status, new_status in (
            ('PENDING', 'PICKED_UP'),
            ('PICKED_UP', 'IN_TRANSIT'),
            ('IN_TRANSIT', 'OUT_FOR_DELIVERY'),
            ('OUT_FOR_DELIVERY', 'DELIVERED'),
        ):
            with self.subTest(old_status=old_status, new_status=new_status):
                validate_shipment_transition(old_status, new_status)

    def test_invalid_and_duplicate_transitions_are_rejected(self):
        for old_status, new_status in (
            ('PENDING', 'DELIVERED'),
            ('DELIVERED', 'IN_TRANSIT'),
            ('COMPLETED', 'IN_TRANSIT'),
            ('PICKED_UP', 'PICKED_UP'),
        ):
            with self.subTest(old_status=old_status, new_status=new_status):
                with self.assertRaises(ValidationError):
                    validate_shipment_transition(old_status, new_status)

    def test_status_update_records_admin_provenance_and_updates_only_shipment(self):
        shipment = SimpleNamespace(
            id=3,
            status='PENDING',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event = SimpleNamespace(id=17, status='PICKED_UP')
        event_model = Mock()
        event_model.objects.create.return_value = event
        actor = SimpleNamespace(id=76)

        with patch(
            'books.shipment_services.timezone.now',
            return_value=Mock(name='now'),
        ):
            created, old_status = update_shipment_status.__wrapped__(
                shipment,
                status='PICKED_UP',
                source='ADMIN',
                changed_by=actor,
                description='Parcel collected',
                event_model=event_model,
            )

        self.assertEqual(old_status, 'PENDING')
        self.assertIs(created, event)
        event_model.objects.create.assert_called_once()
        self.assertEqual(
            event_model.objects.create.call_args.kwargs['source'],
            'ADMIN',
        )
        self.assertEqual(
            event_model.objects.create.call_args.kwargs['changed_by_id'],
            76,
        )
        self.assertEqual(
            event_model.objects.create.call_args.kwargs['description'],
            'Parcel collected',
        )
        shipment.save.assert_called_once()
        self.assertEqual(shipment.status, 'PICKED_UP')

    def test_domain_status_update_accepts_non_admin_sources(self):
        shipment = SimpleNamespace(
            id=4,
            status='PENDING',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event_model = Mock()
        update_shipment_status.__wrapped__(
            shipment,
            status='PICKED_UP',
            source='CARRIER_API',
            event_model=event_model,
        )
        self.assertEqual(
            event_model.objects.create.call_args.kwargs['source'],
            'CARRIER_API',
        )

    def test_sale_delivery_completes_order_in_same_domain_transition(self):
        order = SimpleNamespace(
            id=9,
            order_type='SALE',
            status='CONFIRMED',
            completed_at=None,
            updated_at=None,
            save=Mock(),
        )
        shipment = SimpleNamespace(
            id=5,
            order_id=order.id,
            order=order,
            status='OUT_FOR_DELIVERY',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event_model = Mock()
        event_model.objects.create.return_value = SimpleNamespace(id=81)
        borrow = SimpleNamespace(return_tracking_code=None)
        shipment_manager = Mock()
        shipment_manager.filter.return_value.exclude.return_value.exists.return_value = False
        payment_manager = Mock()
        payment_manager.select_for_update.return_value.filter.return_value = []

        with patch(
            'books.shipment_services.notify_order_status_changed',
        ) as notify, patch(
            'books.shipment_services.Shipment.objects',
            shipment_manager,
        ), patch(
            'books.shipment_services.Payment.objects',
            payment_manager,
        ):
            event, old_status = update_shipment_status.__wrapped__(
                shipment,
                status='DELIVERED',
                source='ADMIN',
                changed_by=SimpleNamespace(id=76),
                borrow=borrow,
                event_model=event_model,
            )

        self.assertEqual(old_status, 'OUT_FOR_DELIVERY')
        self.assertEqual(event.id, 81)
        self.assertEqual(shipment.status, 'DELIVERED')
        self.assertEqual(order.status, 'COMPLETED')
        self.assertIsNotNone(order.completed_at)
        shipment.save.assert_called_once()
        order.save.assert_called_once_with(
            update_fields=['status', 'completed_at', 'updated_at'],
        )
        notify.assert_called_once_with(order, 'CONFIRMED')

    def test_admin_borrow_delivery_activates_ticket_and_collects_cod(self):
        now = timezone.now()
        payment = SimpleNamespace(
            payment_method='COD',
            status='PENDING',
            paid_at=None,
            updated_at=None,
            save=Mock(),
        )
        payment_manager = Mock()
        payment_manager.select_for_update.return_value.filter.return_value = [payment]
        book = SimpleNamespace(status='RESERVED', updated_at=None, save=Mock())
        listing = SimpleNamespace(
            status='RESERVED',
            updated_at=None,
            book=book,
            save=Mock(),
        )
        borrow = SimpleNamespace(
            id=14,
            status='PENDING',
            borrower_id=12,
            lender_id=13,
            actual_start_at=None,
            expected_start_at=now - timedelta(days=3),
            expected_return_at=now + timedelta(days=3),
            updated_at=None,
            return_tracking_code=None,
            lend_listing=listing,
            save=Mock(),
        )
        order = SimpleNamespace(
            id=9,
            order_type='BORROW',
            status='CONFIRMED',
            updated_at=None,
            save=Mock(),
        )
        shipment = SimpleNamespace(
            id=5,
            order_id=order.id,
            order=order,
            status='OUT_FOR_DELIVERY',
            shipped_at=now - timedelta(hours=1),
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event_model = Mock()
        event_model.objects.create.return_value = SimpleNamespace(id=83)

        with patch(
            'books.shipment_services.timezone.now',
            return_value=now,
        ), patch(
            'books.shipment_services.Payment.objects',
            payment_manager,
        ), patch(
            'books.shipment_services.notify_order_status_changed',
        ), patch(
            'books.shipment_services.notify_borrow_order_parties',
        ) as notify_borrow:
            event, old_status = update_shipment_status.__wrapped__(
                shipment,
                status='DELIVERED',
                source='ADMIN',
                borrow=borrow,
                event_model=event_model,
            )

        self.assertEqual(old_status, 'OUT_FOR_DELIVERY')
        self.assertEqual(event.id, 83)
        self.assertEqual(borrow.status, 'ACTIVE')
        self.assertIs(borrow.actual_start_at, now)
        self.assertEqual(listing.status, 'ON_LOAN')
        self.assertEqual(book.status, 'ON_LOAN')
        self.assertEqual(order.status, 'PROCESSING')
        self.assertEqual(payment.status, 'PAID')
        borrow.save.assert_called_once_with(
            update_fields=[
                'status',
                'actual_start_at',
                'expected_return_at',
                'updated_at',
            ],
        )
        listing.save.assert_called_once_with(update_fields=['status', 'updated_at'])
        book.save.assert_called_once_with(update_fields=['status', 'updated_at'])
        order.save.assert_called_once_with(update_fields=['status', 'updated_at'])
        payment.save.assert_called_once_with(
            update_fields=['status', 'paid_at', 'updated_at'],
        )
        notify_borrow.assert_called_once_with(
            borrow,
            title='Sách đã giao · Phiếu mượn đang hoạt động',
            content=(
                f'Admin đã xác nhận giao sách và thu COD cho phiếu #{borrow.id}. '
                'Phiếu mượn đã bắt đầu; bạn có thể xem thời hạn trả trong chi tiết phiếu.'
            ),
        )

    def test_admin_return_delivery_completes_borrow_and_charges_full_late_days(self):
        now = timezone.now()
        book = SimpleNamespace(status='ON_LOAN', updated_at=None, save=Mock())
        listing = SimpleNamespace(
            status='ON_LOAN',
            expires_at=None,
            updated_at=None,
            book=book,
            save=Mock(),
        )
        order = SimpleNamespace(
            id=9,
            order_type='BORROW',
            status='PROCESSING',
            completed_at=None,
            updated_at=None,
            save=Mock(),
        )
        borrow = SimpleNamespace(
            id=14,
            order_id=order.id,
            order=order,
            borrower_id=12,
            lender_id=13,
            status='RETURN_REQUESTED',
            return_status='SHIPPING',
            return_tracking_code='RET-123',
            expected_return_at=now - timedelta(hours=49),
            actual_return_at=None,
            return_approved_at=None,
            late_fee_amount=Decimal('0'),
            borrow_terms_snapshot={'late_fee_per_day': '1500.0000'},
            updated_at=None,
            lend_listing=listing,
            save=Mock(),
        )
        shipment = SimpleNamespace(
            id=23,
            order_id=order.id,
            order=order,
            tracking_code='RET-123',
            status='IN_TRANSIT',
            shipped_at=now - timedelta(hours=1),
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event_model = Mock()
        event_model.objects.create.return_value = SimpleNamespace(id=84)

        with patch(
            'books.shipment_services.timezone.now',
            return_value=now,
        ), patch(
            'books.shipment_services.notify_borrow_order_parties',
        ) as notify_borrow:
            event, _old_status = update_shipment_status.__wrapped__(
                shipment,
                status='DELIVERED',
                source='ADMIN',
                borrow=borrow,
                event_model=event_model,
            )

        self.assertEqual(event.id, 84)
        self.assertEqual(borrow.status, 'COMPLETED')
        self.assertEqual(borrow.return_status, 'COMPLETED')
        self.assertEqual(borrow.actual_return_at, now)
        self.assertEqual(borrow.late_fee_amount, Decimal('3000.0000'))
        self.assertEqual(order.status, 'COMPLETED')
        self.assertEqual(listing.status, 'ACTIVE')
        self.assertEqual(book.status, 'AVAILABLE')
        notify_borrow.assert_called_once_with(
            borrow,
            title='Đã nhận lại sách · Phiếu mượn hoàn tất',
            content=(
                f'Admin đã xác nhận nhận lại sách của phiếu #{borrow.id}. '
                'Phiếu mượn đã hoàn tất.'
            ),
        )
        self.assertEqual(
            borrow.save.call_args.kwargs['update_fields'],
            [
                'status',
                'return_status',
                'actual_return_at',
                'return_approved_at',
                'late_fee_amount',
                'updated_at',
            ],
        )

    def test_cod_delivery_pays_payment_when_order_is_completed(self):
        now = Mock(name='now')
        payment = SimpleNamespace(
            id=31,
            payment_method='COD',
            status='PENDING',
            paid_at=None,
            updated_at=None,
            save=Mock(),
        )
        payment_manager = Mock()
        payment_manager.select_for_update.return_value.filter.return_value = [payment]
        shipment_manager = Mock()
        shipment_manager.filter.return_value.exclude.return_value.exists.return_value = False
        order = SimpleNamespace(
            id=9,
            order_type='SALE',
            status='CONFIRMED',
            completed_at=None,
            updated_at=None,
            save=Mock(),
        )
        shipment = SimpleNamespace(
            id=5,
            order_id=order.id,
            order=order,
            status='OUT_FOR_DELIVERY',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event_model = Mock()
        event_model.objects.create.return_value = SimpleNamespace(id=82)

        with patch(
            'books.shipment_services.timezone.now',
            return_value=now,
        ), patch(
            'books.shipment_services.Shipment.objects',
            shipment_manager,
        ), patch(
            'books.shipment_services.Payment.objects',
            payment_manager,
        ), patch(
            'books.shipment_services.notify_order_status_changed',
        ):
            update_shipment_status.__wrapped__(
                shipment,
                status='DELIVERED',
                source='ADMIN',
                borrow=SimpleNamespace(return_tracking_code=None),
                event_model=event_model,
            )

        self.assertEqual(payment.status, 'PAID')
        self.assertIs(payment.paid_at, now)
        payment.save.assert_called_once_with(
            update_fields=['status', 'paid_at', 'updated_at'],
        )
        self.assertEqual(order.status, 'COMPLETED')
        self.assertIs(order.completed_at, now)

    def test_sale_order_waits_for_every_shipment_to_be_delivered(self):
        order = SimpleNamespace(
            id=9,
            order_type='SALE',
            status='CONFIRMED',
            completed_at=None,
            updated_at=None,
            save=Mock(),
        )
        shipment = SimpleNamespace(
            id=5,
            order_id=order.id,
            order=order,
            status='OUT_FOR_DELIVERY',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        shipment_manager = Mock()
        shipment_manager.filter.return_value.exclude.return_value.exists.return_value = True

        with patch(
            'books.shipment_services.Shipment.objects',
            shipment_manager,
        ), patch(
            'books.shipment_services.notify_order_status_changed',
        ) as notify:
            update_shipment_status.__wrapped__(
                shipment,
                status='DELIVERED',
                source='ADMIN',
                borrow=SimpleNamespace(return_tracking_code=None),
                event_model=Mock(),
            )

        self.assertEqual(shipment.status, 'DELIVERED')
        self.assertEqual(order.status, 'CONFIRMED')
        order.save.assert_not_called()
        notify.assert_not_called()

    def test_sale_delivery_rejects_unpayable_order_state(self):
        order = SimpleNamespace(
            id=9,
            order_type='SALE',
            status='CANCELLED',
            completed_at=None,
            updated_at=None,
            save=Mock(),
        )
        shipment = SimpleNamespace(
            id=5,
            order_id=order.id,
            order=order,
            status='OUT_FOR_DELIVERY',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
            tracking_events=Mock(),
        )
        shipment.tracking_events.order_by.return_value.first.return_value = None
        event_model = Mock()
        event_model.objects.create.return_value = SimpleNamespace(id=81)

        with self.assertRaises(ValidationError), patch(
            'books.shipment_services.notify_order_status_changed',
        ) as notify:
            update_shipment_status.__wrapped__(
                shipment,
                status='DELIVERED',
                source='ADMIN',
                borrow=SimpleNamespace(return_tracking_code=None),
                event_model=event_model,
            )

        order.save.assert_not_called()
        notify.assert_not_called()


class AdminShipmentPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = SimpleNamespace(id=76, is_authenticated=True, role='ADMIN')

    def test_list_detail_and_update_require_admin(self):
        requests = (
            (AdminShipmentListView.as_view(), 'get', {}),
            (AdminShipmentDetailView.as_view(), 'get', {'shipment_id': 1}),
            (AdminShipmentStatusView.as_view(), 'patch', {'shipment_id': 1}),
        )
        for view, method, kwargs in requests:
            anonymous = getattr(self.factory, method)(
                '/api/admin/dashboard/shipping/shipments/',
                {'status': 'PICKED_UP'} if method == 'patch' else None,
                format='json',
            )
            response = view(anonymous, **kwargs)
            self.assertEqual(response.status_code, 401)

            regular_user = getattr(self.factory, method)(
                '/api/admin/dashboard/shipping/shipments/1/status/',
                {'status': 'PICKED_UP'} if method == 'patch' else None,
                format='json',
            )
            force_authenticate(
                regular_user,
                user=SimpleNamespace(
                    id=25,
                    is_authenticated=True,
                    role='STUDENT',
                ),
            )
            response = view(regular_user, **kwargs)
            self.assertEqual(response.status_code, 403)

    def test_admin_update_returns_old_and_new_status_and_source(self):
        shipment = SimpleNamespace(
            id=3,
            order_id=7,
            tracking_code='TRACK-3',
            status='PENDING',
            shipped_at=None,
            delivered_at=None,
            updated_at=None,
            save=Mock(),
        )
        borrow_manager = Mock()
        borrow_manager.select_for_update.return_value.filter.return_value.first.return_value = None
        event = SimpleNamespace(id=17)
        request = self.factory.patch(
            '/api/admin/dashboard/shipping/shipments/3/status/',
            {'status': 'PICKED_UP', 'note': 'Picked up'},
            format='json',
        )
        view = AdminShipmentStatusView()
        request = view.initialize_request(request)
        request.user = self.admin

        with patch(
            'books.admin_dashboard_views.get_object_or_404',
            return_value=shipment,
        ), patch(
            'books.admin_dashboard_views.BorrowOrder.objects',
            borrow_manager,
        ), patch(
            'books.admin_dashboard_views.update_shipment_status',
            side_effect=lambda *args, **kwargs: (
                setattr(shipment, 'status', 'PICKED_UP') or event,
                'PENDING',
            ),
        ):
            response = AdminShipmentStatusView.patch.__wrapped__(
                view,
                request,
                shipment_id=3,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['old_status'], 'PENDING')
        self.assertEqual(response.data['status'], 'PICKED_UP')
        self.assertEqual(response.data['source'], 'ADMIN')

    def test_borrow_shipment_payload_includes_late_fee_summary(self):
        now = timezone.now()
        lender = SimpleNamespace(id=11, full_name='Lender', email='lender@example.test')
        borrower = SimpleNamespace(id=12, full_name='Borrower', email='borrower@example.test')
        borrow = SimpleNamespace(
            id=18,
            return_tracking_code=None,
            lender=lender,
            borrower=borrower,
            status='CONFIRMED',
            expected_return_at=now + timedelta(days=7),
            borrow_terms_snapshot={'late_fee_per_day': '2500'},
            late_fee_amount=Decimal('0'),
            actual_return_at=None,
        )
        order = SimpleNamespace(
            id=7,
            order_code='ORDER-7',
            order_type='BORROW',
            status='CONFIRMED',
            borrow_order=borrow,
        )
        shipment = SimpleNamespace(
            id=3,
            order=order,
            tracking_code='TRACK-3',
            carrier='Local delivery',
            status='PENDING',
            shipped_at=None,
            delivered_at=None,
            created_at=now,
            updated_at=now,
            tracking_events=SimpleNamespace(all=lambda: []),
        )

        payload = AdminShipmentListView.payload(shipment)

        self.assertEqual(payload['type'], 'BORROW')
        self.assertEqual(payload['borrow']['id'], borrow.id)
        self.assertEqual(payload['borrow']['late_fee_per_day'], '2500')
        self.assertEqual(payload['borrow']['late_fee_estimate'], '0')

    def test_missing_shipment_is_not_found(self):
        request = self.factory.patch(
            '/api/admin/dashboard/shipping/shipments/999/status/',
            {'status': 'PICKED_UP'},
            format='json',
        )
        view = AdminShipmentStatusView()
        request = view.initialize_request(request)
        request.user = self.admin
        with patch(
            'books.admin_dashboard_views.get_object_or_404',
            side_effect=Http404,
        ):
            with self.assertRaises(Http404):
                AdminShipmentStatusView.patch.__wrapped__(
                    view,
                    request,
                    shipment_id=999,
                )

    def test_sale_tracking_status_cannot_be_updated_by_seller_api(self):
        seller = SimpleNamespace(id=96, is_authenticated=True, role='STUDENT')
        order = SimpleNamespace(order_type='SALE', seller_id=seller.id)
        shipment = SimpleNamespace(
            id=30,
            order_id=31,
            tracking_code='PB-SALE-TEST',
            status='PENDING',
            order=order,
        )
        borrow_manager = Mock()
        borrow_manager.filter.return_value.first.return_value = None
        request = self.factory.post(
            '/api/shipments/30/tracking/',
            {'status': 'PICKED_UP'},
            format='json',
        )
        view = ShipmentTrackingCreateView()
        request = view.initialize_request(request)
        request.user = seller

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=shipment,
        ), patch(
            'books.commerce_api_views.BorrowOrder.objects',
            borrow_manager,
        ), patch(
            'books.commerce_api_views.ShipmentTracking.objects.create',
        ) as create_event:
            with self.assertRaises(PermissionDenied):
                ShipmentTrackingCreateView.post.__wrapped__(
                    view,
                    request,
                    shipment_id=shipment.id,
                )

        create_event.assert_not_called()


    def test_borrow_tracking_status_is_reserved_for_admin_shipping_api(self):
        borrower = SimpleNamespace(id=88, is_authenticated=True, role='STUDENT')
        order = SimpleNamespace(order_type='BORROW', seller_id=96)
        shipment = SimpleNamespace(
            id=30,
            order_id=31,
            tracking_code='PB-BORROW-TEST',
            status='PENDING',
            order=order,
        )
        borrow = SimpleNamespace(
            borrower_id=borrower.id,
            lender_id=96,
            return_tracking_code=None,
        )
        borrow_manager = Mock()
        borrow_manager.filter.return_value.first.return_value = borrow
        request = self.factory.post(
            '/api/shipments/30/tracking/',
            {'status': 'PICKED_UP'},
            format='json',
        )
        view = ShipmentTrackingCreateView()
        request = view.initialize_request(request)
        request.user = borrower

        with patch(
            'books.commerce_api_views.get_object_or_404',
            return_value=shipment,
        ), patch(
            'books.commerce_api_views.BorrowOrder.objects',
            borrow_manager,
        ), patch(
            'books.commerce_api_views.ShipmentTracking.objects.create',
        ) as create_event:
            with self.assertRaises(PermissionDenied):
                ShipmentTrackingCreateView.post.__wrapped__(
                    view,
                    request,
                    shipment_id=shipment.id,
                )

        create_event.assert_not_called()


class OverdueBorrowOrderTests(SimpleTestCase):
    def test_late_fee_counts_only_full_24_hour_periods(self):
        due_at = timezone.now()
        borrow = SimpleNamespace(
            expected_return_at=due_at,
            borrow_terms_snapshot={'late_fee_per_day': '2500.0000'},
        )

        before_full_day = calculate_borrow_late_fee(
            borrow,
            at=due_at + timedelta(hours=23, minutes=59),
        )
        after_full_day = calculate_borrow_late_fee(
            borrow,
            at=due_at + timedelta(hours=24),
        )
        after_two_full_days = calculate_borrow_late_fee(
            borrow,
            at=due_at + timedelta(hours=49),
        )

        self.assertEqual(before_full_day['late_days'], 0)
        self.assertEqual(before_full_day['late_fee_amount'], Decimal('0'))
        self.assertEqual(after_full_day['late_days'], 1)
        self.assertEqual(after_full_day['late_fee_amount'], Decimal('2500.0000'))
        self.assertEqual(after_two_full_days['late_days'], 2)
        self.assertEqual(after_two_full_days['late_fee_amount'], Decimal('5000.0000'))

    def test_overdue_sweep_updates_active_order_once_and_notifies_both_parties(self):
        now = timezone.now()
        borrow = SimpleNamespace(
            id=22,
            status='ACTIVE',
            updated_at=None,
            borrower_id=12,
            lender_id=13,
            save=Mock(),
        )
        queryset = Mock()
        queryset.filter.return_value.order_by.return_value = [borrow]
        manager = Mock()
        manager.select_for_update.return_value.select_related.return_value = queryset

        with patch('books.services.BorrowOrder.objects', manager), patch(
            'books.services.notify_borrow_order_parties',
        ) as notify:
            count = mark_overdue_borrow_orders.__wrapped__(now=now)

        self.assertEqual(count, 1)
        self.assertEqual(borrow.status, 'OVERDUE')
        borrow.save.assert_called_once_with(update_fields=['status', 'updated_at'])
        notify.assert_called_once_with(
            borrow,
            title='Phiếu mượn đã quá hạn',
            content=(
                f'Phiếu mượn #{borrow.id} đã quá hạn. '
                'Phí trễ được tính theo số ngày 24 giờ hoàn tất và Admin sẽ xác nhận khi nhận sách trả.'
            ),
            created_at=now,
        )
