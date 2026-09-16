from unittest.mock import patch
from smtplib import SMTPException

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .email_confirmation import confirmation_token
from .models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_CONFIRMATION_BASE_URL='https://viazap.net')
class EmailConfirmationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.data = {'username': 'confirm-shop', 'email': 'confirm@example.com',
                     'password1': 'Strong!8923Forest', 'password2': 'Strong!8923Forest'}

    def register(self):
        response = self.client.post(reverse('register'), self.data)
        self.assertRedirects(response, reverse('email_confirmation_request'))
        return User.objects.get(email=self.data['email'])

    def test_registration_email_and_activation_then_login(self):
        user = self.register()
        self.assertFalse(user.is_active)
        self.assertTrue(user.email_confirmation_pending)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://viazap.net/confirmar-email/', mail.outbox[0].body)
        login_data = {'email': user.email, 'password': self.data['password1']}
        response = self.client.post(reverse('login'), login_data)
        self.assertContains(response, 'Confirme seu e-mail antes de entrar')
        self.assertNotIn('_auth_user_id', self.client.session)
        url = reverse('email_confirm', args=[confirmation_token(user)])
        self.assertContains(self.client.get(url), 'Confirmar meu e-mail')
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertRedirects(self.client.post(url), reverse('login'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(user.email_confirmation_pending)
        self.assertIsNotNone(user.email_verified_at)
        self.assertContains(self.client.post(url), 'Link inválido ou expirado')
        response = self.client.post(reverse('login'), login_data)
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_expired_tampered_and_changed_email_tokens_do_not_activate(self):
        user = self.register()
        with patch('django.core.signing.time.time', return_value=1000):
            expired = confirmation_token(user)
        valid = confirmation_token(user)
        for token in [expired, valid + 'invalid']:
            self.assertContains(self.client.post(reverse('email_confirm', args=[token])),
                                'Link inválido ou expirado')
        user.email = 'changed@example.com'
        user.save()
        self.client.post(reverse('email_confirm', args=[valid]))
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_resend_throttles_and_unknown_email_has_same_response(self):
        user = self.register()
        url = reverse('email_confirmation_request')
        self.client.post(url, {'email': user.email})
        self.assertEqual(len(mail.outbox), 1)
        cache.clear()
        response = self.client.post(url, {'email': user.email})
        self.assertEqual(len(mail.outbox), 2)
        unknown = self.client.post(url, {'email': 'unknown@example.com'})
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(response.context['submitted'])
        self.assertTrue(unknown.context['submitted'])

    def test_existing_accounts_and_admin_disabled_users_stay_unchanged(self):
        existing = User.objects.create_user(email='existing@example.com', username='existing',
                                             password='Strong!123Forest')
        self.assertTrue(existing.is_active)
        existing.is_active = False
        existing.save()
        url = reverse('email_confirm', args=[confirmation_token(existing)])
        self.assertContains(self.client.post(url), 'Link inválido ou expirado')
        self.client.post(reverse('email_confirmation_request'), {'email': existing.email})
        self.assertEqual(len(mail.outbox), 0)
        existing.refresh_from_db()
        self.assertFalse(existing.is_active)

    def test_smtp_failure_keeps_pending_account_for_retry(self):
        with patch('customers.email_confirmation.send_mail', side_effect=SMTPException('failure')):
            response = self.client.post(reverse('register'), self.data, follow=True)
        self.assertContains(response, 'não conseguimos enviar')
        user = User.objects.get(email=self.data['email'])
        self.assertFalse(user.is_active)
        self.client.post(reverse('email_confirmation_request'), {'email': user.email})
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_does_not_activate_pending_account(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        user = self.register()
        url = reverse('password_reset_confirm', args=[
            urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)])
        self.client.post(url, {'password1': 'Another!1289Forest', 'password2': 'Another!1289Forest'})
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(user.email_confirmation_pending)
