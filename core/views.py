from urllib import request
from django.shortcuts import render, HttpResponse, get_object_or_404
from menu.models import Produto, Category
from core.utils import formatar_brl, formatar_brl_noS
from django.http import JsonResponse
from orders.models import Ordem, OrdemItem
from customers.models import Cliente
from tenants.models import Tenant, TenantSettings
import uuid


# Funções utilitárias de sessão
def get_cart(request):
    return request.session.get('cart', {})

def get_qdt_prod(request):
    qtd_prod = get_cart(request)
    return len(qtd_prod)

def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True

def get_categorias(request):
    return  Category.objects.filter(tenant=request.tenant)   

def loja(request):
   qtd_prd = get_qdt_prod(request)
   categoria_id = request.GET.get("categoria_id")
   produtos = Produto.objects.none()

   if categoria_id is None:
 
      # Obtendo produtos do tenant atual
      produtos = Produto.objects.filter(
         tenant=request.tenant,
         category__exibir=True  # Filtra apenas categorias marcadas para exibir
      )
   else:
   
      # Se categoria_id for fornecido, filtra os produtos por essa categoria
      produtos = Produto.objects.filter(
         tenant=request.tenant,
         category__id=categoria_id  # Filtra apenas categorias marcadas para exibir
      )

   for produto in produtos:
      
       produto.preco_formatado = formatar_brl(produto.price)

   # Obtendo todas as categorias do tenant atual para exibir no menu categorias      
   categorias = get_categorias(request)
   # Pega o carrinho da sessão
   cart = request.session.get('cart', {})
   cart_count = sum(cart.values())
    
   telefone_cookie = request.COOKIES.get('telefone_cliente', '')
   nome_cliente = ''
   ordens_pendentes = 0

   if telefone_cookie:
        try:
            cliente = Cliente.objects.get(telefone=telefone_cookie)
            nome_cliente = cliente.nome
            ordens_pendentes = cliente.ordem_set.filter(completo=False).count()
        except Cliente.DoesNotExist:
            nome_cliente = ''
            ordens_pendentes = 0

    # Carrega configurações do tenant atual
   config = TenantSettings.load(tenant=request.tenant)

   if config.is_open_now():
    aberto = True
   else:
    aberto = False

   context = {
       'produtos': produtos,
       'categorias': categorias,
       'cart_count': cart_count,
       'qtd_prd': len(cart),
       'telefone_cookie': telefone_cookie,
       'nome_cliente': nome_cliente,
       'ordens_pendentes': ordens_pendentes,
       'config': config,
       'aberto': aberto,
    }
   print(f"Total>>>>> {get_qdt_prod(request)}")
   return render(request, 'loja/index.html', context=context)


#detalhe =====================================================================
def detalhe(request,produto_id):

   produto = get_object_or_404(Produto, tenant=request.tenant, id=produto_id)
   # formata para R$ 23,44
   valor_br = formatar_brl(produto.price)
   valor_br_semS = formatar_brl_noS(produto.price)

    # Pega o carrinho da sessão
   cart = get_cart(request)
   cart_count = sum(cart.values())

   print(f" contador: {cart_count}")

   # Obtendo todas as categorias do tenant atual para exibir no menu categorias   
   categorias = get_categorias(request)
  
   context = {
      'valor_sem_S' : valor_br_semS,
      'valor_br' : valor_br,
      'produto' : produto,
      'categorias' : categorias,
      'cart_count': cart_count,
      'tot_prod_cart' : len(cart),
   }
   
   return render(request, 'loja/produto/detail.html', context)



# Adicionar produto ao carrinho ===============================================
def add_to_cart(request):
        
    # Só aceita POST
    if request.method == 'POST':
        
        produto_id = request.POST.get('produto_id')
        quantidade = int(request.POST.get('quantidade', 1))

        # Pega o carrinho da sessão
        cart = cart = get_cart(request)

        # Adiciona ou atualiza quantidade
        if produto_id in cart:
            cart[produto_id] += quantidade
        else:
            cart[produto_id] = quantidade

        # Salva carrinho na sessão
        request.session['cart'] = cart
        request.session.modified = True

        # Debug: imprime tudo do carrinho
        print("=== DEBUG CARRINHO ===")
        #print(request.session.get('cart', {}))
        print(cart)

        for pid, qty in cart.items():
            try:
                produto = Produto.objects.get(id=pid)
                print(f"Produto: {produto.nome} (ID: {pid}), Quantidade: {qty}, Subtotal: R${produto.price * qty:.2f}")
            except Produto.DoesNotExist:
                print(f"Produto ID {pid} não existe mais! Quantidade: {qty}")
        print("=======================")

        # Retorna info do produto e total
        produto = Produto.objects.get(id=produto_id)
        subtotal = produto.price * cart[produto_id]

        qtd_pedidos = len(cart)         

        return JsonResponse({
            'status': 'ok',
            'produto': {
                'id': produto.id,
                'nome': produto.nome,
                'quantidade': cart[produto_id],
                'subtotal': f"{subtotal:.2f}"
            },
            'cart_count': sum(cart.values()),
            'qtd_pedidos' : qtd_pedidos
        })
    return JsonResponse({'status': 'error'}, status=400)


# Remover produto do carrinho ================================================

def remover_do_carrinho_ajax(request):
    if request.method == "POST":
        produto_id = request.POST.get("produto_id")
        carrinho = request.session.get("cart", {})

        if str(produto_id) in carrinho:
            del carrinho[str(produto_id)]
            request.session["cart"] = carrinho
            request.session.modified = True

        # Recalcula total do carrinho
        total = 0
        for pid, qtd in carrinho.items():
            p = get_object_or_404(Produto, id=pid)
            total += p.price * qtd

        return JsonResponse({
            "status": "ok",
            "cart_count": sum(carrinho.values()),
            "total": total
        })

    return JsonResponse({"status": "erro", "mensagem": "Requisição inválida."})

# Ver carrinho ================================================================
def sacola(request):
   cart = get_cart(request)
   cart_count = sum(cart.values())
   produtos = []
   total = 0
   for produto_id, qtd in cart.items():
      produto = get_object_or_404(Produto, id=produto_id)
      subtotal = produto.price * qtd
      total += subtotal
      produtos.append({
            'produto': produto,
            'quantidade': qtd,
            'subtotal': subtotal
        })

   categorias = get_categorias(request)
   context = {
      'produtos': produtos,
      'total': formatar_brl(total),
      'categorias':categorias,
      'cart_count':cart_count,
   }
 
   return render(request, 'loja/sacola.html', context)




def atualizar_carrinho_ajax(request):
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        produto_id = request.POST.get("produto_id")
        quantidade = request.POST.get("quantidade")

        try:
            quantidade = int(quantidade)
            produto = get_object_or_404(Produto, id=produto_id)
        except (ValueError, Produto.DoesNotExist):
            return JsonResponse({"status": "erro", "mensagem": "Produto inválido."})

        # Recupera carrinho da sessão
        carrinho = request.session.get("cart", {})

        if quantidade < 1:
            # Remove produto do carrinho se quantidade for menor que 1
            carrinho.pop(str(produto_id), None)
        else:
            # Atualiza quantidade
            carrinho[str(produto_id)] = quantidade

        request.session["cart"] = carrinho
        request.session.modified = True

        # Calcula subtotal do item e total do carrinho
        item_subtotal = produto.price * quantidade if quantidade > 0 else 0
        total = sum(get_object_or_404(Produto, id=pid).price * qtd for pid, qtd in carrinho.items())

        return JsonResponse({
            "status": "ok",
            "cart_count": sum(carrinho.values()),
            "item_subtotal": item_subtotal,
            "total": total
        })

    return JsonResponse({"status": "erro", "mensagem": "Requisição inválida."})


# Checkout ===================================================================
def checkout(request):
    if request.method == 'POST':
        tenant_id = request.POST.get('tenant_id')
        tenant = get_object_or_404(Tenant, id=tenant_id)
        cart = get_cart(request)

        if not cart:
            return JsonResponse({'status': 'error', 'message': 'Carrinho vazio'}, status=400)

        # Criar ordem temporária
        ordem = Ordem.objects.create(
            tenant=tenant,
            transacao_id=str(uuid.uuid4())[:8]
        )

        for produto_id, qtd in cart.items():
            produto = get_object_or_404(Produto, id=produto_id)
            OrdemItem.objects.create(
                tenant=tenant,
                ordem=ordem,
                produto=produto,
                quantidade=qtd
            )

        # Limpa o carrinho da sessão
        save_cart(request, {})

        return JsonResponse({'status': 'ok', 'ordem_id': ordem.id})
    
    # Se for GET, mostrar formulário de checkout (nome, email, endereço)
    return render(request, 'loja/checkout.html')

# Pedido Delivery ##########################################################



from django.utils.html import escape
import urllib.parse

def checkout_sucesso(request):
    # Recupera dados do último pedido salvo na sessão (ou personalize conforme sua lógica)
    pedido_info = request.session.get('last_pedido_info')
    if not pedido_info:
        return HttpResponse("<h1>Pedido finalizado</h1><p>Não foi possível montar o link do WhatsApp.</p>")

    # Monta mensagem para o WhatsApp
    mensagem = f"*{pedido_info.get('loja', 'DUCK BURGER')}*\n------\n*Pedido {pedido_info.get('pedido_id','')}*\n------\n{pedido_info.get('datahora','')}\n------\n*Nome:* {pedido_info.get('nome','')}\n*Whatsapp:* {pedido_info.get('whatsapp','')}\n*Endereços:* CEP: {pedido_info.get('cep','')}, Bairro: {pedido_info.get('bairro','')}, Rua: {pedido_info.get('rua','')}, Complemento: {pedido_info.get('complemento','')}, Referência: {pedido_info.get('referencia','')}\n------\n*PRODUTOS*\n------\n"
    for item in pedido_info.get('produtos', []):
        mensagem += f"*{item['quantidade']} x* #{item['referencia']} {item['nome']}\n*Valor:* R$ {item['valor']:.2f}\n------\n"
    mensagem += f"*Subtotal:* R$ {pedido_info.get('subtotal',0):.2f}\n*Entrega:* {pedido_info.get('entrega','')}\n------\n*Forma de pagamento:*\n{pedido_info.get('pagamento','')}\n*Total:* R$ {pedido_info.get('total',0):.2f}\n------\nhttps://site.cliente.com"

    mensagem_url = urllib.parse.quote(mensagem)
    telefone = pedido_info.get('telefone_loja','')

    link_whatsapp = f"https://api.whatsapp.com/send/?phone={telefone}&text={mensagem_url}&type=phone_number&app_absent=0"

    html = f"""
    <html><head>
    <meta http-equiv='refresh' content='5;url={link_whatsapp}' />
    <style>body{{text-align:center;font-family:sans-serif;}}</style>
    </head><body>
    <h1>Pedido finalizado com sucesso!</h1>
    <p>Você será redirecionado para o WhatsApp em 5 segundos...</p>
    <a href='{link_whatsapp}' target='_blank'>Clique aqui se não for redirecionado automaticamente</a>
    </body></html>
    """
    return HttpResponse(html)