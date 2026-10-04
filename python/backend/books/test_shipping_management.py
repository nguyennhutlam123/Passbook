from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.http import Http404
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
    update_shipment_status,
    validate_shipment_transition,
)


class ShipmentStateMachineTests(SimpleTestCase):
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
