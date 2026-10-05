import re

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import signing
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OtpVerification, User
from .services import issue_otp, verify_otp

OTP_PURPOSES = {
    'REGISTER',
    'LOGIN',
    'FORGOT_PASSWORD',
    'CHANGE_EMAIL',
    'CHANGE_PHONE',
}


def _channel_for_target(target):
    return 'EMAIL' if '@' in target else 'PHONE'


def _user_for_target(target, channel):
    if channel == 'EMAIL':
        return User.objects.filter(email=target.lower()).first()
    matches = list(User.objects.filter(phone=target).order_by('id')[:2])
    return matches[0] if len(matches) == 1 else None


class OtpVerifySerializer(serializers.Serializer):
    target = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    purpose = serializers.ChoiceField(choices=sorted(OTP_PURPOSES))
    otp = serializers.RegexField(r'^\d{6}$', write_only=True)

    def validate(self, attrs):
        if attrs['purpose'] == 'REGISTER' and '@' not in attrs['target']:
            raise serializers.ValidationError({'target': 'Đăng ký hiện xác minh bằng email.'})
        attrs['target'] = _validate_target(attrs['target'])
        return attrs


class OtpResendSerializer(serializers.Serializer):
    target = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    purpose = serializers.ChoiceField(choices=sorted(OTP_PURPOSES))

    def validate_target(self, value):
        return _validate_target(value)


class TargetInputSerializer(serializers.Serializer):
    target = serializers.CharField(
        max_length=255,
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate_target(self, value):
        return _validate_target(value)


def _validate_target(value):
    value = value.strip()
    if '@' in value:
        return serializers.EmailField().run_validation(value).lower()
    if not re.fullmatch(r'\+?[0-9 ()-]{7,30}', value):
        raise serializers.ValidationError('Thông tin liên hệ không hợp lệ.')
    return value


class OtpRequestView(APIView):
    def post(self, request):
        serializer = OtpResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data['target']
        purpose = serializer.validated_data['purpose']
        channel = _channel_for_target(target)
        user = None

        if purpose == 'REGISTER' and channel != 'EMAIL':
            raise serializers.ValidationError({'target': 'Đăng ký hiện xác minh bằng email.'})

        if purpose in ('CHANGE_EMAIL', 'CHANGE_PHONE'):
            if not request.user.is_authenticated:
                raise NotAuthenticated()
            expected_channel = 'EMAIL' if purpose == 'CHANGE_EMAIL' else 'PHONE'
            if channel != expected_channel:
                raise serializers.ValidationError({'target': 'Kênh không khớp với mục đích xác minh.'})
            user = request.user
            if purpose == 'CHANGE_EMAIL' and User.objects.filter(
                email__iexact=target,
            ).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({'target': 'Email đã được đăng ký.'})
            if purpose == 'CHANGE_PHONE' and User.objects.filter(
                phone=target,
            ).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({'target': 'Số điện thoại đã được sử dụng.'})
        elif purpose == 'REGISTER':
            user = _user_for_target(target, channel)
            if user is None or user.status != 'PENDING_VERIFICATION':
                return Response(
                    {'detail': 'Nếu tài khoản cần xác minh, mã sẽ được gửi đến địa chỉ đã đăng ký.'},
                    status=status.HTTP_202_ACCEPTED,
                )
        elif purpose == 'LOGIN':
            user = _user_for_target(target, channel)
            if user is None or user.status != 'ACTIVE':
                return Response(
                    {'detail': 'Nếu tài khoản đủ điều kiện, mã sẽ được gửi.'},
                    status=status.HTTP_202_ACCEPTED,
                )
        else:
            user = _user_for_target(target, channel)

        issue_otp(
            target=target,
            channel=channel,
            purpose=purpose,
            user=user,
        )
        return Response(
            {
                'detail': 'Nếu yêu cầu hợp lệ, mã xác minh sẽ được gửi.',
                'otp_expires_in_seconds': settings.OTP_LIFETIME_SECONDS,
                'otp_resend_after_seconds': settings.OTP_RESEND_COOLDOWN_SECONDS,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class OtpVerifyView(APIView):
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        purpose = data['purpose']
        user_id = None
        if purpose in ('CHANGE_EMAIL', 'CHANGE_PHONE'):
            if not request.user.is_authenticated:
                raise NotAuthenticated()
            user_id = request.user.id

        verification = verify_otp(
            target=data['target'],
            purpose=purpose,
            code=data['otp'],
            user_id=user_id,
        )

        if purpose == 'REGISTER':
            user = get_object_or_404(
                User,
                pk=verification.user_id,
                status='PENDING_VERIFICATION',
            )
            user.status = 'ACTIVE'
            user.updated_at = timezone.now()
            user.save(update_fields=['status', 'updated_at'])
            return Response({
                'detail': 'Tài khoản đã được xác minh.',
                'user_id': user.id,
            })

        if purpose == 'LOGIN':
            user = get_object_or_404(User, pk=verification.user_id, status='ACTIVE')
            refresh = RefreshToken.for_user(user)
            from .serializers import RegisteredUserSerializer

            return Response({
                'message': 'Đăng nhập thành công',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': RegisteredUserSerializer(user).data,
            })

        if purpose == 'FORGOT_PASSWORD':
            if verification.user_id is None:
                raise serializers.ValidationError(
                    'Mã xác minh không hợp lệ hoặc đã hết hạn.',
                )
            reset_token = signing.dumps(
                {'user_id': verification.user_id, 'otp_id': verification.id},
                salt='passbook.password-reset',
            )
            return Response({'reset_token': reset_token})

        if purpose == 'CHANGE_EMAIL':
            user = get_object_or_404(User, pk=verification.user_id)
            if User.objects.filter(email__iexact=verification.target).exclude(
                pk=user.pk,
            ).exists():
                raise serializers.ValidationError({'target': 'Email đã được đăng ký.'})
            user.email = verification.target.lower()
        elif purpose == 'CHANGE_PHONE':
            user = get_object_or_404(User, pk=verification.user_id)
            if User.objects.filter(phone=verification.target).exclude(
                pk=user.pk,
            ).exists():
                raise serializers.ValidationError({'target': 'Số điện thoại đã được sử dụng.'})
            user.phone = verification.target
        else:
            raise PermissionDenied('Mục đích xác minh không được hỗ trợ.')

        user.updated_at = timezone.now()
        try:
            with transaction.atomic():
                user.save(update_fields=['email', 'phone', 'updated_at'])
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {'target': 'Thông tin liên hệ đã được sử dụng.'},
            ) from exc
        return Response({'detail': 'Thông tin liên hệ đã được xác minh.'})


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = TargetInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data['target']
        channel = _channel_for_target(target)
        user = _user_for_target(target, channel)
        issue_otp(
            target=target,
            channel=channel,
            purpose='FORGOT_PASSWORD',
            user=user,
        )
        return Response(
            {
                'detail': 'Nếu tài khoản tồn tại, mã xác minh sẽ được gửi.',
                'otp_expires_in_seconds': settings.OTP_LIFETIME_SECONDS,
                'otp_resend_after_seconds': settings.OTP_RESEND_COOLDOWN_SECONDS,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField(write_only=True, allow_blank=False)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        allow_blank=False,
        trim_whitespace=False,
    )


class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = signing.loads(
                serializer.validated_data['reset_token'],
                salt='passbook.password-reset',
                max_age=settings.OTP_RESET_TOKEN_LIFETIME_SECONDS,
            )
        except signing.BadSignature as exc:
            raise serializers.ValidationError(
                {'reset_token': 'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.'},
            ) from exc

        with transaction.atomic():
            verification = get_object_or_404(
                OtpVerification.objects.select_for_update(),
                pk=payload.get('otp_id'),
                user_id=payload.get('user_id'),
                purpose='FORGOT_PASSWORD',
                status='VERIFIED',
            )
            user = get_object_or_404(User.objects.select_for_update(), pk=payload.get('user_id'))
            try:
                validate_password(serializer.validated_data['new_password'], user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'new_password': exc.messages}) from exc

            user.password_hash = make_password(serializer.validated_data['new_password'])
            user.updated_at = timezone.now()
            user.save(update_fields=['password_hash', 'updated_at'])
            verification.status = 'BLOCKED'
            verification.updated_at = timezone.now()
            verification.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Đã đặt lại mật khẩu.'})


class ChangeContactRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, channel):
        if channel == 'email':
            serializer = serializers.EmailField()
            target = serializer.run_validation(request.data.get('email'))
            purpose = 'CHANGE_EMAIL'
        else:
            target = serializers.CharField(max_length=30).run_validation(
                request.data.get('phone'),
            )
            if not re.fullmatch(r'\+?[0-9 ()-]{7,30}', target):
                raise serializers.ValidationError({'phone': 'Số điện thoại không hợp lệ.'})
            purpose = 'CHANGE_PHONE'

        user = request.user
        field_name = 'email' if channel == 'email' else 'phone'
        if User.objects.filter(**{f'{field_name}__iexact' if channel == 'email' else field_name: target}).exclude(
            pk=user.pk,
        ).exists():
            raise serializers.ValidationError({'target': 'Thông tin liên hệ đã được sử dụng.'})
        issue_otp(
            target=target,
            channel='EMAIL' if channel == 'email' else 'PHONE',
            purpose=purpose,
            user=user,
        )
        return Response(
            {'detail': 'Mã xác minh sẽ được gửi đến thông tin liên hệ mới.'},
            status=status.HTTP_202_ACCEPTED,
        )
