from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

from .models import User


class PassbookJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise AuthenticationFailed('Token không hợp lệ.', code='token_user_id_missing') from exc

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed('User không tồn tại.', code='user_not_found') from exc

        if user.status != 'active':
            raise AuthenticationFailed('Tài khoản không hoạt động.', code='user_inactive')

        return user
