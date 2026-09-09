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


@transaction.atomic
def set_chat_session_mode(session_key, mode='bot', user_id=None, *, tenant_id):
    session = _tenant_sessions(tenant_id).select_for_update().get(session_key=session_key)
    if session.mode == 'closed':
        return _session_state(session)
    session.mode = mode if mode in ('operator', 'closed') else 'bot'
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
    ).select_related('category').order_by('category__ordem', 'ordem_exibicao', 'nome')
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
            'orientacoes_ia': config.ai_orientations or '',
            'chave_pix': config.chave_pix or '',
            'nome_pix': config.nome_pix or '',
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
        return 'Obrigado! Recebemos seu telefone e logo entraremos em contato. Como posso ajudar você hoje?'
    if message.strip().lower() in ('prefiro não informar', 'prefiro nao informar', 'não quero informar', 'nao quero informar'):
        session.introduction_complete = True
        session.save(update_fields=['introduction_complete', 'updated_at'])
        return 'Tudo bem! Como posso ajudar você hoje?'
    return 'Claro, será um prazer ajudar! Por gentileza, qual é o seu telefone com DDD?'


def product_contact_reply(context):
    if context.get('cliente', {}).get('telefone'):
        return 'Seu telefone já está registrado para que uma atendente entre em contato com você.'
    return 'Por gentileza, deixe seu telefone com DDD para que uma atendente entre em contato com você.'


def matching_products(message, context):
    import unicodedata
    def normalize(text):
        return ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c)).strip()
    term = normalize(message)
    return [p for p in context.get('produtos', []) if term and normalize(p['nome']) and
            (normalize(p['nome']) in term or term in normalize(p['nome']))]


def product_details_reply(products, context):
    lines = [f"{p['nome']} — {p['preco']}" for p in products[:5]]
    methods = context.get('store', {}).get('formas_pagamento') or []
    payment = 'Formas de pagamento: ' + ', '.join(methods) + '.' if methods else 'As formas de pagamento ainda não estão cadastradas.'
    return 'Temos estes produtos cadastrados:\n' + '\n'.join(lines) + '\n' + payment + '\n\n' + product_contact_reply(context)


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
        chave_pix = str(store.get('chave_pix') or '').strip()
        pix_info = f' A chave PIX é: {chave_pix}.' if chave_pix and any(term in termo for term in ['pix', 'pagar']) else ''
        if formas:
            return f"Na {store.get('nome', 'loja')} você pode pagar com: {', '.join(formas)}.{pix_info}"
        return f"Para pagar na {store.get('nome', 'loja')}, fale com a loja pelo WhatsApp: {store.get('whatsapp', 'não informado')}.{pix_info}"

    if any(keyword in termo for keyword in ['horario', 'horário', 'aberto', 'funciona', 'encerra', 'fecha', 'fechado']):
        status = 'aberta' if store.get('aberto') else 'fechada'
        return f"A loja está {status} no momento. Se quiser, também posso te passar o endereço ou formas de pagamento."

    encontrados = matching_products(message, context)
    if encontrados:
        return product_details_reply(encontrados, context)

    if any(term in termo for term in ['vocês têm', 'voces tem', 'vocês tem', 'tem ', 'vende', 'produto', 'disponível', 'disponivel']):
        return 'Não consegui localizar com segurança esse produto no cadastro disponível. ' + whatsapp_handoff_reply(context)
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
                'Você é o atendente virtual de uma loja especializada em capacetes.'
                'Seu objetivo é atender os clientes de forma educada, rápida, clara e comercial, ajudando na escolha dos produtos disponíveis.'
                'HORÁRIO DE FUNCIONAMENTO:'
                'A loja funciona das 08:00 às 14:00.'
                'Caso o cliente entre em contato fora desse horário, informe que a loja está fechada no momento e que o atendimento humano funciona das 08:00 às 14:00. Mesmo fora do horário, continue ajudando o cliente com informações sobre os produtos.'
                'PRODUTOS:'
                'Os produtos disponíveis estão cadastrados na tabela `produtos` do sistema.'
                'Sempre que o cliente perguntar sobre:'
                '* capacetes disponíveis;'
                '* marcas;'
                '* modelos;'
                '* tamanhos;'
                '* cores;'
                '* preços;'
                '* estoque;'
                '* características de um capacete;'
                'consulte primeiro os dados disponíveis na tabela `produtos`.'
                'Nunca invente produtos, preços, tamanhos, cores ou disponibilidade.'
                'Se o produto não estiver cadastrado ou não for encontrado, informe ao cliente que não encontrou aquele produto no estoque atual.'
                'ATENDIMENTO:'
                'Responda de forma simples, amigável e objetiva.'
                'Quando possível, faça perguntas para entender melhor o que o cliente procura, por exemplo:'
                '"Você procura capacete aberto, fechado ou articulado?"'
                '"Qual tamanho você usa?"'
                '"Tem alguma faixa de preço que deseja?"'
                'Quando encontrar produtos compatíveis, apresente algumas opções com nome, modelo, preço e principais características.'
                'Evite respostas muito longas.'
                'Se o cliente demonstrar interesse em comprar, incentive a continuidade da compra e informe os próximos passos disponíveis no sistema.'
                'Nunca informe que um produto está disponível sem consultar o estoque.'
                'Se não souber uma informação, diga que não possui aquela informação no momento em vez de inventar uma resposta.'
                'Seu papel é ajudar o cliente a encontrar o capacete mais adequado entre os produtos realmente cadastrados na loja.'
                'Sempre que ficar confuso informe ao cliente para falar com um atendimento humano pwlo whatsapp.'
                'HORÁRIO DE FUNCIONAMENTO:'
                'A loja funciona das 08:00 às 14:00.'
                'Caso o cliente entre em contato fora desse horário, informe que a loja está fechada no momento e que o atendimento humano funciona das 08:00 às 14:00. Mesmo fora do horário, continue ajudando o cliente com informações sobre os produtos.'
                'PRODUTOS:'
                'Os produtos disponíveis estão cadastrados na tabela `produtos` do sistema.'
                'Sempre que o cliente perguntar sobre:'
                '* capacetes disponíveis;'
                '* marcas;'
                '* modelos;'
                '* tamanhos;'
                '* cores;'
                '* preços;'
                '* estoque;'
                '* características de um capacete;'
                'consulte primeiro os dados disponíveis na tabela `produtos`.'
                'Nunca invente produtos, preços, tamanhos, cores ou disponibilidade.'
                'Se o produto não estiver cadastrado ou não for encontrado, informe ao cliente que não encontrou aquele produto no estoque atual.'
                'Inclua sempre o contato do WhatsApp da loja para atendimento humano.'
                'ATENDIMENTO:'
                'Responda de forma simples, amigável e objetiva.'
                'Quando possível, faça perguntas para entender melhor o que o cliente procura, por exemplo:'
                '"Você procura capacete aberto, fechado ou articulado?"'
                '"Qual tamanho você usa?"'
                "Tem alguma faixa de preço que deseja?"
                'Quando encontrar produtos compatíveis, apresente algumas opções com nome, modelo, preço e principais características.'
                'Evite respostas muito longas.'
                'Se o cliente demonstrar interesse em comprar, incentive a continuidade da compra e informe os próximos passos disponíveis no sistema.'
                '- Nunca informe que um produto está disponível sem consultar o estoque.'
                'Se não souber uma informação, diga que não possui aquela informação no momento em vez de inventar uma resposta.'
                'Seu papel é ajudar o cliente a encontrar o capacete mais adequado entre os produtos realmente cadastrados na loja.'
                'Sempre que ficar confuso informe ao cliente para falar com um atendimento humano pwlo whatsapp'
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
                '- Para consultas de produtos, consulte a lista produtos do contexto, carregada do banco da própria loja. '
                'Ela contém todos os produtos ativos e visíveis. Se encontrar, informe primeiro o nome, o preço cadastrado e as formas de pagamento em store.formas_pagamento. '
                'Quando o cliente perguntar sobre PIX ou solicitar a chave PIX, informe o valor exato de store.chave_pix. Se estiver vazio, diga que a chave PIX não está cadastrada. '
                'Se não encontrar, diga que não localizou no cadastro; se o pedido for ambíguo, peça o nome do produto. '
                'O cadastro não controla estoque: não prometa disponibilidade física nem invente quantidades. '
                'Somente após informar produto, preço e formas de pagamento, peça gentilmente o telefone com DDD para que uma atendente entre em contato. '
                'Se cliente.telefone já estiver preenchido, diga que o telefone está registrado, sem pedir novamente. '
                'Não invente prazo de retorno nem diga que uma atendente já foi notificada automaticamente. '
                '- Se não souber a resposta ou faltar informação no contexto, encaminhe gentilmente para um atendente e inclua o número exato de store.whatsapp na resposta. Se não estiver cadastrado, informe isso sem inventar um telefone. '
                '- Não fale sobre assuntos que não tenham relação com a empresa.'                    
                '- Nunca diga que é um robô.'
                '- Quando o cliente quiser contratar, peça nome, telefone e endereço. e informe o contato do WhatsApp da loja.'
                ),
            },
            {
                'role': 'system',
                'content': (
                    'Orientações personalizadas da loja para este atendimento: '
                    f"{context.get('store', {}).get('orientacoes_ia', '').strip() or 'Nenhuma orientação personalizada cadastrada.'}"
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
