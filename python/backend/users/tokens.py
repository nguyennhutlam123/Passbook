import time

from django.core.cache import cache
from rest_framework_simplejwt.settings import api_settings


def revoked_token_cache_key(token):
    return f'passbook:revoked-jwt:{token["jti"]}'


def revoke_token(token):
    remaining_seconds = int(token['exp']) - int(time.time())
    if remaining_seconds > 0:
        cache.set(revoked_token_cache_key(token), True, timeout=remaining_seconds)


def is_token_revoked(token):
    return cache.get(revoked_token_cache_key(token), False)


def revoke_token_pair(access_token, refresh_token):
    revoke_token(access_token)
    revoke_token(refresh_token)


def refresh_token_for_user(token_string, user_id=None):
    from rest_framework_simplejwt.exceptions import TokenError

    from rest_framework.exceptions import AuthenticationFailed

    from rest_framework_simplejwt.tokens import RefreshToken

    try:
        token = RefreshToken(token_string)
    except TokenError as exc:
        raise AuthenticationFailed('Refresh token không hợp lệ hoặc đã hết hạn.') from exc
    if user_id is not None and str(token.get(api_settings.USER_ID_CLAIM)) != str(user_id):
        raise AuthenticationFailed('Refresh token không thuộc tài khoản hiện tại.')
    if is_token_revoked(token):
        raise AuthenticationFailed('Refresh token đã bị thu hồi.')
    return token
