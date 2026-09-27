import json
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase, RequestFactory

from analytics.commerce import cart_data, order_data
from core.discovery import sitemap, robots
from core.product_metadata import product_metadata
from core.views import detalhe, add_to_cart, checkout_sucesso
from customers.contexto import configuracao_context
from menu.models import Category, Produto
from orders.models import Ordem, OrdemItem
from tenants.models import Tenant, TenantSettings, Configuracao


class Session(dict):
    modified = False


class ProductDiscoveryTests(TestCase):
    def setUp(self):
        self.a = Tenant.objects.create(name='Loja A', subdomain='alpha')
        self.b = Tenant.objects.create(name='Loja B', subdomain='beta')
        self.config = TenantSettings.objects.create(tenant=self.a, tag_google_analytics='G-AAAAAAA')
        self.other_config = TenantSettings.objects.create(tenant=self.b, tag_google_analytics='G-BBBBBBB')
        self.category = Category.objects.create(tenant=self.a, name='Calçados', status=True, exibir=True)
        self.product = Produto.objects.create(tenant=self.a, category=self.category, nome='Sandália & "Luxo"',
                                              price=199.90, description='<p>Confortável</p>', image='produtos/foto.jpg')
        self.foreign = Produto.objects.create(tenant=self.b, nome='Produto B', price=10)
        self.hidden = Produto.objects.create(tenant=self.a, nome='Oculto', price=10, exibir=False)
        self.inactive = Produto.objects.create(tenant=self.a, nome='Inativo', price=10, status=False)
        self.global_config = Configuracao.load()

    def request(self, tenant=None, path='/loja/', post=None):
        factory = RequestFactory()
        request = factory.post(path, post) if post is not None else factory.get(path)
        request.META['HTTP_HOST'] = f'{(tenant or self.a).subdomain}.localhost'
        request.tenant = tenant or self.a
        request.session = Session()
        request.user = AnonymousUser()
        return request

    def test_canonical_schema_and_share_links_use_same_tenant(self):
        request = self.request(path='/loja/datail/1?tracking=foreign')
        response = detalhe(request, self.product.pk)
        html = response.content.decode()
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        canonical = f'https://alpha.localhost/loja/datail/{self.product.pk}'
        self.assertIn(f'<link rel="canonical" href="{canonical}">', html)
        self.assertEqual(schema['offers']['url'], canonical)
        self.assertEqual(schema['offers']['price'], '199.90')
        self.assertEqual(schema['offers']['priceCurrency'], 'BRL')
        self.assertEqual(schema['offers']['seller']['name'], 'Loja A')
        self.assertEqual(schema['category'], 'Calçados')
        self.assertEqual(schema['sku'], self.product.referencia)
        self.assertNotIn('aggregateRating', schema)
        self.assertContains(response, 'G-AAAAAAA')
        self.assertNotContains(response, 'G-BBBBBBB')
        data = product_metadata(request, self.product, [], self.config, self.global_config)
        self.assertEqual(parse_qs(urlsplit(data['facebook_url']).query), {'u': [canonical]})
        self.assertEqual(parse_qs(urlsplit(data['x_url']).query)['url'], [canonical])
        self.assertEqual(data['analytics']['tenant_id'], self.a.pk)
        self.assertEqual(configuracao_context(self.request(self.b))['ga_measurement_id'], 'G-BBBBBBB')

    def test_metadata_rejects_foreign_product_or_settings(self):
        for product, config in [(self.foreign, self.config), (self.product, self.other_config)]:
            with self.assertRaises(PermissionDenied):
                product_metadata(self.request(), product, [], config, self.global_config)
        self.product.category = Category.objects.create(tenant=self.b, name='Categoria secreta')
        data = product_metadata(self.request(), self.product, [], self.config, self.global_config)
        self.assertEqual(data['category'], '')
        self.assertNotIn('Categoria secreta', data['schema_json'])

    def test_json_ld_cannot_close_script(self):
        self.product.referencia = '</script><script>alert("x")</script>'
        self.product.nome = 'Ação & "aspas"'
        data = product_metadata(self.request(), self.product, [], self.config, self.global_config)
        self.assertNotIn('</script>', data['schema_json'])
        self.assertEqual(json.loads(data['schema_json'])['sku'], self.product.referencia)

    def test_sitemap_only_announces_public_products_and_categories_of_current_store(self):
        for tenant, product, excluded in [(self.a, self.product, self.foreign), (self.b, self.foreign, self.product)]:
            xml = sitemap(self.request(tenant)).content
            tree = ElementTree.fromstring(xml)
            urls = [node.text for node in tree.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
            root = f'https://{tenant.subdomain}.localhost'
            self.assertIn(root + '/loja/', urls)
            self.assertIn(root + f'/loja/datail/{product.pk}', urls)
            for missing in [excluded, self.hidden, self.inactive]:
                self.assertNotIn(root + f'/loja/datail/{missing.pk}', urls)
            self.assertTrue(all(url.startswith(root + '/') for url in urls))
            if tenant == self.a:
                self.assertIn(root + f'/loja/?categoria_id={self.category.pk}', urls)
        self.product.delete()
        xml = sitemap(self.request()).content.decode()
        self.assertNotIn('categoria_id', xml)

    def test_hidden_inactive_and_foreign_product_are_not_public(self):
        for product in (self.hidden, self.inactive, self.foreign):
            with self.assertRaises(Http404):
                detalhe(self.request(), product.pk)
        data = product_metadata(self.request(), self.inactive, [], self.config, self.global_config)
        self.assertEqual(data['availability'], 'OutOfStock')

    def test_robots_exposes_own_sitemap_and_keeps_assets_crawlable(self):
        text = robots(self.request()).content.decode()
        self.assertIn('Disallow: /painel/', text)
        self.assertIn('Disallow: /admin/', text)
        self.assertIn('Sitemap: https://alpha.localhost/sitemap.xml', text)
        self.assertNotIn('Disallow: /media/', text)
        self.assertNotIn('Disallow: /static/', text)

    def test_cart_analytics_only_after_valid_tenant_product_added(self):
        request = self.request(post={'produto_id': self.product.pk, 'quantidade': 2})
        data = json.loads(add_to_cart(request).content)['analytics']
        self.assertEqual(data['value'], 399.8)
        self.assertEqual(data['items'][0]['quantity'], 2)
        self.assertEqual(data['tenant_id'], self.a.pk)
        request = self.request(post={'produto_id': self.foreign.pk, 'quantidade': 1})
        with self.assertRaises(Http404):
            add_to_cart(request)
        self.assertNotIn('cart', request.session)
        request.session['cart'] = {str(self.product.pk): 2, str(self.foreign.pk): 7}
        self.assertEqual(len(cart_data(request)['items']), 1)

    def test_purchase_uses_order_records_and_no_personal_session_data(self):
        order = Ordem.objects.create(tenant=self.a, tx_entrega=5)
        OrdemItem.objects.create(tenant=self.a, ordem=order, produto=self.product, quantidade=2, preco_unitario=150)
        data = order_data(order)
        self.assertEqual(data['value'], 300)
        self.assertEqual(data['shipping'], 5)
        self.assertEqual(data['transaction_id'], f'{self.a.pk}-{order.pk}')
        request = self.request()
        request.session['last_pedido_info'] = {'pedido_id': order.pk, 'nome': 'Nome privado', 'whatsapp': '9999999'}
        html = checkout_sucesso(request).content.decode()
        payload = re.search(r'<script id="purchaseAnalyticsData" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn('Nome privado', payload)
        self.assertNotIn('9999999', payload)
        self.assertEqual(json.loads(payload)['transaction_id'], data['transaction_id'])
        request.tenant = self.b
        self.assertEqual(checkout_sucesso(request).status_code, 404)
