from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from tenants.models import Configuracao


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

    context = {
        'dias_restantes': dias_restantes,
        'data_expiracao': user.data_expiracao,
        'valor_mensalidade': valor_mensalidade,
    }
    return render(request, 'pagamento/index.html', context)