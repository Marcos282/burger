import re

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from core.utils import get_tenant_url
from orders.models import Ordem
from .defaults import ETAPAS, VARIAVEIS
from .models import MensagemAutomatica


VARIAVEIS_PERMITIDAS = {nome for nome, _ in VARIAVEIS}


def configuracao(request):
    if not request.user.is_authenticated:
        return redirect('login')

    tenant = getattr(request.user, 'tenant', None)
    if tenant is None:
        return redirect('login')

    mensagens_salvas = {
        item.status_pedido: item
        for item in MensagemAutomatica.objects.filter(tenant=tenant)
    }

    if request.method == 'POST':
        erros = []
        atualizacoes = []
        for etapa in ETAPAS:
            status = etapa['status']
            texto = request.POST.get(f'mensagem_{status}', '').strip()
            desconhecidas = set(re.findall(r'\{[^{}]+\}', texto)) - VARIAVEIS_PERMITIDAS
            if not texto:
                erros.append(f'A mensagem de “{etapa["titulo"]}” está vazia.')
            elif len(texto) > 1000:
                erros.append(f'A mensagem de “{etapa["titulo"]}” ultrapassa 1000 caracteres.')
            elif desconhecidas:
                erros.append(f'Variável inválida em “{etapa["titulo"]}”: {", ".join(sorted(desconhecidas))}.')
            atualizacoes.append((status, texto, request.POST.get(f'ativa_{status}') == 'on'))

        if erros:
            for erro in erros:
                messages.error(request, erro)
        else:
            with transaction.atomic():
                for status, texto, ativa in atualizacoes:
                    MensagemAutomatica.objects.update_or_create(
                        tenant=tenant,
                        status_pedido=status,
                        defaults={'mensagem': texto, 'ativa': ativa},
                    )
            messages.success(request, 'Mensagens automáticas salvas com sucesso.')
            return redirect('painel_whatsapp_api')

    etapas = []
    for etapa in ETAPAS:
        salva = mensagens_salvas.get(etapa['status'])
        etapas.append({
            **etapa,
            'mensagem_atual': salva.mensagem if salva else etapa['mensagem'],
            'ativa': salva.ativa if salva else True,
        })

    return render(request, 'whatsapp/configuracao.html', {
        'localizacao': [{'n1': 'WhatsApp API', 'url': 'painel_whatsapp_api'}],
        'qt_items_cliente': Ordem.objects.filter(tenant=tenant).count(),
        'url_marketplace': get_tenant_url(request, '/loja/'),
        'etapas': etapas,
        'variaveis': VARIAVEIS,
    })

# Create your views here.
