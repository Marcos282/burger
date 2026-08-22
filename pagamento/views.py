from django.conf import settings
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from tenants.models import Configuracao
import requests
from django.http import JsonResponse


def pagamento(request):
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user
    configuracao = Configuracao.load()
    valor_mensalidade = configuracao.valor_mensalidade

    if request.method == 'POST':
        # Valor sempre vem do servidor (Configuracao.valor_mensalidade), nunca do POST do cliente.
        forma_pagamento = request.POST.get('forma_pagamento', '')
        # TODO: integrar com o gateway de pagamento (ex: Mercado Pago) usando `valor_mensalidade` e `forma_pagamento`.
        messages.info(request, f'Pagamento de R$ {valor_mensalidade:.2f} via {forma_pagamento} recebido. Integração de cobrança em breve.')

    dias_restantes = None
    if user.data_expiracao:
        dias_restantes = (user.data_expiracao - timezone.now()).days

    localizacao = [
        {"n1": "Pagamento", "url": "pagamento"},
    ]

    context = {
        'dias_restantes': dias_restantes,
        'data_expiracao': user.data_expiracao,
        'valor_mensalidade': valor_mensalidade,
        'localizacao': localizacao,
        'configuracao': configuracao,
    }
    return render(request, 'pagamento/index.html', context)


def pagamento_callback(request):
    if not request.user.is_authenticated:
        return redirect('login')

    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "missing_code"}, status=400)

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.MERCADOLIVRE_CLIENT_ID,
        "client_secret": settings.MERCADOLIVRE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.MERCADOLIVRE_REDIRECT_URI,
    }
    response = requests.post("https://api.mercadolibre.com/oauth/token", data=data)

    return JsonResponse(response.json(), status=response.status_code)