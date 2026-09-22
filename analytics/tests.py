from types import SimpleNamespace
from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from .views import relatorio_acessos


class RelatorioAcessosTests(SimpleTestCase):
    def request_for(self, host_tenant_id=None, user_tenant_id=7):
        request = RequestFactory().get('/painel/relatorios/acessos/')
        request.user = SimpleNamespace(is_authenticated=True, tenant_id=user_tenant_id)
        request.tenant = SimpleNamespace(id=host_tenant_id) if host_tenant_id else None
        return request

    def test_main_domain_and_own_subdomain_filter_by_user_tenant(self):
        for host_tenant_id in (None, 7):
            with self.subTest(host_tenant_id=host_tenant_id):
                with patch('analytics.views.AcessoSite.objects.filter') as query, patch(
                    'analytics.views.render', return_value=HttpResponse('ok')
                ):
                    response = relatorio_acessos(self.request_for(host_tenant_id))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(query.call_args.kwargs['tenant_id'], 7)

    def test_other_tenant_and_user_without_tenant_are_rejected(self):
        for host_tenant_id, user_tenant_id in ((8, 7), (None, None)):
            with self.subTest(host_tenant_id=host_tenant_id, user_tenant_id=user_tenant_id):
                with self.assertRaises(Http404):
                    relatorio_acessos(self.request_for(host_tenant_id, user_tenant_id))

    def test_period_links_keep_report_path_despite_base_tag(self):
        from django.template.loader import render_to_string
        from django.urls import reverse
        html = render_to_string('painel/relatorio_acessos.html', {'period_days': 30})
        for days in (7, 30, 90):
            self.assertIn(f'href="{reverse("relatorio_acessos")}?dias={days}"', html)

    def test_period_parameter_controls_date_filter(self):
        from datetime import timedelta
        from django.utils import timezone
        for days in (7, 30, 90):
            with self.subTest(days=days):
                request = self.request_for()
                request.GET = {'dias': str(days)}
                with patch('analytics.views.AcessoSite.objects.filter') as query, patch(
                    'analytics.views.render', return_value=HttpResponse('ok')
                ) as render:
                    relatorio_acessos(request)
                self.assertEqual(query.call_args.kwargs['data_hora__date__gte'], timezone.localdate() - timedelta(days=days - 1))
                self.assertEqual(render.call_args.args[2]['period_days'], days)


class GoogleStatsTests(TestCase):
    def setUp(self):
        from customers.models import User
        from tenants.models import Tenant, TenantSettings

        self.tenant = Tenant.objects.create(name='Stats', subdomain='stats-loja')
        self.settings = TenantSettings.objects.create(tenant=self.tenant, tag_google_analytics='G-TESTE123')
        self.user = User.objects.create_user(
            email='stats@example.com', username='stats-loja', password='senha', tenant=self.tenant,
        )
        self.client.force_login(self.user)

    def unlock(self):
        return self.client.post('/stats/', {'stats_pin': '1234'}, HTTP_HOST='localhost')

    def test_requests_four_digit_pin(self):
        response = self.client.get('/stats/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Digite o PIN de quatro dígitos')
        denied = self.client.post('/stats/', {'stats_pin': '9999'}, HTTP_HOST='localhost')
        self.assertEqual(denied.status_code, 403)
        self.assertContains(denied, 'PIN incorreto', status_code=403)
        accepted = self.unlock()
        self.assertRedirects(accepted, '/stats/', fetch_redirect_response=False)

    def test_requires_numeric_property_id(self):
        self.unlock()
        response = self.client.get('/stats/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cadastre o ID numérico da propriedade GA4')

    @patch('analytics.views.get_google_analytics_report')
    def test_displays_report_for_authenticated_tenant(self, report):
        from analytics.google_analytics import GoogleAnalyticsReport

        self.settings.google_analytics_property_id = '123456789'
        self.settings.save(update_fields=['google_analytics_property_id'])
        self.unlock()
        report.return_value = GoogleAnalyticsReport(
            totals={'activeUsers': 12, 'sessions': 18, 'screenPageViews': 30, 'eventCount': 50},
            daily=[], pages=[],
        )
        response = self.client.get('/stats/?dias=7', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuários ativos')
        report.assert_called_once_with(tenant_id=self.tenant.pk, property_id='123456789', days=7)

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        response = self.client.get('/stats/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 302)
