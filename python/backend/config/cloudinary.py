import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}


class CloudinaryVerificationUnavailable(APIException):
    status_code = 503
    default_detail = 'Không thể xác minh ảnh trên Cloudinary.'
    default_code = 'cloudinary_unavailable'


def verify_cloudinary_image(*, user_id, image_url, public_id):
    if not isinstance(public_id, str) or not re.fullmatch(
        rf'user-{user_id}-[a-f0-9]{{32}}',
        public_id,
    ):
        raise ValidationError({
            'images': 'Ảnh phải được tải lên bằng phiên upload của tài khoản hiện tại.',
        })

    credentials = (
        settings.CLOUDINARY_API_KEY,
        settings.CLOUDINARY_API_SECRET,
    )
    if not settings.CLOUDINARY_CLOUD_NAME or not all(credentials):
        raise CloudinaryVerificationUnavailable(
            'Cloudinary chưa được cấu hình để xác minh ảnh.',
        )
    if not image_url or not image_url.startswith('https://'):
        raise ValidationError({'images': 'Ảnh phải có URL HTTPS hợp lệ.'})

    url = (
        f'https://api.cloudinary.com/v1_1/'
        f'{urllib.parse.quote(settings.CLOUDINARY_CLOUD_NAME, safe="")}'
        f'/resources/image/upload/{urllib.parse.quote(public_id, safe="")}'
    )
    credential = base64.b64encode(
        f'{settings.CLOUDINARY_API_KEY}:{settings.CLOUDINARY_API_SECRET}'.encode(),
    ).decode()
    request = urllib.request.Request(
        url,
        headers={'Authorization': f'Basic {credential}'},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            resource = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValidationError({
                'images': 'Không tìm thấy ảnh đã tải lên Cloudinary.',
            }) from exc
        raise CloudinaryVerificationUnavailable() from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise CloudinaryVerificationUnavailable() from exc

    if not isinstance(resource, dict):
        raise CloudinaryVerificationUnavailable()
    image_format = resource.get('format')
    byte_count = resource.get('bytes')
    if (
        resource.get('public_id') != public_id
        or resource.get('secure_url') != image_url
        or image_format not in ALLOWED_IMAGE_FORMATS
        or not isinstance(byte_count, int)
        or byte_count <= 0
        or byte_count > MAX_IMAGE_BYTES
    ):
        raise ValidationError({
            'images': (
                'Ảnh không hợp lệ. Chỉ chấp nhận JPG, PNG, WebP hoặc GIF '
                'và tối đa 10 MB mỗi ảnh.'
            ),
        })
