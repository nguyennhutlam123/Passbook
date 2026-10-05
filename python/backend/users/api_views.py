from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.exceptions import AuthenticationFailed

from books.pagination import BookPagination
from .models import User, UserAddress
from .serializers import (
    LoginSerializer,
    ChangePasswordSerializer,
    ProfileSerializer,
    PublicSellerSerializer,
    RegisterSerializer,
    RegisteredUserSerializer,
    UserAddressSerializer,
)
from .services import issue_otp
from .tokens import refresh_token_for_user, revoke_token_pair


class RegisterView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        issue_otp(
            target=user.email,
            channel='EMAIL',
            purpose='REGISTER',
            user=user,
        )
        return Response(
            {
                'message': 'Đăng ký thành công. Vui lòng xác minh email.',
                'verification_required': True,
                'target': user.email,
                'otp_expires_in_seconds': settings.OTP_LIFETIME_SECONDS,
                'otp_resend_after_seconds': settings.OTP_RESEND_COOLDOWN_SECONDS,
                'user': RegisteredUserSerializer(user).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get('email')
        phone = serializer.validated_data.get('phone')
        password = serializer.validated_data['password']
        if email:
            user = User.objects.filter(email=email).first()
        else:
            phone_matches = list(
                User.objects.filter(phone=phone).order_by('id')[:2],
            )
            user = phone_matches[0] if len(phone_matches) == 1 else None

        if user is None:
            return Response(
                {'detail': 'Thông tin đăng nhập không đúng.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if user.status == 'PENDING_VERIFICATION':
            return Response(
                {'detail': 'Vui lòng xác minh tài khoản trước khi đăng nhập.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.status != 'ACTIVE':
            return Response(
                {'detail': 'Tài khoản không hoạt động.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not check_password(password, user.password_hash):
            return Response(
                {'detail': 'Thông tin đăng nhập không đúng.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        otp_channel = serializer.validated_data.get('otp_channel')
        if otp_channel:
            target = user.email if otp_channel == 'EMAIL' else user.phone
            if not target:
                raise serializers.ValidationError({
                    'otp_channel': 'Tài khoản chưa có thông tin cho kênh xác minh này.',
                })
            issue_otp(
                target=target,
                channel=otp_channel,
                purpose='LOGIN',
                user=user,
            )
            return Response(
                {
                    'verification_required': True,
                    'target': target,
                    'purpose': 'LOGIN',
                    'otp_expires_in_seconds': settings.OTP_LIFETIME_SECONDS,
                    'otp_resend_after_seconds': settings.OTP_RESEND_COOLDOWN_SECONDS,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Đăng nhập thành công',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': RegisteredUserSerializer(user).data,
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = refresh_token_for_user(
            serializer.validated_data['refresh'],
            request.user.id,
        )
        access_token = request.auth
        if access_token is None:
            raise AuthenticationFailed('Access token không hợp lệ.')
        revoke_token_pair(access_token, token)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutInputSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, allow_blank=False, trim_whitespace=True)


class ActiveUserTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = refresh_token_for_user(attrs['refresh'])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        if user_id is None or not User.objects.filter(
            pk=user_id,
            status='ACTIVE',
        ).exists():
            raise AuthenticationFailed('Tài khoản không hoạt động.')
        data = {'access': str(refresh.access_token)}
        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            data['refresh'] = str(refresh)
        return data


class ActiveUserTokenRefreshView(TokenRefreshView):
    serializer_class = ActiveUserTokenRefreshSerializer


class AuthenticatedUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'user': RegisteredUserSerializer(request.user).data,
        })


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = User.objects.select_related('university').get(pk=request.user.id)
        return Response(ProfileSerializer(user).data)

    def patch(self, request):
        user = User.objects.select_related('university').get(pk=request.user.id)
        serializer = ProfileSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(updated_at=timezone.now())
        return Response(ProfileSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.select_for_update().get(pk=request.user.id)
        if not check_password(
            serializer.validated_data['old_password'],
            user.password_hash,
        ):
            return Response(
                {'detail': 'Mật khẩu hiện tại không đúng.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_password = serializer.validated_data['new_password']
        if check_password(new_password, user.password_hash):
            raise serializers.ValidationError({
                'new_password': 'Mật khẩu mới phải khác mật khẩu hiện tại.',
            })
        try:
            validate_password(new_password, user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                'new_password': exc.messages,
            }) from exc
        user.password_hash = make_password(new_password)
        user.updated_at = timezone.now()
        user.save(update_fields=['password_hash', 'updated_at'])
        return Response({'message': 'Đổi mật khẩu thành công.'})


class SellerProfileView(APIView):
    def get(self, request, user_id):
        user = User.objects.select_related('university').filter(
            pk=user_id,
            status='ACTIVE',
        ).first()
        if user is None:
            from django.http import Http404
            raise Http404
        return Response(PublicSellerSerializer(user).data)


class UserAddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = UserAddress.objects.filter(user=request.user).order_by(
            '-is_default', '-created_at', '-id',
        )
        paginator = BookPagination()
        page = paginator.paginate_queryset(addresses, request, view=self)
        return paginator.get_paginated_response(
            UserAddressSerializer(page, many=True).data,
        )

    def post(self, request):
        serializer = UserAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        with transaction.atomic():
            if serializer.validated_data.get('is_default'):
                UserAddress.objects.filter(user=request.user).update(is_default=False)
            address = serializer.save(
                user=request.user,
                created_at=now,
                updated_at=now,
            )
        return Response(
            UserAddressSerializer(address).data,
            status=status.HTTP_201_CREATED,
        )


class UserAddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, address_id):
        address = get_object_or_404(
            UserAddress,
            pk=address_id,
            user=request.user,
        )
        serializer = UserAddressSerializer(
            address,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        with transaction.atomic():
            if serializer.validated_data.get('is_default') is True:
                UserAddress.objects.filter(user=request.user).exclude(
                    pk=address.pk,
                ).update(is_default=False)
            address = serializer.save(updated_at=now)
        return Response(UserAddressSerializer(address).data)

    def delete(self, request, address_id):
        address = get_object_or_404(
            UserAddress,
            pk=address_id,
            user=request.user,
        )
        address.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
