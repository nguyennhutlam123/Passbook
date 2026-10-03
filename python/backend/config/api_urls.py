import hashlib
import time

from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.api_views import (
    AuthenticatedUserView,
    ChangePasswordView,
    LoginView,
    ProfileView,
    RegisterView,
    SellerProfileView,
)
from messaging.api_views import (
    ConversationCreateView,
    ConversationDetailView,
    ConversationListView,
    MessageListView,
)
from notifications.api_views import NotificationListView, NotificationReadView
from reports.api_views import MyReportListView, ReportCreateView
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
            'folder': settings.CLOUDINARY_UPLOAD_FOLDER,
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
            'folder': settings.CLOUDINARY_UPLOAD_FOLDER,
            'timestamp': timestamp,
            'signature': signature,
        })


urlpatterns = [
    path('health/', health_check, name='health-check'),
    path(
        'uploads/cloudinary/signature/',
        CloudinaryUploadSignatureView.as_view(),
        name='cloudinary-upload-signature',
    ),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/authenticated-user/', AuthenticatedUserView.as_view(), name='authenticated-user'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('users/<int:user_id>/profile/', SellerProfileView.as_view(), name='seller-profile'),
    path('my-books/', MyBooksView.as_view(), name='my-books'),
    path('books/<int:book_id>/conversations/', ConversationCreateView.as_view(), name='conversation-create'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view(), name='message-list'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:notification_id>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('reports/', ReportCreateView.as_view(), name='report-create'),
    path('reports/my/', MyReportListView.as_view(), name='my-report-list'),
    path('books/', BookListView.as_view(), name='book-list'),
    path('books/<int:book_id>/images/', BookImageListView.as_view(), name='book-image-list'),
    path('books/<int:book_id>/images/<int:image_id>/', BookImageDetailView.as_view(), name='book-image-detail'),
    path('books/<int:book_id>/favorite/', FavoriteCreateDeleteView.as_view(), name='book-favorite'),
    path('favorites/', FavoriteListView.as_view(), name='favorite-list'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book-detail'),
    path('books/<int:pk>/sold/', BookSoldView.as_view(), name='book-sold'),
]
