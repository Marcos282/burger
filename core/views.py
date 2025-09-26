from django.shortcuts import render, HttpResponse, get_object_or_404
from menu.models import Produto, Category
from core.utils import formatar_brl 
from django.http import JsonResponse
from orders.models import Ordem, OrdemItem
from tenants.models import Tenant
import uuid


# Funções utilitárias de sessão
def get_cart(request):
    return request.session.get('cart', {})

def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True

def get_categorias(request):
    return  Category.objects.filter(tenant=request.tenant)   

def loja(request):

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
   context = {
         'produtos': produtos,
         'categorias': categorias,
         'cart_count': cart_count,     
    }

   return render(request, 'loja/index.html', context=context)



def detalhe(request,produto_id):

   produto = get_object_or_404(Produto, tenant=request.tenant, id=produto_id)
   produto.price = formatar_brl(produto.price)

    # Pega o carrinho da sessão
   cart = get_cart(request)
   cart_count = sum(cart.values())

   print(f" contador: {cart_count}")

   # Obtendo todas as categorias do tenant atual para exibir no menu categorias   
   categorias = get_categorias(request)
  
   context = {
      'produto' : produto,
      'categorias' : categorias,
      'cart_count': cart_count,
   }
   
   return render(request, 'loja/produto/detail.html', context)

# Sacola =====================================================================


################ CARRINHO #########################



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

         

        return JsonResponse({
            'status': 'ok',
            'produto': {
                'id': produto.id,
                'nome': produto.nome,
                'quantidade': cart[produto_id],
                'subtotal': f"{subtotal:.2f}"
            },
            'cart_count': sum(cart.values())
        })
    return JsonResponse({'status': 'error'}, status=400)


# Remover produto do carrinho ================================================
def remove_from_cart(request):
    if request.method == 'POST':
        produto_id = str(request.POST.get('produto_id'))
        cart = get_cart(request)
        if produto_id in cart:
            del cart[produto_id]
        save_cart(request, cart)
        return JsonResponse({'status': 'ok', 'cart': cart})
    return JsonResponse({'status': 'error'}, status=400)

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
      'total': total,
      'categorias':categorias,
      'cart_count':cart_count,
   }
 
   return render(request, 'loja/sacola.html', context)

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