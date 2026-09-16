from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core import mail
from .models import User
from tenants.models import Tenant


@override_settings(GOOGLE_CLIENT_ID='test.apps.googleusercontent.com',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GoogleAuthTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client.get(reverse('login'))
        self.claims = {'sub': 'google-subject-123', 'email': 'newuser@gmail.com',
                       'email_verified': True, 'nonce': self.client.session['google_nonce']}
        self.data = {'credential': 'signed-token', 'mode': 'register', 'username': 'google-shop'}

    def post(self, claims=None, data=None):
        with patch('customers.google_auth.id_token.verify_oauth2_token',
                   return_value=claims or self.claims) as verify:
            response = self.client.post(reverse('google_login'), data or self.data)
        verify.assert_called_once()
        self.assertEqual(verify.call_args.args[2], 'test.apps.googleusercontent.com')
        return response

    def test_google_registration_creates_verified_user_and_session(self):
        self.assertEqual(self.post().status_code, 200)
        user = User.objects.get(google_sub=self.claims['sub'])
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.email_verified_at)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self.client.session['tenant_id'], user.tenant_id)
        self.assertNotIn('google_nonce', self.client.session)

    def test_invalid_signature_and_nonce_rejected(self):
        with patch('customers.google_auth.id_token.verify_oauth2_token', side_effect=ValueError):
            self.assertEqual(self.client.post(reverse('google_login'), self.data).status_code, 401)
        self.assertEqual(self.post({**self.claims, 'nonce': 'wrong'}).status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_existing_account_requires_password_for_linking(self):
        user = User.objects.create_user(email=self.claims['email'], username='existing',
                                        password='Forest!12389')
        self.assertTrue(self.post().json()['requires_password'])
        self.assertEqual(self.post(data={**self.data, 'password': 'wrong'}).status_code, 403)
        user.refresh_from_db()
        self.assertIsNone(user.google_sub)
        self.assertEqual(self.post(data={**self.data, 'password': 'Forest!12389'}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.google_sub, self.claims['sub'])

    def test_existing_google_identity_is_found_by_subject_not_email(self):
        user = User.objects.create_user(email='old@gmail.com', username='existing',
                                        google_sub=self.claims['sub'])
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertEqual(User.objects.count(), 1)

    def test_disabled_user_cannot_login(self):
        User.objects.create_user(email=self.claims['email'], username='disabled',
                                 google_sub=self.claims['sub'], is_active=False)
        self.assertEqual(self.post().status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_external_email_requires_confirmation(self):
        self.assertEqual(self.post({**self.claims, 'email': 'new@example.com'}).status_code, 200)
        user = User.objects.get(google_sub=self.claims['sub'])
        self.assertFalse(user.is_active)
        self.assertTrue(user.email_confirmation_pending)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(len(mail.outbox), 1)

    def test_occupied_subdomain_is_not_reused(self):
        tenant = Tenant.objects.create(name='Existing', subdomain='google-shop')
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(User.objects.filter(tenant=tenant).exists())

    def test_login_does_not_create_account_without_registration(self):
        self.assertEqual(self.post(data={**self.data, 'mode': 'login'}).status_code, 409)
        self.assertFalse(User.objects.exists())

    def test_logout_disables_automatic_login(self):
        self.post()
        from .views_auth import logout_view
        from django.test import RequestFactory
        request = RequestFactory().get('/logout/')
        request.session = self.client.session
        request.user = User.objects.get(google_sub=self.claims['sub'])
        logout_view(request)
        self.assertTrue(request.session['google_signed_out'])

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('google_login'), self.data).status_code, 403)

    def test_unverified_google_email_rejected(self):
        self.assertEqual(self.post({**self.claims, 'email_verified': False}).status_code, 400)
        self.assertFalse(User.objects.exists())

    @override_settings(GOOGLE_CLIENT_ID='')
    def test_disabled_when_not_configured(self):
        self.assertEqual(self.client.post(reverse('google_login'), self.data).status_code, 503)
        self.assertNotContains(self.client.get(reverse('login')), 'accounts.google.com/gsi/client')
