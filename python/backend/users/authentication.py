from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

from .models import User
from .tokens import is_token_revoked


class PassbookJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        if is_token_revoked(validated_token):
            raise AuthenticationFailed('Token đã bị thu hồi.', code='token_revoked')
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise AuthenticationFailed('Token không hợp lệ.', code='token_user_id_missing') from exc

        try:
            user = User.objects.select_related('university').get(pk=user_id)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed('User không tồn tại.', code='user_not_found') from exc

        if user.status != 'ACTIVE':
            raise AuthenticationFailed('Tài khoản không hoạt động.', code='user_inactive')

        return user
