from django.test import TestCase
from django.urls import reverse

from .forms import UserCreationForm
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


class UserCredentialUniquenessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='nessa@example.com',
            username='nessa',
            password='senha123',
        )

    def test_manager_rejeita_username_duplicado(self):
        tenants_before = Tenant.objects.count()

        with self.assertRaisesMessage(
            ValueError,
            'Já existe um usuário com este username.',
        ):
            User.objects.create_user(
                email='outro@example.com',
                username='NESSA',
                password='senha123',
            )

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Tenant.objects.count(), tenants_before)

    def test_manager_rejeita_email_duplicado(self):
        tenants_before = Tenant.objects.count()

        with self.assertRaisesMessage(
            ValueError,
            'Já existe um usuário com este email.',
        ):
            User.objects.create_user(
                email='NESSA@example.com',
                username='outro',
                password='senha123',
            )

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Tenant.objects.count(), tenants_before)

    def test_formulario_informa_username_e_email_duplicados(self):
        form = UserCreationForm(data={
            'username': 'NESSA',
            'email': 'NESSA@example.com',
            'password1': 'senha123',
            'password2': 'senha123',
        })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['username'], ['Este username já está em uso.'])
        self.assertEqual(form.errors['email'], ['Este email já está em uso.'])
