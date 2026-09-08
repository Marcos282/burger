import logging
import re
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .models import ChatSession, ChatMessage

import requests
from django.conf import settings

from customers.models import Cliente
from menu.models import Category, Produto
from orders.models import Ordem
from tenants.models import TenantSettings

logger = logging.getLogger(__name__)
def _session_state(session):
    return {
        'session_id': session.session_key,
        'session_number': session.pk,
        'tenant_id': session.tenant_id,
        'mode': session.mode,
        'introduction_complete': session.introduction_complete or bool(session.customer_phone),
        'assumido_por': session.operator_id,
        'last_update': session.updated_at.isoformat(),
    }


def _tenant_sessions(tenant_id):
    if tenant_id is None:
        raise ValueError('Tenant obrigatório para acessar o chat.')
    return ChatSession.objects.filter(tenant_id=tenant_id)


def ensure_chat_session_state(session_key, tenant_id=None):
    session, _ = _tenant_sessions(tenant_id).get_or_create(
        session_key=str(session_key or '').strip() or 'default',
        defaults={'tenant_id': tenant_id},
    )
    return _session_state(session)


def set_chat_session_mode(session_key, mode='bot', user_id=None, *, tenant_id):
    session = _tenant_sessions(tenant_id).get(session_key=session_key)
    session.mode = 'operator' if mode == 'operator' else 'bot'
    if user_id is not None and session.mode == 'operator':
        from django.contrib.auth import get_user_model
        if not get_user_model().objects.filter(pk=user_id, tenant_id=tenant_id).exists():
            raise ValueError('Operador não pertence ao tenant.')
    session.operator_id = user_id if session.mode == 'operator' else None
    session.save(update_fields=['mode', 'operator', 'updated_at'])
    return _session_state(session)


def list_active_chat_sessions(tenant_id=None):
    return [dict(_session_state(session), message_count=session.message_count)
            for session in _tenant_sessions(tenant_id).annotate(message_count=Count('messages')).order_by('-id')]


def get_chat_session(session_key, *, tenant_id):
    session = _tenant_sessions(tenant_id).filter(session_key=session_key).first()
    return _session_state(session) if session else None


def chat_session_belongs_to_tenant(session_key, tenant_id):
    return tenant_id is not None and _tenant_sessions(tenant_id).filter(session_key=session_key).exists()


def _message_data(message):
    return {'id': message.id, 'sender': message.sender, 'message': message.message,
            'created_at': message.created_at.isoformat()}


@transaction.atomic
def add_chat_message(session_key, sender, message, tenant_id=None):
    ensure_chat_session_state(session_key, tenant_id=tenant_id)
    # Serializa gravações da sessão para preservar a ordem dos IDs no polling.
    session = _tenant_sessions(tenant_id).select_for_update().get(session_key=str(session_key or '').strip() or 'default')
    entry = ChatMessage.objects.create(session=session, sender=sender, message=str(message).strip())
    session.updated_at = timezone.now()
    session.save(update_fields=['updated_at'])
    return _message_data(entry)


def get_chat_messages(session_key, after_id=0, *, tenant_id):
    sessions = _tenant_sessions(tenant_id).filter(session_key=session_key)
    return [_message_data(entry) for entry in ChatMessage.objects.filter(session__in=sessions, id__gt=after_id)]


def _format_money(value):
    return f"R$ {float(value):.2f}".replace('.', ',')


def _payment_methods(config):
    if not config:
        return []

    methods = []
    if config.pix:
        methods.append('PIX')
    if config.credito:
        methods.append('cartao de credito')
    if config.debito:
        methods.append('cartao de debito')
    if config.dinheiro:
        methods.append('dinheiro')
    return methods


def build_store_context(request):
    tenant = request.tenant
    config = TenantSettings.load(tenant=tenant)
    telefone = request.COOKIES.get('telefone_cliente', '').strip()
    cliente = None

    if telefone:
        cliente = Cliente.objects.filter(tenant=tenant, telefone=telefone).first()

    produtos = Produto.objects.filter(
        tenant=tenant,
        status=True,
        exibir=True,
    ).select_related('category').order_by('category__ordem', 'ordem_exibicao', 'nome')[:40]
    categorias = Category.objects.filter(tenant=tenant, status=True).order_by('ordem', 'name')[:20]
    pedidos_pendentes = 0

    if cliente:
        pedidos_pendentes = Ordem.objects.filter(tenant=tenant, cliente=cliente, completo=False).count()

    return {
        'store': {
            'nome': config.nome_loja,
            'descricao': config.descricao_loja or '',
            'segmento': config.segmento or 'alimentacao/delivery',
            'whatsapp': config.whatsapp,
            'endereco': ', '.join(filter(None, [config.endereco, config.numero_endereco, config.bairro, config.cidade, config.estado])),
            'taxa_entrega': _format_money(config.taxa_entrega),
            'pedido_minimo': _format_money(config.pagamento_minimo),
            'formas_pagamento': _payment_methods(config),
            'aberto': config.is_open_now(),
        },
        'cliente': {
            'nome': cliente.nome if cliente else '',
            'telefone': telefone,
            'cidade': cliente.cidade if cliente else '',
            'pedidos_pendentes': pedidos_pendentes,
        },
        'categorias': [categoria.name for categoria in categorias],
        'produtos': [
            {
                'nome': produto.nome,
                'categoria': produto.category.name if produto.category else '',
                'descricao': produto.description or '',
                'preco': _format_money(produto.price),
            }
            for produto in produtos
        ],
    }


def chat_greeting():
    hour = timezone.localtime().hour
    return 'Bom dia' if hour < 12 else 'Boa tarde' if hour < 18 else 'Boa noite'


@transaction.atomic
def chat_introduction(session_key, message, *, tenant_id):
    session = _tenant_sessions(tenant_id).select_for_update().get(session_key=session_key)
    if session.introduction_complete or session.customer_phone:
        return None
    match = re.fullmatch(r'\s*(?:meu (?:telefone|número|numero) (?:é|e)\s*)?([+\d() .-]+)\s*', message, re.IGNORECASE)
    phone = re.sub(r'\D', '', match.group(1)) if match else ''
    if len(phone) in (10, 11) or (len(phone) in (12, 13) and phone.startswith('55')):
        session.customer_phone = phone
        session.introduction_complete = True
        session.save(update_fields=['customer_phone', 'introduction_complete', 'updated_at'])
        return 'Obrigado! Como posso ajudar você hoje?'
    if message.strip().lower() in ('prefiro não informar', 'prefiro nao informar', 'não quero informar', 'nao quero informar'):
        session.introduction_complete = True
        session.save(update_fields=['introduction_complete', 'updated_at'])
        return 'Tudo bem! Como posso ajudar você hoje?'
    return 'Claro, será um prazer ajudar! Por gentileza, qual é o seu telefone com DDD?'


def whatsapp_handoff_reply(context):
    whatsapp = str(context.get('store', {}).get('whatsapp') or '').strip()
    if whatsapp:
        return f'Não consegui esclarecer essa dúvida. Por favor, fale com um atendente pelo WhatsApp da loja: {whatsapp}.'
    return 'Não consegui esclarecer essa dúvida. Por favor, procure um atendente da loja. O WhatsApp ainda não está cadastrado.'


def fallback_reply(message, context):
    termo = message.lower().strip()
    store = context.get('store', {})
    produtos = context.get('produtos', []) or []

    if not termo:
        return f"Olá! Posso te ajudar com informações da {store.get('nome', 'loja')}"

    if any(keyword in termo for keyword in ['endereco', 'endereço', 'local', 'onde fica', 'bairro', 'cidade']):
        endereco = str(store.get('endereco') or '').strip()
        if endereco:
            return f'O endereço da loja é: {endereco}'
        whatsapp = str(store.get('whatsapp') or '').strip()
        if whatsapp:
            return f'O endereço da loja ainda não está cadastrado. Por gentileza, confirme com um atendente pelo WhatsApp: {whatsapp}.'
        return 'O endereço da loja ainda não está cadastrado. Por gentileza, confirme com um atendente da loja.'

    if any(keyword in termo for keyword in ['whatsapp', 'contato', 'telefone', 'falar com', 'atendimento']):
        whatsapp = store.get('whatsapp') or 'Não informado.'
        return f"Você pode falar com a loja pelo WhatsApp: {whatsapp}"

    if any(keyword in termo for keyword in ['entrega', 'taxa', 'frete', 'delivery']):
        taxa = store.get('taxa_entrega') or 'não informado'
        return f"A taxa de entrega é {taxa}."

    if any(keyword in termo for keyword in ['pedido minimo', 'pedido mínimo', 'minimo', 'mínimo']):
        minimo = store.get('pedido_minimo') or 'não informado'
        return f"O pedido mínimo é {minimo}."

    if any(keyword in termo for keyword in ['pagamento', 'pagar', 'pix', 'cartao', 'cartão', 'credito', 'crédito', 'debito', 'dinheiro']):
        formas = store.get('formas_pagamento') or []
        if formas:
            return f"Na {store.get('nome', 'loja')} você pode pagar com: {', '.join(formas)}."
        return f"Para pagar na {store.get('nome', 'loja')}, fale com a loja pelo WhatsApp: {store.get('whatsapp', 'não informado')}."

    if any(keyword in termo for keyword in ['horario', 'horário', 'aberto', 'funciona', 'encerra', 'fecha', 'fechado']):
        status = 'aberta' if store.get('aberto') else 'fechada'
        return f"A loja está {status} no momento. Se quiser, também posso te passar o endereço ou formas de pagamento."

    encontrados = [produto for produto in produtos if termo and (termo in produto['nome'].lower() or produto['nome'].lower() in termo)]

    if encontrados:
        linhas = [f"{produto['nome']} - {produto['preco']}" for produto in encontrados[:5]]
        return 'Encontrei estes itens no cardapio:\n' + '\n'.join(linhas)

    return whatsapp_handoff_reply(context)


def ask_ai_assistant(message, context):
    api_key = getattr(settings, 'AI_CHAT_API_KEY', '')
    if not api_key:
        return fallback_reply(message, context), False

    payload = {
        'model': getattr(settings, 'AI_CHAT_MODEL', 'gpt-4o-mini'),
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Não fale posso te ajudar com cardapio.  Fale que pode me ajudar com informações da loja. '
                    'O cumprimento e a coleta do telefone já foram realizados pelo sistema. Não repita essas etapas. '
                    'Responda em portugues do Brasil, '
                    'com frases curtas, usando apenas as informacoes do contexto da loja. '
                    'Quando nao souber, oriente o cliente a chamar no WhatsApp da loja.'
                    'Você atende a empresa identificada no contexto da loja. '
                    'o WhatsApp da loja é o principal canal de contato. Voce pode passar pegando do contexto.'
                    'Regras:'
                    '- Responda sempre em português do Brasil.'
                    'informe se a loja esta aberta ou fechada de acordo com o contexto.  Tente pegar essa informação das configurações da loja.'
                    '- Seja educado, gentil e acolhedor. Ao perguntar como pode ajudar, use: Como posso ajudar você hoje? '
                    '- Nunca invente informações.'
                    '- Se não souber a resposta ou faltar informação no contexto, encaminhe gentilmente para um atendente e inclua o número exato de store.whatsapp na resposta. Se não estiver cadastrado, informe isso sem inventar um telefone. '
                    '- Não fale sobre assuntos que não tenham relação com a empresa.'                    
                    '- Nunca diga que é um robô.'
                    '- Quando o cliente quiser contratar, peça nome, telefone e endereço.'
                ),
            },
            {
                'role': 'system',
                'content': f'Contexto da loja vindo do banco de dados: {context}',
            },
            {
                'role': 'user', 'content': message
            },
        ],
        'temperature': 0.4,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            getattr(settings, 'AI_CHAT_API_URL', 'https://api.openai.com/v1/chat/completions'),
            json=payload,
            headers=headers,
            timeout=getattr(settings, 'AI_CHAT_TIMEOUT', 20),
        )
        response.raise_for_status()
        data = response.json()
        answer = (data['choices'][0]['message']['content'] or '').strip()
        if not answer:
            return whatsapp_handoff_reply(context), False
        return answer, True
    except Exception:
        logger.exception('Falha ao consultar IA do chat')
        return fallback_reply(message, context), False
