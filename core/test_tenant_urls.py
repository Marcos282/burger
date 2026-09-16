from django.test import TestCase, RequestFactory
from tenants.models import Configuracao, Tenant
from core.utils import get_tenant_url


class TenantURLTests(TestCase):
    def setUp(self):
        config = Configuracao.load()
        config.dominio = 'viazap.net'
        config.save()
        self.tenant = Tenant.objects.create(name='Marley', subdomain='marley')

    def test_local_links_stay_local_with_public_domain_configured(self):
        for host in ['localhost:8000', '127.0.0.1:8000', 'marley.localhost:8000']:
            with self.subTest(host=host):
                request = RequestFactory().get('/', HTTP_HOST=host)
                request.tenant = self.tenant
                self.assertEqual(get_tenant_url(request, '/loja/'),
                                 'http://marley.localhost:8000/loja/')

    def test_public_links_use_configured_domain(self):
        request = RequestFactory().get('/', HTTP_HOST='viazap.net', secure=True)
        request.tenant = self.tenant
        self.assertEqual(get_tenant_url(request, '/loja/'),
                         'https://marley.viazap.net/loja/')
