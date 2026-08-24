import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, SimpleTestCase

from pagamento.mercadopago_client import get_sdk
from pagamento.views import pagamento, webhook_log, webhook_mercadopago


class MercadoPagoTokenTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.configuracao = SimpleNamespace(
			SecrectKey='TEST-access-token',
			valor_mensalidade=Decimal('49.90'),
			dias_gratuitos=30,
		)

	@patch('pagamento.views.mercadopago.SDK')
	@patch('pagamento.views.Configuracao.load')
	@patch('pagamento.views.Pagamento.objects.create')
	def test_pagamento_usa_secrect_key(
		self,
		pagamento_create,
		configuracao_load,
		sdk_class,
	):
		configuracao_load.return_value = self.configuracao
		pagamento_registro = pagamento_create.return_value
		sdk = sdk_class.return_value
		sdk.preference.return_value.create.return_value = {
			'status': 201,
			'response': {
				'id': 'preference-id',
				'sandbox_init_point': 'https://sandbox.mercadopago.test/checkout',
			},
		}
		request = self.factory.post(
			'/painel/pagamento/',
			{'forma_pagamento': 'pix'},
			HTTP_HOST='localhost',
		)
		request.user = SimpleNamespace(
			is_authenticated=True,
			pk=1,
			email='cliente@example.com',
			data_expiracao=None,
			tenant=SimpleNamespace(pk=1),
		)
		SessionMiddleware(lambda current_request: None).process_request(request)
		MessageMiddleware(lambda current_request: None).process_request(request)

		response = pagamento(request)

		sdk_class.assert_called_once_with('TEST-access-token')
		preference_data = sdk.preference.return_value.create.call_args.args[0]
		self.assertTrue(preference_data['external_reference'].startswith('renovacao-1-'))
		self.assertEqual(
			pagamento_registro.mp_preference_id,
			'preference-id',
		)
		self.assertEqual(response.status_code, 302)
		self.assertEqual(
			response.url,
			'https://sandbox.mercadopago.test/checkout',
		)

	@patch('pagamento.mercadopago_client.mercadopago.SDK')
	@patch('pagamento.mercadopago_client.Configuracao.load')
	def test_get_sdk_usa_secrect_key(self, configuracao_load, sdk_class):
		configuracao_load.return_value = self.configuracao

		sdk = get_sdk()

		sdk_class.assert_called_once_with('TEST-access-token')
		self.assertIs(sdk, sdk_class.return_value)

	@patch('pagamento.views.validar_assinatura_webhook', return_value=True)
	@patch('pagamento.views.buscar_pagamento')
	@patch('pagamento.views.Pagamento.objects.filter')
	def test_webhook_persiste_json_do_pagamento(
		self,
		pagamento_filter,
		buscar_pagamento,
		validar_assinatura,
	):
		pagamento_registro = Mock()
		pagamento_filter.return_value.first.return_value = pagamento_registro
		buscar_pagamento.return_value = {
			'external_reference': 'renovacao-1-abc',
			'status': 'approved',
		}
		request = self.factory.post(
			'/painel/pagamento/webhook/mercadopago/',
			data=json.dumps({'type': 'payment', 'data': {'id': '123'}}),
			content_type='application/json',
			HTTP_X_REQUEST_ID='request-123',
		)

		response = webhook_mercadopago(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(pagamento_registro.mp_payment_id, '123')
		self.assertEqual(pagamento_registro.status, 'approved')
		self.assertEqual(
			pagamento_registro.resposta_bruta['webhook']['data']['id'],
			'123',
		)
		pagamento_registro.save.assert_called_once()
		validar_assinatura.assert_called_once_with(request, '123')

	@patch('pagamento.views.Pagamento.objects.filter')
	def test_webhook_log_retorna_apenas_log_do_usuario(self, pagamento_filter):
		pagamento_registro = SimpleNamespace(
			resposta_bruta={'webhook': {'type': 'payment'}},
			data_atualizacao=SimpleNamespace(
				isoformat=lambda: '2026-08-23T23:00:00-03:00'
			),
		)
		pagamento_filter.return_value.order_by.return_value.first.return_value = (
			pagamento_registro
		)
		request = self.factory.get('/painel/pagamento/webhook/log/')
		request.user = SimpleNamespace(is_authenticated=True, pk=1)

		response = webhook_log(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			json.loads(response.content)['webhook'],
			{'webhook': {'type': 'payment'}},
		)
		pagamento_filter.assert_called_once_with(
			user=request.user,
			resposta_bruta__isnull=False,
		)
