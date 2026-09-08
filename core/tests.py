from datetime import datetime, timedelta

from django.test import SimpleTestCase
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


class ChatSessionTests(SimpleTestCase):
    def test_session_de_chat_pode_ser_assumida_individualmente(self):
        session_key = 'session-abc-1'
        state = ensure_chat_session_state(session_key)

        self.assertEqual(state['mode'], 'bot')
        self.assertIn(session_key, [entry['session_id'] for entry in list_active_chat_sessions()])

        set_chat_session_mode(session_key, 'operator', user_id=42)
        state = ensure_chat_session_state(session_key)

        self.assertEqual(state['mode'], 'operator')
        self.assertEqual(state['assumido_por'], 42)
        self.assertIn(session_key, [entry['session_id'] for entry in list_active_chat_sessions()])

        set_chat_session_mode(session_key, 'bot', user_id=None)
        state = ensure_chat_session_state(session_key)

        self.assertEqual(state['mode'], 'bot')
        self.assertIsNone(state['assumido_por'])

    def test_mensagens_da_sessao_sao_ordenadas_e_isoladas_por_tenant(self):
        session_key = 'session-tenant-1'
        ensure_chat_session_state(session_key, tenant_id=10)
        primeira = add_chat_message(session_key, 'customer', 'Olá', tenant_id=10)
        segunda = add_chat_message(session_key, 'operator', 'Olá! Como posso ajudar?', tenant_id=10)

        self.assertTrue(chat_session_belongs_to_tenant(session_key, 10))
        self.assertFalse(chat_session_belongs_to_tenant(session_key, 11))
        self.assertEqual(get_chat_messages(session_key, after_id=primeira['id']), [segunda])
        self.assertIn(session_key, [entry['session_id'] for entry in list_active_chat_sessions(tenant_id=10)])
        self.assertNotIn(session_key, [entry['session_id'] for entry in list_active_chat_sessions(tenant_id=11)])
