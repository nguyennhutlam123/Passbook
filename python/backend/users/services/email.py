import logging
import smtplib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail as django_send_mail


logger = logging.getLogger(__name__)


class EmailProviderError(Exception):
    pass


def send_email(*, recipient, subject, text):
    try:
        sent_count = django_send_mail(
            subject,
            text,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except (ImproperlyConfigured, OSError, smtplib.SMTPException) as exc:
        logger.warning('OTP email sending failed (%s).', type(exc).__name__)
        raise EmailProviderError('Email delivery failed.') from exc

    if sent_count != 1:
        logger.warning('OTP email sending failed (message_count=%s).', sent_count)
        raise EmailProviderError('Email delivery failed.')
