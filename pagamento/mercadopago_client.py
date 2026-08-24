import hashlib
import hmac

import mercadopago
from django.conf import settings
from tenants.models import Configuracao


def get_sdk():
    access_token = Configuracao.load().SecrectKey
    return mercadopago.SDK(access_token)


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
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '')
    if not secret:
        # Ambiente de teste do Mercado Pago não fornece uma chave de assinatura própria.
        # Não bloqueia o webhook, mas o status ainda é confirmado via buscar_pagamento()
        # (nunca confiamos apenas no payload recebido).
        print("⚠️ MERCADOPAGO_WEBHOOK_SECRET não configurado — pulando validação de assinatura (modo teste).")
        return True

    signature_header = request.headers.get('x-signature', '')
    request_id = request.headers.get('x-request-id', '')

    ts = None
    v1 = None
    for part in signature_header.split(','):
        part = part.strip()
        if part.startswith('ts='):
            ts = part[3:]
        elif part.startswith('v1='):
            v1 = part[3:]

    if not ts or not v1:
        return False

    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    assinatura_calculada = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(assinatura_calculada, v1)
