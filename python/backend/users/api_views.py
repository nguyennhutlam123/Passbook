from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    LoginSerializer,
    ChangePasswordSerializer,
    ProfileSerializer,
    PublicSellerSerializer,
    RegisterSerializer,
    RegisteredUserSerializer,
)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'Đăng ký thành công',
                'user': RegisteredUserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = User.objects.filter(email=email).first()

        if user is None:
            return Response(
                {'detail': 'Email hoặc mật khẩu không đúng.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if user.status != 'active':
            return Response(
                {'detail': 'Tài khoản không hoạt động.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not check_password(password, user.password_hash):
            return Response(
                {'detail': 'Email hoặc mật khẩu không đúng.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Đăng nhập thành công',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': RegisteredUserSerializer(user).data,
        })


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

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not check_password(serializer.validated_data['old_password'], request.user.password_hash):
            return Response(
                {'detail': 'Mật khẩu hiện tại không đúng.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.get(pk=request.user.id)
        user.password_hash = make_password(serializer.validated_data['new_password'])
        user.updated_at = timezone.now()
        user.save(update_fields=['password_hash', 'updated_at'])
        return Response({'message': 'Đổi mật khẩu thành công.'})


class SellerProfileView(APIView):
    def get(self, request, user_id):
        user = User.objects.select_related('university').filter(
            pk=user_id,
            status='active',
        ).first()
        if user is None:
            from django.http import Http404
            raise Http404
        return Response(PublicSellerSerializer(user).data)
