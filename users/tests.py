from django.test import SimpleTestCase, override_settings


class OTPDisabledEndpointTests(SimpleTestCase):
    @override_settings(OTP_ENABLED=False)
    def test_otp_status_reports_disabled(self):
        response = self.client.get('/api/auth/otp-status/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'otp_enabled': False})

    @override_settings(OTP_ENABLED=False)
    def test_otp_and_password_reset_endpoints_are_unavailable(self):
        for path in (
            '/api/auth/verify-otp/',
            '/api/auth/resend-otp/',
            '/api/auth/forgot-password/',
            '/api/auth/reset-password/',
        ):
            with self.subTest(path=path):
                response = self.client.post(path, data='{}', content_type='application/json')
                self.assertEqual(response.status_code, 503)
                self.assertIn('temporarily unavailable', response.json()['detail'])

    def test_registration_can_omit_optional_university(self):
        from .serializers import RegisterSerializer

        self.assertFalse(RegisterSerializer().fields['university_id'].required)
