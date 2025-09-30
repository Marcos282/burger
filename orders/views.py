from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string

from customers.models import Cliente, EnderecoEntrega
from orders.models import Ordem, OrdemItem
from menu.models import Produto
from tenants.models import Tenant

def cadastro_form(request):
    # Recupera o tenant (ajuste conforme sua lógica de multi-tenancy)
    tenant = getattr(request, 'tenant', None)

    # Recupera o carrinho da sessão
    cart = request.session.get('cart', {})
    produtos_carrinho = []
    subtotal = 0
    total_itens = 0

    if tenant and cart:
        for produto_id, qtd in cart.items():
            try:
                produto = Produto.objects.get(id=produto_id, tenant=tenant)
                valor = produto.price * qtd
                produtos_carrinho.append({
                    'nome': produto.nome,
                    'referencia': produto.referencia,
                    'quantidade': qtd,
                    'preco_unitario': produto.price,
                    'valor': valor,
                })
                subtotal += valor
                total_itens += qtd
            except Produto.DoesNotExist:
                continue

    # Exemplo de taxa de entrega fixa (ajuste conforme sua regra)
    taxa_entrega = 0.0
    total = subtotal + taxa_entrega

    telefone_cookie = request.COOKIES.get('telefone_cliente', '')
    context = {
        'produtos_carrinho': produtos_carrinho,
        'subtotal': subtotal,
        'taxa_entrega': taxa_entrega,
        'total': total,
        'total_itens': total_itens,
        'telefone_cliente': telefone_cookie,
    }
    return render(request, 'loja/pedidodelivery.html', context)



@csrf_exempt  # Desabilita a verificação CSRF (não é o ideal em produção, melhor manter o {% csrf_token %})
def pedido_delivery(request):
    """
    View responsável por processar o checkout (cadastro de pedido).
    Fluxo:
    1. Recebe os dados do formulário via POST.
    2. Cria ou recupera o cliente.
    3. Gera uma ordem de compra (pedido).
    4. Percorre o carrinho da sessão e cria itens do pedido (OrdemItem).
    5. Salva o endereço de entrega.
    6. Limpa o carrinho e redireciona para página de sucesso.
    """

    # Só trata o POST (quando o usuário envia o formulário)
    if request.method == "POST":
        # 🔹 1. Identificar o tenant
        # Aqui estou pegando o primeiro tenant só para exemplo.
        # Depois você pode trocar para buscar pelo subdomínio ou usuário logado.
        tenant = request.tenant
        
        # 🔹 2. Pegar os dados do cliente vindos do form
        nome = request.POST.get("nome") or "Cliente sem nome"  # <- valor default
        whatsapp = request.POST.get("whatsapp") or "0000000000" # <- sempre precisa de algo único
        
        # 🔹 3. Criar ou recuperar cliente existente
        # - Usa `telefone` como identificador único
        # - Se já existe, retorna o objeto existente
        # - Se não existe, cria com defaults
        cliente, created = Cliente.objects.get_or_create(
            tenant=tenant,
            telefone=whatsapp,
            defaults={
                "nome": nome,
                "email": f"{whatsapp}@fake.com",     # Gera um email fake só pra preencher
                "senha": get_random_string(12),      # Gera senha aleatória
            },
        )

        # 🔹 4. Criar ordem (pedido principal)
        ordem = Ordem.objects.create(
            tenant=tenant,
            cliente=cliente,
            completo=False  # ainda não finalizado/pago
        )

        # 🔹 5. Recuperar carrinho da session
        # Estrutura esperada: {"produto_id": quantidade, ...}
        cart = request.session.get("cart", {})

        # Percorre os itens do carrinho e cria OrdemItem
        for produto_id, qtd in cart.items():
            produto = get_object_or_404(Produto, id=produto_id, tenant=tenant)
            OrdemItem.objects.create(
                tenant=tenant,
                ordem=ordem,
                produto=produto,
                quantidade=qtd
            )

        # 🔹 6. Criar endereço de entrega
        endereco_obj = EnderecoEntrega.objects.create(
            tenant=tenant,
            cliente=cliente,
            ordem=ordem,
            endereco=request.POST.get("endereco_rua"),
            referencia=request.POST.get("endereco_referencia"),
            cidade=request.POST.get("cidade"),
            cep = request.POST.get("endereco_cep"),
            endereco_bairro = request.POST.get("forma_entrega"),
            endereco_numero = request.POST.get("endereco_numero"),
            endereco_complemento = request.POST.get("endereco_complemento"),
        )

        # Monta dados do pedido para WhatsApp
        produtos = []
        subtotal = 0
        for item in ordem.ordemitem_set.all():
            valor = item.get_total
            produtos.append({
                'nome': item.produto.nome if item.produto else '',
                'referencia': item.produto.referencia if item.produto else '',
                'quantidade': item.quantidade,
                'valor': valor,
            })
            subtotal += valor
        
        # Obtém o telefone da loja
        telefone_loja = get_object_or_404(Tenant, subdomain=tenant).whatsapp

        pedido_info = {
            'loja': 'DUCK BURGER',
            'pedido_id': ordem.id,
            'datahora': ordem.dataHora.strftime('%d/%m/%Y às %H:%M'),
            'nome': cliente.nome,
            'whatsapp': cliente.telefone,
            'cep': endereco_obj.cep,
            'bairro': endereco_obj.endereco_bairro,
            'rua': endereco_obj.endereco,
            'complemento': endereco_obj.endereco_complemento,
            'referencia': endereco_obj.referencia,
            'produtos': produtos,
            'subtotal': subtotal,
            'entrega': endereco_obj.cidade,
            'pagamento': request.POST.get('forma_pagamento',''),
            'total': subtotal,  # ajuste se tiver taxa de entrega
            'telefone_loja': telefone_loja,
        
        }
        request.session['last_pedido_info'] = pedido_info

        # 🔹 7. Limpar carrinho da sessão
        request.session["cart"] = {}

    # 🔹 8. Registrar cookie com telefone do cliente e redirecionar
    response = redirect("checkout_sucesso")
    response.set_cookie('telefone_cliente', cliente.telefone, max_age=60*60*24*30)  # 30 dias
    return response


