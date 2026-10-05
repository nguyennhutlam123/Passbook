import json
import logging
import urllib.error
import urllib.request
from html import escape

from django.conf import settings


logger = logging.getLogger(__name__)
BREVO_EMAILS_URL = 'https://api.brevo.com/v3/smtp/email'


class EmailProviderError(Exception):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_email(*, recipient, subject, text):
    api_key = settings.BREVO_API_KEY.strip()
    sender_email = settings.BREVO_SENDER_EMAIL.strip()
    sender_name = settings.BREVO_SENDER_NAME.strip()
    timeout = settings.BREVO_API_TIMEOUT
    if not api_key or not sender_email or not sender_name or timeout <= 0:
        logger.warning('OTP email provider configuration is missing or invalid.')
        raise EmailProviderError('Email provider is not configured.')

    body = json.dumps({
        'sender': {
            'name': sender_name,
            'email': sender_email,
        },
        'to': [{'email': recipient}],
        'subject': subject,
        'htmlContent': f'<p>{escape(text)}</p>',
    }).encode('utf-8')
    request = urllib.request.Request(
        BREVO_EMAILS_URL,
        data=body,
        headers={
            'api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )

    try:
        opener = urllib.request.build_opener(_NoRedirectHandler)
        with opener.open(request, timeout=timeout) as response:
            status_code = response.status
    except urllib.error.HTTPError as exc:
        logger.warning(
            'Brevo email delivery failed (HTTP %d).',
            exc.code,
        )
        raise EmailProviderError(
            f'Email provider rejected the message (HTTP {exc.code}).',
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            'Brevo email request failed (%s).',
            type(exc).__name__,
        )
        raise EmailProviderError('Email provider request failed.') from exc

    if not 200 <= status_code < 300:
        logger.warning(
            'Brevo email delivery failed (HTTP %d).',
            status_code,
        )
        raise EmailProviderError(
            f'Email provider returned HTTP {status_code}.',
        )
