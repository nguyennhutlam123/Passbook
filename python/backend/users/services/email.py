import json
import logging
import urllib.error
import urllib.request

from django.conf import settings


logger = logging.getLogger(__name__)
RESEND_EMAILS_URL = 'https://api.resend.com/emails'


class EmailProviderError(Exception):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_email(*, recipient, subject, text):
    api_key = settings.EMAIL_API_KEY.strip()
    sender = settings.DEFAULT_FROM_EMAIL.strip()
    timeout = settings.EMAIL_API_TIMEOUT
    if not api_key or not sender or timeout <= 0:
        logger.warning('OTP email provider configuration is missing or invalid.')
        raise EmailProviderError('Email provider is not configured.')

    body = json.dumps({
        'from': sender,
        'to': [recipient],
        'subject': subject,
        'text': text,
    }).encode('utf-8')
    request = urllib.request.Request(
        RESEND_EMAILS_URL,
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Passbook/1.0',
        },
        method='POST',
    )

    try:
        opener = urllib.request.build_opener(_NoRedirectHandler)
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
    except urllib.error.HTTPError as exc:
        logger.warning(
            'OTP email provider rejected delivery (HTTP %d).',
            exc.code,
        )
        raise EmailProviderError(
            f'Email provider rejected the message (HTTP {exc.code}).',
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            'OTP email provider request failed (%s).',
            type(exc).__name__,
        )
        raise EmailProviderError('Email provider request failed.') from exc

    if not 200 <= status_code < 300:
        logger.warning(
            'OTP email provider returned an unsuccessful status (HTTP %d).',
            status_code,
        )
        raise EmailProviderError(
            f'Email provider returned HTTP {status_code}.',
        )
