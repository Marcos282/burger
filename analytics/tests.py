from types import SimpleNamespace
from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, SimpleTestCase

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
