from django.test import TestCase
from django.urls import reverse
from tenants.models import Tenant
from .forms import UserCreationForm


class SubdomainAvailabilityTests(TestCase):
    def check_name(self, name):
        return self.client.get(reverse('subdomain_availability'), {'subdomain': name})

    def test_free_name_is_normalized(self):
        response = self.check_name('  Minha-Loja  ')
        self.assertTrue(response.json()['available'])
        self.assertEqual(response.json()['subdomain'], 'minha-loja')
        self.assertIn('no-store', response['Cache-Control'])

    def test_existing_tenant_without_user_is_unavailable(self):
        Tenant.objects.create(name='Loja', subdomain='ocupada')
        self.assertFalse(self.check_name('OCUPADA').json()['available'])
        form = UserCreationForm({'username': 'OCUPADA', 'email': 'new@example.com',
            'password1': 'Forest!9238Strong', 'password2': 'Forest!9238Strong'})
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_invalid_and_reserved_names_are_rejected(self):
        for name in ['', 'www', 'ADMIN', 'duas palavras', '-loja', 'loja-', 'a.b', 'á', 'a' * 51]:
            with self.subTest(name=name):
                self.assertFalse(self.check_name(name).json()['available'])
