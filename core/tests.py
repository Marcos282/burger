from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase, RequestFactory
from django.utils import timezone

from .ai_chat import (
    add_chat_message,
    chat_session_belongs_to_tenant,
    fallback_reply,
    ensure_chat_session_state,
    get_chat_messages,
    list_active_chat_sessions,
    set_chat_session_mode,
)
from .utils import calcular_dias_restantes, gravar_os_dias, normalizar_datetime


class ExpiracaoTests(SimpleTestCase):
    def test_calcula_dias_restantes_com_data_sem_timezone(self):
        agora = datetime(2026, 8, 23, 18, 0)
        data_expiracao = agora + timedelta(days=5)

        self.assertEqual(calcular_dias_restantes(data_expiracao, agora), 5)

    def test_preserva_data_com_timezone(self):
        valor = timezone.now()

        self.assertIs(normalizar_datetime(valor), valor)

    def test_gravar_os_dias_soma_saldo_restante_e_credito(self):
        agora = timezone.now()

        nova_data = gravar_os_dias(5, agora, 30)

        self.assertEqual(nova_data, agora + timedelta(days=35))
        self.assertTrue(timezone.is_aware(nova_data))

    def test_gravar_os_dias_inicia_credito_quando_nao_ha_saldo(self):
        agora = timezone.now()

        nova_data = gravar_os_dias(-1, agora, 30)

        self.assertEqual(nova_data, agora + timedelta(days=30))


class AIBotFallbackTests(SimpleTestCase):
    def setUp(self):
        self.context = {
            'store': {
                'nome': 'Burger House',
                'descricao': 'Hamburgueres artesanais',
                'segmento': 'delivery',
                'whatsapp': '(47) 99999-0000',
                'endereco': 'Rua das Flores, 123, Centro, Itajaí, SC',
                'taxa_entrega': 'R$ 8,00',
                'pedido_minimo': 'R$ 25,00',
                'formas_pagamento': ['PIX', 'cartao de credito', 'dinheiro'],
                'aberto': True,
            },
            'cliente': {'nome': 'Maria', 'telefone': '47999990000', 'cidade': 'Itajaí', 'pedidos_pendentes': 0},
            'categorias': ['Lanches', 'Bebidas'],
            'produtos': [
                {'nome': 'X-Burger', 'categoria': 'Lanches', 'descricao': 'Hamburguer com queijo', 'preco': 'R$ 29,90'},
                {'nome': 'Refrigerante', 'categoria': 'Bebidas', 'descricao': 'Lata 350ml', 'preco': 'R$ 8,00'},
            ],
        }

    def test_responde_endereco_e_pagamento_sem_ia(self):
        endereco = fallback_reply('Qual é o endereço?', self.context)
        pagamento = fallback_reply('Quais são as formas de pagamento?', self.context)
        ent = fallback_reply('Qual a taxa de entrega?', self.context)
        whatsapp = fallback_reply('Qual é o WhatsApp?', self.context)

        self.assertIn('Rua das Flores', endereco)
        self.assertIn('PIX', pagamento)
        self.assertIn('R$ 8,00', ent)
        self.assertIn('(47) 99999-0000', whatsapp)

    def test_responde_pelo_nome_do_produto_no_fallback(self):
        resposta = fallback_reply('Quero o X-Burger', self.context)

        self.assertIn('X-Burger', resposta)
        self.assertIn('R$ 29,90', resposta)


class WhatsAppHandoffTests(SimpleTestCase):
    def test_missing_address_refers_to_store_contact(self):
        reply = fallback_reply('Qual o endereço?', {'store': {'nome': 'Seu nome completo', 'endereco': ' ', 'whatsapp': '47999991234'}})
        self.assertIn('endereço da loja ainda não está cadastrado', reply)
        self.assertIn('47999991234', reply)
        self.assertNotIn('Seu nome completo', reply)

    def test_missing_address_and_phone(self):
        reply = fallback_reply('Onde fica?', {'store': {}})
        self.assertIn('confirme com um atendente', reply)
        self.assertNotIn('WhatsApp:', reply)

    def test_unknown_question_uses_store_whatsapp(self):
        from .ai_chat import fallback_reply
        reply = fallback_reply('Uma dúvida sem informação disponível', {'store': {'whatsapp': '47999991234'}})
        self.assertIn('47999991234', reply)
        self.assertIn('atendente', reply)

    def test_missing_whatsapp_is_not_invented(self):
        from .ai_chat import whatsapp_handoff_reply
        self.assertIn('não está cadastrado', whatsapp_handoff_reply({'store': {}}))

    def test_empty_ai_response_returns_whatsapp(self):
        from unittest.mock import patch, Mock
        from django.test import override_settings
        from .ai_chat import ask_ai_assistant
        response = Mock()
        response.json.return_value = {'choices': [{'message': {'content': ' '}}]}
        with override_settings(AI_CHAT_API_KEY='test'), patch('core.ai_chat.requests.post', return_value=response):
            reply, enabled = ask_ai_assistant('Dúvida', {'store': {'whatsapp': '47999991234'}})
        self.assertFalse(enabled)
        self.assertIn('47999991234', reply)


class ChatSessionTests(TestCase):
    def setUp(self):
        from tenants.models import Tenant
        from customers.models import User
        self.tenant = Tenant.objects.create(name='Loja A', subdomain='chat-a')
        self.other = Tenant.objects.create(name='Loja B', subdomain='chat-b')
        self.operator = User.objects.create(tenant=self.tenant, username='chat-a', email='chat-a@example.com', is_staff=True)

    def test_messages_and_handoff_survive_module_reload(self):
        import importlib
        from . import ai_chat
        from .models import ChatMessage, ChatSession
        first = add_chat_message('abc', 'customer', 'Olá', tenant_id=self.tenant.pk)
        second = add_chat_message('abc', 'bot', 'Bem-vindo', tenant_id=self.tenant.pk)
        set_chat_session_mode('abc', 'operator', self.operator.pk, tenant_id=self.tenant.pk)
        importlib.reload(ai_chat)
        self.assertEqual(ChatSession.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 2)
        state = ensure_chat_session_state('abc', tenant_id=self.tenant.pk)
        self.assertEqual(state['mode'], 'operator')
        self.assertEqual(state['assumido_por'], self.operator.pk)
        self.assertEqual(get_chat_messages('abc', first['id'], tenant_id=self.tenant.pk), [second])
        self.assertEqual(list_active_chat_sessions(self.tenant.pk)[0]['message_count'], 2)
        set_chat_session_mode('abc', 'bot', tenant_id=self.tenant.pk)
        self.assertIsNone(ensure_chat_session_state('abc', tenant_id=self.tenant.pk)['assumido_por'])

    def test_same_session_key_is_isolated_between_tenants(self):
        a = add_chat_message('same', 'customer', 'Loja A', tenant_id=self.tenant.pk)
        b = add_chat_message('same', 'customer', 'Loja B', tenant_id=self.other.pk)
        self.assertEqual(get_chat_messages('same', tenant_id=self.tenant.pk), [a])
        self.assertEqual(get_chat_messages('same', tenant_id=self.other.pk), [b])
        set_chat_session_mode('same', 'operator', self.operator.pk, tenant_id=self.tenant.pk)
        self.assertEqual(ensure_chat_session_state('same', tenant_id=self.other.pk)['mode'], 'bot')
        self.assertEqual(list_active_chat_sessions(self.other.pk)[0]['message_count'], 1)

    def test_missing_tenant_and_foreign_operator_are_rejected(self):
        with self.assertRaises(ValueError):
            ensure_chat_session_state('missing')
        ensure_chat_session_state('foreign', tenant_id=self.other.pk)
        with self.assertRaises(ValueError):
            set_chat_session_mode('foreign', 'operator', self.operator.pk, tenant_id=self.other.pk)
        self.assertFalse(chat_session_belongs_to_tenant('foreign', self.tenant.pk))
        self.assertEqual(get_chat_messages('foreign', tenant_id=self.tenant.pk), [])

    def test_panel_cannot_read_or_change_another_tenants_chat(self):
        from customers.views_auth import painel_bot_mensagens, painel_bot_enviar, painel_bot_alternar_sessao
        from .models import ChatMessage
        add_chat_message('private', 'customer', 'Segredo', tenant_id=self.other.pk)
        factory = RequestFactory()
        for view, request in [
            (painel_bot_mensagens, factory.get('/', {'session_id': 'private'})),
            (painel_bot_enviar, factory.post('/', {'session_id': 'private', 'message': 'Teste'})),
            (painel_bot_alternar_sessao, factory.post('/', {'session_id': 'private'})),
        ]:
            request.user = self.operator
            self.assertEqual(view(request).status_code, 404)
        self.assertEqual(ChatMessage.objects.count(), 1)

    def test_store_messages_are_saved_with_request_tenant(self):
        import json
        from unittest.mock import patch
        from .views import loja_ai_chat
        from .models import ChatMessage
        request = RequestFactory().post('/', data=json.dumps({'session_id': 'store', 'message': 'Olá'}), content_type='application/json')
        request.tenant = self.tenant
        ensure_chat_session_state('store', tenant_id=self.tenant.pk)
        from .models import ChatSession
        ChatSession.objects.filter(tenant=self.tenant, session_key='store').update(introduction_complete=True)
        with patch('core.views.build_store_context', return_value={}), patch('core.views.ask_ai_assistant', return_value=('Resposta de teste', True)):
            response = loja_ai_chat(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(ChatMessage.objects.filter(session__tenant=self.tenant).values_list('sender', flat=True)), ['customer', 'bot'])

    def test_introduction_collects_phone_once(self):
        from .ai_chat import chat_introduction
        from .models import ChatSession
        ensure_chat_session_state('intro', tenant_id=self.tenant.pk)
        self.assertIn('telefone com DDD', chat_introduction('intro', 'Oi', tenant_id=self.tenant.pk))
        self.assertEqual(chat_introduction('intro', '(47) 99999-1234', tenant_id=self.tenant.pk), 'Obrigado! Como posso ajudar você hoje?')
        self.assertEqual(ChatSession.objects.get(tenant=self.tenant, session_key='intro').customer_phone, '47999991234')
        self.assertIsNone(chat_introduction('intro', 'Qual o endereço?', tenant_id=self.tenant.pk))

    def test_greetings_follow_local_hour(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from .ai_chat import chat_greeting
        for hour, expected in [(8, 'Bom dia'), (12, 'Boa tarde'), (18, 'Boa noite')]:
            with patch('core.ai_chat.timezone.localtime', return_value=SimpleNamespace(hour=hour)):
                self.assertEqual(chat_greeting(), expected)
