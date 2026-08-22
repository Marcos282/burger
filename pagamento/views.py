from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from tenants.models import Configuracao
import requests


def pagamento(request):
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user
    config = Configuracao.load()
    valor_mensalidade = config.valor_mensalidade

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
        'configuracao': config,
    }

    code = request.GET.get("code")
    if code:
        data = {
            "grant_type": "authorization_code",
            "client_id": config.client_id_mercadolivre,
            "client_secret": config.secret_mercadolivre,
            "code": code,
            "redirect_uri": "http://localhost:8000/pagamento",
        }
        response = requests.post("https://api.mercadolibre.com/oauth/token", data=data)
        token_info = response.json()

        access_token = token_info.get("access_token")
        context["access_token"] = access_token
        context["refresh_token"] = token_info.get("refresh_token")
        context["expires_in"] = token_info.get("expires_in")

        if access_token:
            # Persiste o token para uso posterior (ex: chamadas futuras à API do Mercado Livre)
            config.Token_mercadolivre = access_token
            config.save()

            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = requests.get("https://api.mercadolibre.com/users/me", headers=headers)
            context["user_info"] = user_response.json()

    return render(request, 'pagamento/index.html', context)