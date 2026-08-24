import logging

import mercadopago
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from mercadopago.webhook.validator import (
    InvalidWebhookSignatureError,
    WebhookSignatureValidator,
)
from tenants.models import Configuracao


logger = logging.getLogger(__name__)


def get_access_token():
    access_token = (Configuracao.load().SecrectKey or '').strip()
    if not access_token:
        raise ImproperlyConfigured('Access Token do Mercado Pago não configurado.')
    if not access_token.startswith(('APP_USR-', 'TEST-')):
        raise ImproperlyConfigured('Access Token do Mercado Pago possui formato inválido.')
    return access_token


def get_sdk():
    return mercadopago.SDK(get_access_token())


def criar_pagamento_pix(pagamento, notification_url):
    """Cria uma cobrança Pix no Mercado Pago para o registro `Pagamento` informado."""
    sdk = get_sdk()
    payload = {
        "transaction_amount": float(pagamento.valor),
        "description": f"Renovação de acesso - {pagamento.user.username}",
        "payment_method_id": "pix",
        "payer": {"email": pagamento.user.email},
        "external_reference": pagamento.external_reference,
        "notification_url": notification_url,
    }
    result = sdk.payment().create(payload)
    return result["response"]


def buscar_pagamento(mp_payment_id):
    """Consulta o status atual de um pagamento direto na API do Mercado Pago."""
    sdk = get_sdk()
    result = sdk.payment().get(mp_payment_id)
    return result["response"]


def validar_assinatura_webhook(request, data_id):
    """
    Valida o header x-signature do webhook do Mercado Pago.
    https://www.mercadopago.com.br/developers/pt/docs/checkout-api/webhooks#editor_5
    """
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '').strip()
    if not secret:
        # A consulta posterior à API continua sendo a fonte de verdade do pagamento.
        logger.warning('MERCADOPAGO_WEBHOOK_SECRET não configurado; assinatura não validada.')
        return True

    try:
        WebhookSignatureValidator.validate(
            request.headers.get('x-signature'),
            request.headers.get('x-request-id'),
            data_id,
            secret,
        )
    except InvalidWebhookSignatureError:
        return False
    return True
