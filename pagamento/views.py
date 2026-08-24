import logging
import json
import uuid

from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.utils import calcular_dias_restantes
from pagamento.mercadopago_client import buscar_pagamento, validar_assinatura_webhook
from pagamento.models import Pagamento
from tenants.models import Configuracao
import mercadopago



logger = logging.getLogger(__name__)

def pagamento(request):
    logger.debug('Requisição %s recebida em /pagamento por %s', request.method, request.user)

    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user
    config = Configuracao.load()

    if request.method == 'POST':
        logger.info(
            'POST de pagamento recebido: usuário=%s dados=%s',
            user.pk,
            {
                key: value
                for key, value in request.POST.dict().items()
                if key != 'csrfmiddlewaretoken'
            },
        )

        if not config.SecrectKey:
            logger.warning('Pagamento recusado: Access Token não configurado.')
            messages.error(request, 'Access Token do Mercado Pago não configurado.')
            return redirect('pagamento')

        valor = config.valor_mensalidade
        forma_pagamento = request.POST.get('forma_pagamento', 'pix')
        external_reference = f'renovacao-{user.pk}-{uuid.uuid4().hex}'
        pagamento_registro = Pagamento.objects.create(
            nr_cobranca=external_reference,
            tenant=user.tenant,
            user=user,
            valor=valor,
            forma_pagamento=forma_pagamento,
            external_reference=external_reference,
            dias_creditados=config.dias_gratuitos,
        )
        success_url = request.build_absolute_uri(reverse('pagamento_sucesso'))
        preference_data = {
            'items': [
                {
                    'id': 'renovacao-assinatura',
                    'user_id': '3634590631',
                    'usuario_teste': 'TESTUSER5363523354863917438',
                    'title': 'Renovação de Assinatura',
                    'quantity': 1,
                    'unit_price': float(valor),
                    'currency_id': 'BRL',
                }
            ],
            'payer': {'email': user.email},
            'external_reference': external_reference,
            'back_urls': {
                'success': success_url,
                'failure': request.build_absolute_uri(reverse('pagamento_falha')),
                'pending': request.build_absolute_uri(reverse('pagamento_pendente')),
            },
            'notification_url': request.build_absolute_uri(reverse('webhook_mercadopago')),
        }

        if not success_url.startswith(('http://localhost', 'http://127.0.0.1')):
            preference_data['auto_return'] = 'approved'

        logger.info(
            'Criando preferência para usuário=%s forma=%s valor=%s',
            user.pk,
            forma_pagamento,
            valor,
        )
        preference_response = mercadopago.SDK(
            config.SecrectKey
        ).preference().create(preference_data)
        preference = preference_response.get('response', {})
        logger.info(
            'Resposta da preferência do Mercado Pago: status=%s resposta=%s',
            preference_response.get('status'),
            preference,
        )
        request.session['mercadopago_preference_json'] = json.dumps(
            preference_response,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        if preference_response.get('status') not in (200, 201):
            pagamento_registro.status = 'rejected'
            pagamento_registro.save(update_fields=['status', 'data_atualizacao'])
            logger.error('Falha ao criar preferência: %s', preference_response)
            messages.error(request, 'Não foi possível gerar o pagamento.')
            return redirect('pagamento')

        is_sandbox = config.SecrectKey.startswith('TEST-')
        checkout_url = (
            preference.get('sandbox_init_point')
            if is_sandbox
            else preference.get('init_point')
        )
        if not checkout_url:
            logger.error('Preferência criada sem URL de checkout: %s', preference_response)
            messages.error(request, 'O Mercado Pago não retornou a URL de pagamento.')
            return redirect('pagamento')

        pagamento_registro.mp_preference_id = preference.get('id')
        pagamento_registro.save(
            update_fields=['mp_preference_id', 'data_atualizacao']
        )

        logger.info(
            'Redirecionando para checkout: preferência=%s sandbox=%s url=%s',
            preference.get('id'),
            is_sandbox,
            checkout_url,
        )
        return redirect(checkout_url)

    dias_restantes = None
    if user.data_expiracao:
        dias_restantes = calcular_dias_restantes(user.data_expiracao)

    ultimo_webhook = (
        Pagamento.objects.filter(user=user, resposta_bruta__isnull=False)
        .order_by('-data_atualizacao')
        .first()
    )

    context = {
        "configuracao": config,
        "dias_restantes": dias_restantes,
        "data_expiracao": user.data_expiracao,
        "mercadopago_preference_json": request.session.pop(
            'mercadopago_preference_json', None
        ),
        "mercadopago_return_json": request.session.pop(
            'mercadopago_return_json', None
        ),
        "webhook_json": json.dumps(
            ultimo_webhook.resposta_bruta,
            ensure_ascii=False,
            indent=2,
            default=str,
        ) if ultimo_webhook else None,
    }

    return render(request, 'pagamento/index.html', context)


def pagamento_sucesso(request):
    retorno = request.GET.dict()
    logger.info('Retorno aprovado do Mercado Pago: %s', retorno)
    request.session['mercadopago_return_json'] = json.dumps(
        retorno, ensure_ascii=False, indent=2
    )
    messages.success(request, 'Pagamento aprovado. Obrigado!')
    return redirect('pagamento')


def pagamento_falha(request):
    retorno = request.GET.dict()
    logger.warning('Retorno de pagamento recusado/cancelado: %s', retorno)
    request.session['mercadopago_return_json'] = json.dumps(
        retorno, ensure_ascii=False, indent=2
    )
    messages.error(request, 'O pagamento não foi concluído. Tente novamente.')
    return redirect('pagamento')


def pagamento_pendente(request):
    retorno = request.GET.dict()
    logger.info('Retorno de pagamento pendente: %s', retorno)
    request.session['mercadopago_return_json'] = json.dumps(
        retorno, ensure_ascii=False, indent=2
    )
    messages.info(request, 'Pagamento pendente de confirmação.')
    return redirect('pagamento')


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    conteudo_bruto = request.body.decode('utf-8', errors='replace')
    logger.info(
        'Webhook recebido: query=%s request_id=%s tópico=%s corpo=%s',
        request.GET.dict(),
        request.headers.get('x-request-id'),
        request.GET.get('type') or request.GET.get('topic'),
        conteudo_bruto,
    )

    try:
        dados = json.loads(conteudo_bruto)
    except json.JSONDecodeError as error:
        logger.warning('Webhook do Mercado Pago com JSON inválido: %s', error)
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    data_id = str((dados.get('data') or {}).get('id') or '')
    if not validar_assinatura_webhook(request, data_id):
        logger.warning('Webhook do Mercado Pago com assinatura inválida.')
        return JsonResponse({'error': 'Assinatura inválida'}, status=403)

    pagamento_dados = {}
    if data_id:
        try:
            pagamento_dados = buscar_pagamento(data_id)
        except Exception:
            logger.exception('Não foi possível consultar o pagamento %s.', data_id)

    external_reference = (
        pagamento_dados.get('external_reference')
        or dados.get('external_reference')
    )
    pagamento_registro = None
    if external_reference:
        pagamento_registro = Pagamento.objects.filter(
            external_reference=external_reference
        ).first()

    webhook_log = {
        'webhook': dados,
        'query': request.GET.dict(),
        'request_id': request.headers.get('x-request-id'),
        'payment': pagamento_dados or None,
    }
    if pagamento_registro:
        pagamento_registro.resposta_bruta = webhook_log
        if data_id:
            pagamento_registro.mp_payment_id = data_id
        status = pagamento_dados.get('status')
        if status in dict(Pagamento.STATUS_CHOICES):
            pagamento_registro.status = status
        pagamento_registro.save()

    logger.info(
        'Webhook processado: ação=%s tipo=%s id=%s dados=%s',
        dados.get('action'),
        dados.get('type'),
        (dados.get('data') or {}).get('id'),
        json.dumps(dados, ensure_ascii=False),
    )
    return JsonResponse(
        {
            'received': True,
            'persisted': pagamento_registro is not None,
            'data': dados,
        },
        status=200,
    )


def webhook_log(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'unauthorized'}, status=401)

    pagamento_registro = (
        Pagamento.objects.filter(
            user=request.user,
            resposta_bruta__isnull=False,
        )
        .order_by('-data_atualizacao')
        .first()
    )
    return JsonResponse({
        'webhook': (
            pagamento_registro.resposta_bruta
            if pagamento_registro
            else None
        ),
        'updated_at': (
            pagamento_registro.data_atualizacao.isoformat()
            if pagamento_registro
            else None
        ),
    })