from menu.models import Produto, ProdutoImagem, Category
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from itertools import count
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, HttpResponse
from .forms import UserLoginForm, UserCreationForm, CategoryModelForm
from orders.models import Ordem, OrdemItem
from customers.models import EnderecoEntrega, Cliente
from menu.models import Category, Produto, ProdutoImagem
from core.utils import formatar_brl, formatar_brl_to_float
from django.contrib import messages
from django.core.paginator import Paginator

# Função para contar itens do cliente
def qt_items_cliente(request):
    if request.user.is_authenticated:
        user = request.user
        count = Ordem.objects.filter(tenant=user.tenant).count()                
        return count
    return 0

def get_id_ordem_cliente(request):
    if request.user.is_authenticated:
        user = request.user
        id_ordem = Ordem.objects.filter(tenant=user.tenant)        
        return id_ordem
    return 0

def get_qt_ordem_cliente(request):
    if request.user.is_authenticated:
        user = request.user
        count = Ordem.objects.filter(tenant=user.tenant, cliente_id=user.id).count()        
        return count
    return 0

def login_view(request):

    form = UserLoginForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('painel_home')  
        else:
            error = 'Desculpe, parece que há alguns erros detectados, por favor tente novamente.'
    #return render(request, 'login/login.html', {'form': form, 'error': error})
    return render(request, 'login/demo1/dist/custom/pages/login/login-2.html', {'form': form, 'error': error})
    #return HttpResponse('Login page is under maintenance.')

def register_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('login')
    return render(request, 'register/register.html', {'form': form})

def painel_view(request):
    if request.user.is_authenticated:
        
        user = request.user
      
        localizacao = "Ultimos pedidos"

        # Buscar todas as ordens do tenant atual
        ordens = Ordem.objects.filter(tenant=user.tenant).select_related('cliente')

        

        ordens_info = []
        for ordem in ordens:
            qt_itens = OrdemItem.objects.filter(ordem=ordem).count()
            nome_cliente = ordem.cliente.nome if ordem.cliente else "-"
            telefone_cliente = ordem.cliente.telefone if ordem.cliente and hasattr(ordem.cliente, 'telefone') else "-"
            import re
            telefone_cliente_wa = re.sub(r'\D', '', telefone_cliente)
            valor = ordem.valor_total if ordem.valor_total is not None else 0
            tx_entrega = ordem.tx_entrega if ordem.tx_entrega is not None else 0
            valor_total_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            taxa_entrega_formatado = f"R${tx_entrega:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            itens_ordem_objs = OrdemItem.objects.filter(ordem=ordem)
            itens_ordem = []
            total_geral = 0
            for item in itens_ordem_objs:
                preco_unitario = float(item.preco_unitario) if item.preco_unitario is not None else 0.0
                quantidade = item.quantidade if item.quantidade is not None else 0
                amount = preco_unitario * quantidade
                itens_ordem.append({
                    'id': item.id,
                    'produto': item.produto,
                    'preco_unitario': preco_unitario,
                    'quantidade': quantidade,
                    'amount': amount,
                })
                total_geral = amount + total_geral

            endereco_entrega = EnderecoEntrega.objects.filter(ordem=ordem).first()
            dados_cliente = Cliente.objects.filter(id=ordem.cliente_id).first()
            #total_geral_formatado = f"R${total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ordens_info.append({
                'ordem': ordem,
                'qt_itens': qt_itens,
                'nome_cliente': nome_cliente,
                'telefone_cliente': telefone_cliente,
                'telefone_cliente_wa': telefone_cliente_wa,
                'valor_total_formatado': valor_total_formatado,
                'taxa_entrega_formatado': taxa_entrega_formatado,
                'itens_ordem': itens_ordem,
                'dados_cliente': dados_cliente,                                
                'endereco_entrega': endereco_entrega,
                'total_geral':  formatar_brl(total_geral),
            })

        
        
        context = {
            'localizacao': localizacao,
            'ordens_info': ordens_info,            
            
        }
        return render(request, 'painel/index.html', context)
    else:
        return redirect('login')


def painel_home(request):
    if request.user.is_authenticated:
       
        user = request.user
        
                        

        localizacao = "Home"
        context = {
            'localizacao': localizacao,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request)
        }
        return render(request, 'painel/home.html', context)
    else:
        return redirect('login')


def painel_categorias(request): 
    if request.user.is_authenticated:
       
        user = request.user
                        
        localizacao = "Categorias"
        
        categoria = Category.objects.select_related('tenant').filter(tenant=user.tenant).order_by('ordem')
        qt_categoria = Category.objects.filter(tenant=user.tenant).count()

        context = {
            'localizacao': localizacao,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request),
            'categoria': categoria,
            'qt_categoria': qt_categoria
        }
        return render(request, 'painel/categorias.html', context)
    else:
        return redirect('login')


def painel_categorias_add(request): 
    if request.user.is_authenticated:
       
        user = request.user
                           
        localizacao = "Adicionar Categoria"
        
        show_success_modal = False
        if str(request.method) == 'POST':
            form = CategoryModelForm(request.POST)
            if form.is_valid():
                nova_categoria = form.save(commit=False)
                nova_categoria.tenant = user.tenant
                nova_categoria.save()
                print(f"Teste do POST>>>> {nova_categoria.ordem}")
                show_success_modal = True
            else:
                show_success_modal = True
        else:
            form = CategoryModelForm()

        context = {
            'localizacao': localizacao,
            'form': form,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request),
            'show_success_modal': show_success_modal,
        }
        return render(request, 'painel/categorias_add.html', context)    
    else:
        return redirect('login')


def painel_categoria_delete(request, categoria_id):
    if request.user.is_authenticated:
        user = request.user
        categoria = Category.objects.filter(id=categoria_id, tenant=user.tenant).first()
        show_delete_modal = False
        if categoria:
            categoria.delete()
            show_delete_modal = True
        categoria_list = Category.objects.filter(tenant=user.tenant).order_by('name')
        qt_categoria = categoria_list.count()
        context = {
            'categoria': categoria_list,
            'qt_categoria': qt_categoria,
            'show_delete_modal': show_delete_modal,
            'user': user,
            'localizacao': 'Categorias',
            'qt_items_cliente': qt_items_cliente(request),
        }
        return render(request, 'painel/categorias.html', context)
    else:
        return redirect('login')


def painel_categorias_edit(request, categoria_id): 
    if request.user.is_authenticated:
        user = request.user
        categoria = Category.objects.filter(id=categoria_id, tenant=user.tenant).first()
        if not categoria:
            messages.error(request, 'Categoria não encontrada ou você não tem permissão para editá-la.')
            return redirect('painel_categorias')
        
        show_edit_success_modal = False
        if request.method == 'POST':
            form = CategoryModelForm(request.POST, instance=categoria)
            if form.is_valid():
                form.save()
                show_edit_success_modal = True
            # Não faz redirect, renderiza template com modal
        else:
            form = CategoryModelForm(instance=categoria)

        context = {
            'form': form,
            'user': user,
            'categoria': categoria,
            'localizacao': 'Editar Categoria',
            'qt_items_cliente': qt_items_cliente(request),
            'show_edit_success_modal': show_edit_success_modal,
        }
        return render(request, 'painel/categorias_edit.html', context)    
    else:
        return redirect('login')

def painel_produtos(request):
    if request.user.is_authenticated:
        from django.core.paginator import Paginator
        user = request.user
        produtos_list = Produto.objects.filter(tenant=user.tenant).order_by('-id')
        paginator = Paginator(produtos_list, 10)  # 10 produtos por página
        page_number = request.GET.get('page')
        produtos = paginator.get_page(page_number)

        localizacao = "Produtos"
        context = {
            'localizacao': localizacao,
            'produtos': produtos
        }

        return render(request, 'painel/produtos.html', context)
    else:
        return redirect('login')



def painel_produtos_add(request):
    user = request.user
    if request.method == 'POST':
        # Dados principais
        
        nome = request.POST.get('nome')
        categoria_id = request.POST.get('categoria')

        # Remove prefixo e formata para float
        preco = formatar_brl_to_float(request.POST.get('preco', ''))
        ordem = request.POST.get('ordem')
        exibir = request.POST.get('exibir') == 'True'
        status = request.POST.get('status') == 'True'
        descricao = request.POST.get('description', '')
        integrado = request.POST.get('integrado') == 'True'        
        tenant = getattr(request, 'tenant', None) or getattr(user, 'tenant', None)

        categoria = Category.objects.get(id=categoria_id)

        # Proteção contra múltiplos POSTs (ex: Dropzone autoProcessQueue)
        if not Produto.objects.filter(nome=nome, tenant=tenant, category=categoria, price=preco).exists():
            produto = Produto.objects.create(
                tenant=tenant,
                nome=nome,
                category=categoria,
                price=preco,
                exibir=exibir,
                status=status,
                integrado=integrado,
                description=descricao
            )
        else:
            produto = Produto.objects.filter(nome=nome, tenant=tenant, category=categoria, price=preco).latest('id')

        # Imagem extra :: Imagem Principal
        imagem_extra = request.FILES.get('imagem_extra')
        if imagem_extra:
            produto.imagem_extra = imagem_extra
            produto.save()
        print("FILES:", request.FILES)
        # Múltiplas imagens
        # Pega todos os arquivos que começam com 'imagens['
        imagens = [file for key, file in request.FILES.items() if key.startswith('imagens[')]
        for idx, img in enumerate(imagens):
            ProdutoImagem.objects.create(produto=produto, imagem=img, ordem=idx)

        return redirect('painel_produtos')
    else:
        categorias = Category.objects.filter(tenant=user.tenant)
        localizacao = 'Adicionar Produto'
        context = {
            'categorias': categorias,
            'localizacao': localizacao,
        }
        return render(request, 'painel/produtos_add.html', context)
            
		
@csrf_exempt
def painel_produto_delete(request, produto_id):
    if request.method == 'POST':
        user = request.user
        from menu.models import Produto
        produto = Produto.objects.filter(id=produto_id, tenant=getattr(user, 'tenant', None)).first()
        if produto:
            produto.delete()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Produto não encontrado.'}, status=404)
    return JsonResponse({'success': False, 'error': 'Método não permitido.'}, status=405)


def painel_produtos_edit(request, produto_id):
    user = request.user
    produto = Produto.objects.filter(id=produto_id, tenant=getattr(user, 'tenant', None)).first()

    galeria = ProdutoImagem.objects.filter(produto=produto).order_by('ordem')
    categorias = Category.objects.filter(tenant=user.tenant)
    produto.price = formatar_brl(produto.price)

    context = {
        'produto': produto,
        'localizacao': 'Editar Produto',
        'galeria': galeria,
        'categorias': categorias
    }

    return render(request, 'painel/produto_edit.html', context)

def logout_view(request):
    logout(request)
    return redirect('loja')