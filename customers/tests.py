from django.test import TestCase
from django.urls import reverse

from .models import User
from tenants.models import Tenant


class TenantSessionContextTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Loja Teste', subdomain='loja-teste')
        self.user = User.objects.create_user(
            email='admin@loja-teste.com',
            username='loja-teste',
            password='senha123',
            tenant=self.tenant,
        )

    def test_login_persists_tenant_id_in_session(self):
        response = self.client.post(
            reverse('login'),
            {'email': 'admin@loja-teste.com', 'password': 'senha123'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('tenant_id'), self.tenant.id)

    def test_context_processor_loads_tenant_from_session(self):
        session = self.client.session
        session['tenant_id'] = self.tenant.id
        session.save()

        response = self.client.get(reverse('login'))

        self.assertIn('tenant', response.context)
        self.assertEqual(response.context['tenant'].id, self.tenant.id)
