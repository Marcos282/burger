import json
from html.parser import HTMLParser
from xml.etree import ElementTree

from django.test import TestCase, RequestFactory
from django.template.loader import render_to_string
from django.contrib.auth.models import AnonymousUser
from core.views import home_view
from core.discovery import sitemap, robots
from core.institutional import ORIGIN, TITLE
from tenants.models import Tenant, TenantSettings, Configuracao


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.canonical = []
        self.schemas = []
        self.json_buffer = None
        self.h1_count = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.meta.setdefault(attrs.get('property', attrs.get('name')), []).append(attrs.get('content'))
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical.append(attrs['href'])
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.json_buffer = ''
        if tag == 'h1':
            self.h1_count += 1
    def handle_data(self, data):
        if self.json_buffer is not None:
            self.json_buffer += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.json_buffer is not None:
            self.schemas.append(json.loads(self.json_buffer))
            self.json_buffer = None


class InstitutionalSEOTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Marca exclusiva do tenant', subdomain='alpha')
        TenantSettings.objects.create(tenant=self.tenant, foto_perfil='fotoperfil/tenant.jpg', tag_google_analytics='G-TENANT999')
        config = Configuracao.load()
        config.logo = 'logos/viazap.png'
        config.save()

    def request(self, host='www.viazap.net', path='/'):
        request = RequestFactory().get(path, HTTP_HOST=host)
        request.tenant = None
        request.user = AnonymousUser()
        request.session = {}
        return request

    def test_home_seo_on_both_institutional_hosts(self):
        for host in ['www.viazap.net', 'viazap.net']:
            with self.subTest(host=host):
                response = home_view(self.request(host, '/?utm_source=teste'))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                parsed = HeadParser()
                parsed.feed(html)
                self.assertIn('<title>' + TITLE + '</title>', html)
                self.assertEqual(parsed.canonical, [ORIGIN])
                self.assertEqual(parsed.h1_count, 1)
                for name in ['description', 'og:title', 'og:description', 'og:image', 'og:url', 'twitter:card']:
                    self.assertEqual(len(parsed.meta[name]), 1)
                self.assertEqual(parsed.meta['og:title'], [TITLE])
                self.assertEqual(parsed.meta['og:url'], [ORIGIN])
                self.assertEqual(parsed.meta['og:type'], ['website'])
                self.assertEqual(parsed.meta['twitter:card'], ['summary_large_image'])
                self.assertTrue(parsed.meta['og:image'][0].startswith('https://www.viazap.net/'))
                self.assertEqual(parsed.meta['og:image'], parsed.meta['twitter:image'])
                types = {value['@type']: value for value in parsed.schemas}
                self.assertEqual(set(types), {'Organization', 'WebSite'})
                self.assertEqual(types['Organization']['logo'], 'https://www.viazap.net/media/logos/viazap.png')
                self.assertEqual(types['WebSite']['url'], ORIGIN)
                metadata = json.dumps([parsed.meta, parsed.schemas])
                self.assertNotIn('tenant.jpg', metadata)
                self.assertNotIn('Marca exclusiva', metadata)
                self.assertNotIn('G-TENANT999', html)
                self.assertEqual(html.count('googletagmanager.com/gtag/js?'), 1)
                self.assertEqual(html.count("gtag('config', 'G-C4BWMDXFPQ')"), 1)

    def test_tenant_home_keeps_redirect_to_its_store(self):
        request = self.request('alpha.viazap.net')
        request.tenant = self.tenant
        response = home_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/loja/')

    def test_institutional_sitemap_only_lists_existing_public_home(self):
        response = sitemap(self.request())
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.content)
        urls = [node.text for node in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(urls, [ORIGIN])
        response = robots(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sitemap: https://www.viazap.net/sitemap.xml')
        self.assertContains(response, 'Disallow: /painel/')
        self.assertContains(response, 'Disallow: /admin/')
        self.assertNotContains(response, 'Disallow: /static/')

    def test_base_defaults_derive_canonical_from_institutional_path(self):
        request = self.request(path='/futura-pagina/?query=ignored')
        html = render_to_string('institucional/base.html', {}, request)
        self.assertIn('href="https://www.viazap.net/futura-pagina/"', html)
        self.assertIn('content="https://www.viazap.net/futura-pagina/"', html)
