import hashlib
import time

from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.api_views import (
    AuthenticatedUserView,
    ActiveUserTokenRefreshView,
    ChangePasswordView,
    LoginView,
    LogoutView,
    ProfileView,
    RegisterView,
    SellerProfileView,
    UserAddressDetailView,
    UserAddressListCreateView,
)
from users.models import Faculty, Language, Major, Subject, University
from users.otp_api_views import (
    ChangeContactRequestView,
    ForgotPasswordView,
    OtpRequestView,
    OtpVerifyView,
    ResetPasswordView,
)
from messaging.api_views import (
    ConversationCreateView,
    ConversationDetailView,
    ConversationListView,
    MessageListView,
)
from notifications.api_views import (
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
)
from reports.api_views import MyReportListView, ReportCreateView
from reports.admin_api_views import AdminReportDetailView, AdminReportListView
from reports.dashboard_api_views import AdminDashboardView
from books.api_views import (
    BookDetailView,
    BookImageDetailView,
    BookImageListView,
    BookListView,
    BookSoldView,
    FavoriteCreateDeleteView,
    FavoriteListView,
    MyBooksView,
)
from users.admin_api_views import (
    AdminUserListView,
    AdminUserStatusView,
    AdminUserViolationDetailView,
    AdminUserViolationListCreateView,
    MyViolationListView,
)
from books.commerce_api_views import (
    BookReservationActionView,
    BookReservationListCreateView,
    BorrowOrderActionView,
    BorrowOrderListView,
    BorrowOrderReturnRequestView,
    CartItemDetailView,
    CartItemListCreateView,
    CartView,
    CheckoutView,
    LendListingListCreateView,
    LendListingDetailView,
    OrderDetailView,
    OrderListView,
    OrderCancelView,
    FakeRefundTransitionView,
    FakePaymentTransitionView,
    PaymentListCreateView,
    RefundCreateView,
    ReturnCreateView,
    ReturnActionView,
    ReviewCreateView,
    ShipmentListCreateView,
    ShipmentTrackingCreateView,
)
from books.sale_api_views import (
    SaleListingDetailView,
    SaleListingListCreateView,
)
from books.models import Category
from books.request_api_views import (
    BookIntentSummaryView,
    BookRequestDetailView,
    BookRequestInterestView,
    BookRequestListCreateView,
    BookRequestMatchListView,
)


def health_check(request):
    return JsonResponse({
        'status': 'ok',
        'message': 'PASSBOOK API is running',
    })


class CloudinaryUploadSignatureView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        missing = [
            name for name, value in (
                ('CLOUDINARY_CLOUD_NAME', settings.CLOUDINARY_CLOUD_NAME),
                ('CLOUDINARY_API_KEY', settings.CLOUDINARY_API_KEY),
                ('CLOUDINARY_API_SECRET', settings.CLOUDINARY_API_SECRET),
            ) if not value
        ]
        if missing:
            return Response(
                {'detail': 'Cloudinary chưa được cấu hình.', 'missing': missing},
                status=503,
            )

        timestamp = int(time.time())
        parameters = {
            'asset_folder': settings.CLOUDINARY_UPLOAD_FOLDER,
            'timestamp': timestamp,
        }
        signature_base = '&'.join(
            f'{key}={value}' for key, value in sorted(parameters.items())
        )
        signature = hashlib.sha1(
            f'{signature_base}{settings.CLOUDINARY_API_SECRET}'.encode(),
        ).hexdigest()
        return Response({
            'cloud_name': settings.CLOUDINARY_CLOUD_NAME,
            'api_key': settings.CLOUDINARY_API_KEY,
            'asset_folder': settings.CLOUDINARY_UPLOAD_FOLDER,
            'timestamp': timestamp,
            'signature': signature,
        })


class CatalogOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        faculties = Faculty.objects.filter(status='ACTIVE')
        majors = Major.objects.filter(status='ACTIVE')
        university_id = self._optional_id(request, 'university_id')
        faculty_id = self._optional_id(request, 'faculty_id')
        if university_id:
            faculties = faculties.filter(university_id=university_id)
        if faculty_id:
            majors = majors.filter(faculty_id=faculty_id)
        return Response({
            'universities': list(
                University.objects.filter(status='ACTIVE')
                .order_by('name', 'id')
                .values('id', 'name'),
            ),
            'faculties': list(faculties.order_by('name', 'id').values('id', 'name', 'university_id')),
            'majors': list(majors.order_by('name', 'id').values('id', 'name', 'faculty_id')),
            'subjects': list(
                Subject.objects.filter(status='ACTIVE')
                .order_by('name', 'id')
                .values('id', 'name', 'code'),
            ),
            'categories': list(
                Category.objects.filter(status='ACTIVE')
                .order_by('name', 'id')
                .values('id', 'name'),
            ),
            'languages': list(
                Language.objects.filter(status='ACTIVE')
                .order_by('name', 'id')
                .values('id', 'name', 'code'),
            ),
        })

    @staticmethod
    def _optional_id(request, key):
        value = request.query_params.get(key)
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise serializers.ValidationError({key: f'{key} phải là số nguyên.'}) from exc
        if parsed < 1:
            raise serializers.ValidationError({key: f'{key} phải lớn hơn 0.'})
        return parsed


urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('catalog/options/', CatalogOptionsView.as_view(), name='catalog-options'),
    path(
        'uploads/cloudinary/signature/',
        CloudinaryUploadSignatureView.as_view(),
        name='cloudinary-upload-signature',
    ),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path(
        'auth/token/refresh/',
        ActiveUserTokenRefreshView.as_view(),
        name='token-refresh',
    ),
    path('auth/verify-otp/', OtpVerifyView.as_view(), name='verify-otp'),
    path('auth/resend-otp/', OtpRequestView.as_view(), name='resend-otp'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path(
        'auth/change-email/request/',
        ChangeContactRequestView.as_view(),
        {'channel': 'email'},
        name='change-email-request',
    ),
    path(
        'auth/change-phone/request/',
        ChangeContactRequestView.as_view(),
        {'channel': 'phone'},
        name='change-phone-request',
    ),
    path('auth/authenticated-user/', AuthenticatedUserView.as_view(), name='authenticated-user'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('users/<int:user_id>/profile/', SellerProfileView.as_view(), name='seller-profile'),
    path('users/addresses/', UserAddressListCreateView.as_view(), name='address-list-create'),
    path('users/addresses/<int:address_id>/', UserAddressDetailView.as_view(), name='address-detail'),
    path('my-books/', MyBooksView.as_view(), name='my-books'),
    path('books/<int:book_id>/conversations/', ConversationCreateView.as_view(), name='conversation-create'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view(), name='message-list'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/read-all/', NotificationReadAllView.as_view(), name='notification-read-all'),
    path('notifications/<int:notification_id>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('reports/', ReportCreateView.as_view(), name='report-create'),
    path('reports/my/', MyReportListView.as_view(), name='my-report-list'),
    path('admin/reports/', AdminReportListView.as_view(), name='admin-report-list'),
    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path(
        'admin/reports/<int:report_id>/',
        AdminReportDetailView.as_view(),
        name='admin-report-detail',
    ),
    path('users/violations/', MyViolationListView.as_view(), name='my-violation-list'),
    path(
        'admin/users/',
        AdminUserListView.as_view(),
        name='admin-user-list',
    ),
    path(
        'admin/users/<int:user_id>/violations/',
        AdminUserViolationListCreateView.as_view(),
        name='admin-user-violations',
    ),
    path(
        'admin/violations/<int:violation_id>/',
        AdminUserViolationDetailView.as_view(),
        name='admin-violation-detail',
    ),
    path(
        'admin/users/<int:user_id>/status/',
        AdminUserStatusView.as_view(),
        name='admin-user-status',
    ),
    path('books/', BookListView.as_view(), name='book-list'),
    path('books/<int:book_id>/intents/', BookIntentSummaryView.as_view(), name='book-intents'),
    path('sale-listings/', SaleListingListCreateView.as_view(), name='sale-listing-list-create'),
    path('sale-listings/<int:listing_id>/', SaleListingDetailView.as_view(), name='sale-listing-detail'),
    path('book-requests/', BookRequestListCreateView.as_view(), name='book-request-list-create'),
    path('book-requests/<int:request_id>/', BookRequestDetailView.as_view(), name='book-request-detail'),
    path('book-requests/<int:request_id>/matches/', BookRequestMatchListView.as_view(), name='book-request-matches'),
    path('book-requests/<int:request_id>/interests/', BookRequestInterestView.as_view(), name='book-request-interests'),
    path('books/<int:book_id>/images/', BookImageListView.as_view(), name='book-image-list'),
    path('books/<int:book_id>/images/<int:image_id>/', BookImageDetailView.as_view(), name='book-image-detail'),
    path('books/<int:book_id>/favorite/', FavoriteCreateDeleteView.as_view(), name='book-favorite'),
    path('favorites/', FavoriteListView.as_view(), name='favorite-list'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book-detail'),
    path('books/<int:pk>/sold/', BookSoldView.as_view(), name='book-sold'),
    path('books/<int:book_id>/reservations/', BookReservationListCreateView.as_view(), name='book-reservations'),
    path('book-reservations/', BookReservationListCreateView.as_view(), name='reservation-list'),
    path(
        'book-reservations/<int:reservation_id>/<str:action>/',
        BookReservationActionView.as_view(),
        name='reservation-action',
    ),
    path('cart/', CartView.as_view(), name='cart'),
    path('cart/items/', CartItemListCreateView.as_view(), name='cart-items'),
    path('cart/items/<int:item_id>/', CartItemDetailView.as_view(), name='cart-item-detail'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('lend-listings/', LendListingListCreateView.as_view(), name='lend-listings'),
    path('lend-listings/<int:listing_id>/', LendListingDetailView.as_view(), name='lend-listing-detail'),
    path('orders/', OrderListView.as_view(), name='order-list'),
    path('orders/<int:order_id>/cancel/', OrderCancelView.as_view(), name='order-cancel'),
    path('orders/<int:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:order_id>/payments/', PaymentListCreateView.as_view(), name='order-payments'),
    path(
        'admin/fake-payments/<int:payment_id>/transition/',
        FakePaymentTransitionView.as_view(),
        name='fake-payment-transition',
    ),
    path(
        'admin/fake-refunds/<int:refund_id>/transition/',
        FakeRefundTransitionView.as_view(),
        name='fake-refund-transition',
    ),
    path('orders/<int:order_id>/shipments/', ShipmentListCreateView.as_view(), name='order-shipments'),
    path('shipments/<int:shipment_id>/tracking/', ShipmentTrackingCreateView.as_view(), name='shipment-tracking'),
    path('orders/<int:order_id>/returns/', ReturnCreateView.as_view(), name='order-returns'),
    path('returns/<int:return_id>/<str:action>/', ReturnActionView.as_view(), name='return-action'),
    path('orders/<int:order_id>/refunds/', RefundCreateView.as_view(), name='order-refunds'),
    path('orders/<int:order_id>/reviews/', ReviewCreateView.as_view(), name='order-reviews'),
    path('borrow-orders/', BorrowOrderListView.as_view(), name='borrow-order-list'),
    path(
        'borrow-orders/<int:borrow_order_id>/<str:action>/',
        BorrowOrderActionView.as_view(),
        name='borrow-order-action',
    ),
    path(
        'borrow-orders/<int:borrow_order_id>/return-request/',
        BorrowOrderReturnRequestView.as_view(),
        name='borrow-order-return-request',
    ),
]
