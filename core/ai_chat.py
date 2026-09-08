import logging
from datetime import datetime, timezone as datetime_timezone

import requests
from django.conf import settings

from customers.models import Cliente
from menu.models import Category, Produto
from orders.models import Ordem
from tenants.models import TenantSettings

logger = logging.getLogger(__name__)
_CHAT_SESSIONS = {}


def ensure_chat_session_state(session_key, tenant_id=None):
    key = str(session_key or '').strip() or 'default'
    if key not in _CHAT_SESSIONS:
        _CHAT_SESSIONS[key] = {
            'mode': 'bot',
            'assumido_por': None,
            'last_update': None,
            'tenant_id': tenant_id,
            'messages': [],
        }
    elif tenant_id is not None and _CHAT_SESSIONS[key].get('tenant_id') is None:
        _CHAT_SESSIONS[key]['tenant_id'] = tenant_id
    return _CHAT_SESSIONS[key]


def set_chat_session_mode(session_key, mode='bot', user_id=None):
    state = ensure_chat_session_state(session_key)
    normalized_mode = 'operator' if str(mode or '').strip().lower() == 'operator' else 'bot'
    state['mode'] = normalized_mode
    state['assumido_por'] = user_id
    state['last_update'] = __import__('datetime').datetime.utcnow().isoformat()
    return state


def list_active_chat_sessions(tenant_id=None):
    sessions = []
    for session_key, state in _CHAT_SESSIONS.items():
        if not isinstance(state, dict):
            continue
        if tenant_id is not None and str(state.get('tenant_id')) != str(tenant_id):
            continue
        sessions.append({
            'session_id': session_key,
            'mode': 'operator' if state.get('mode') == 'operator' else 'bot',
            'assumido_por': state.get('assumido_por'),
            'last_update': state.get('last_update'),
            'message_count': len(state.get('messages', [])),
        })
    return sorted(sessions, key=lambda item: item['session_id'])


def get_chat_session(session_key):
    return _CHAT_SESSIONS.get(str(session_key or '').strip())


def chat_session_belongs_to_tenant(session_key, tenant_id):
    state = get_chat_session(session_key)
    return bool(state and str(state.get('tenant_id')) == str(tenant_id))


def add_chat_message(session_key, sender, message, tenant_id=None):
    state = ensure_chat_session_state(session_key, tenant_id=tenant_id)
    messages = state.setdefault('messages', [])
    entry = {
        'id': len(messages) + 1,
        'sender': sender,
        'message': str(message).strip(),
        'created_at': datetime.now(datetime_timezone.utc).isoformat(),
    }
    messages.append(entry)
    state['last_update'] = entry['created_at']
    return entry


def get_chat_messages(session_key, after_id=0):
    state = get_chat_session(session_key)
    if not state:
        return []
    return [message for message in state.get('messages', []) if message['id'] > after_id]


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


def fallback_reply(message, context):
    termo = message.lower().strip()
    store = context.get('store', {})
    produtos = context.get('produtos', []) or []

    if not termo:
        return f"Olá! Posso te ajudar com informações da {store.get('nome', 'loja')}"

    if any(keyword in termo for keyword in ['endereco', 'endereço', 'local', 'onde fica', 'bairro', 'cidade']):
        endereco = store.get('endereco') or 'Endereço não informado.'
        return f"O endereço da {store.get('nome', 'loja')} é: {endereco}"

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

    encontrados = [produto for produto in produtos if termo and termo in produto['nome'].lower()]

    if encontrados:
        linhas = [f"{produto['nome']} - {produto['preco']}" for produto in encontrados[:5]]
        return 'Encontrei estes itens no cardapio:\n' + '\n'.join(linhas)

    if produtos:
        sugestoes = [f"{produto['nome']} ({produto['preco']})" for produto in produtos[:4]]
        return f"Posso te ajudar com o cardapio da {store.get('nome', 'loja')}. Sugestoes: " + ', '.join(sugestoes) + '. '

    return f"Olá! Posso te ajudar com informações da {store.get('nome', 'loja')}."


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
                    'se apresente inicialmente dando bom dia ou boa tarde, e informe que quem está falando é um atendente virtual. '
                    'Responda em portugues do Brasil, '
                    'com frases curtas, usando apenas as informacoes do contexto da loja. '
                    'Quando nao souber, oriente o cliente a chamar no WhatsApp da loja.'
                    'Você é o atendente virtual da empresa Nova Rede Fibra.'
                    'o WhatsApp da loja é o principal canal de contato. Voce pode passar pegando do contexto.'
                    'Regras:'
                    '- Responda sempre em português do Brasil.'
                    'informe se a loja esta aberta ou fechada de acordo com o contexto.  Tente pegar essa informação das configurações da loja.'
                    '- Seja educado, direto e amigável.'
                    '- Nunca invente informações.'
                    '- Se não souber a resposta, diga que precisa consultar um atendente.'
                    '- Não fale sobre assuntos que não tenham relação com a empresa.'                    
                    '- Nunca diga que é um robô.'
                    '- Quando o cliente quiser contratar, peça nome, telefone e endereço.'
                ),
            },
            {
                'role': 'system',
                'content': f'Contexto da loja vindo do banco de dados: {context}',
            },
            {'role': 'user', 'content': message},
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
        return data['choices'][0]['message']['content'].strip(), True
    except Exception:
        logger.exception('Falha ao consultar IA do chat')
        return fallback_reply(message, context), False
