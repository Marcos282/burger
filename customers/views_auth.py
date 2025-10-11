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
from core.utils import formatar_brl, formatar_brl_to_float, build_full_url, get_tenant_url, build_tenant_url_for_user
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

        localizacao = [
            {"n1": "Pedidos", "url": "painel_pedidos"},
            
        ]

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
                'data_hora': ordem.dataHora.strftime('%d/%m/%Y %H:%M'),
            })

        
        context = {
            'localizacao': localizacao,
            'ordens_info': ordens_info,
            'url_marketplace': get_tenant_url(request, '/loja/'),
            
        }
        return render(request, 'painel/index.html', context)
    else:
        return redirect('login')


def painel_home(request):
    if request.user.is_authenticated:
       
        user = request.user

        localizacao = [
            {"n1": "Home", "url": "painel_home"}
        ]

        

        context = {
            'localizacao': localizacao,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request),
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/home.html', context)
    else:
        return redirect('login')


def painel_categorias(request): 
    if request.user.is_authenticated:
       
        user = request.user
                        
        localizacao = [
            {"n1": "Categorias", "url": "painel_categorias"},
           
        ]
        
        categoria = Category.objects.select_related('tenant').filter(tenant=user.tenant).order_by('ordem')
        qt_categoria = Category.objects.filter(tenant=user.tenant).count()

        
        url = get_tenant_url(request, '/loja/')
        print (f"URL do marketplace: {url}")

        context = {
            'localizacao': localizacao,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request),
            'categoria': categoria,
            'qt_categoria': qt_categoria,
            'marketplace_url': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/categorias.html', context)
    else:
        return redirect('login')


def painel_categorias_add(request): 
    if request.user.is_authenticated:
       
        user = request.user

        localizacao = [
            {"n1": "Categorias", "url": "painel_categorias"},
            {"n2": "Adicionar Categoria", "url": "painel_categorias_add"}
        ]

        
        
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
            'url_marketplace': get_tenant_url(request, '/loja/'),
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

        localizacao = [
            {"n1": "Categorias", "url": "painel_categorias"},
            {"n2": "Editar Categoria", "url": "painel_categorias_edit", "id": categoria.id}
            
        ]

        context = {
            'form': form,
            'user': user,
            'categoria': categoria,
            'localizacao': localizacao,
            'qt_items_cliente': qt_items_cliente(request),
            'show_edit_success_modal': show_edit_success_modal,
            'url_marketplace': get_tenant_url(request, '/loja/'),
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

        localizacao = [
            {"n1": "Produtos", "url": "painel_produtos"},
            
        ]
        context = {
            'localizacao': localizacao,
            'produtos': produtos,
            'messages': messages.get_messages(request),
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
        localizacao = [
            {"n1": "Produtos", "url": "painel_produtos"},
            {"n2": "Adicionar Produto", "url": "painel_produtos_add"}
        ]
        context = {
            'categorias': categorias,
            'localizacao': localizacao,
            'url_marketplace': get_tenant_url(request, '/loja/'),
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
    if request.user.is_authenticated:
        user = request.user
        produto = Produto.objects.filter(id=produto_id, tenant=getattr(user, 'tenant', None)).first()
        
        if not produto:
            messages.error(request, 'Produto não encontrado ou você não tem permissão para editá-lo.')
            return redirect('painel_produtos')

        galeria = ProdutoImagem.objects.filter(produto=produto).order_by('ordem')
        categorias = Category.objects.filter(tenant=user.tenant)
        
        show_edit_success_modal = False
        
        if request.method == 'POST':
            # Processa dados do formulário
            nome = request.POST.get('nome')
            categoria_id = request.POST.get('categoria')
            preco = formatar_brl_to_float(request.POST.get('preco', ''))
            ordem_exibicao = request.POST.get('ordem_exibicao')
            exibir = request.POST.get('exibir') == 'True'
            status = request.POST.get('status') == 'True'
            descricao = request.POST.get('description', '')
            integrado = request.POST.get('integrado') == 'True'
            
            # Validação básica
            if nome and categoria_id:
                try:
                    categoria = Category.objects.get(id=categoria_id, tenant=user.tenant)
                    
                    # Atualiza o produto
                    produto.nome = nome
                    produto.category = categoria
                    produto.price = preco
                    produto.ordem_exibicao = ordem_exibicao if ordem_exibicao else produto.ordem_exibicao
                    produto.exibir = exibir
                    produto.status = status
                    produto.description = descricao
                    produto.integrado = integrado
                    
                    # Verifica se deve remover a imagem principal
                    if request.POST.get('remover_imagem_extra') == 'true':
                        produto.imagem_extra = None
                    
                    produto.save()
                    
                    # Imagem principal (se uma nova foi enviada)
                    imagem_extra = request.FILES.get('imagem_extra')
                    if imagem_extra:
                        produto.imagem_extra = imagem_extra
                        produto.save()
                    
                    # Processa remoção de imagens selecionadas da galeria (checkboxes)
                    imagens_para_remover = request.POST.getlist('remover_galeria')
                    if imagens_para_remover:
                        print(f"Removendo {len(imagens_para_remover)} imagens da galeria (via checkbox)")
                        for img_id in imagens_para_remover:
                            try:
                                img_obj = ProdutoImagem.objects.get(id=img_id, produto=produto)
                                print(f"Removendo imagem: {img_obj.id} - {img_obj.imagem.name}")
                                img_obj.delete()
                            except ProdutoImagem.DoesNotExist:
                                print(f"Imagem com ID {img_id} não encontrada")
                        messages.success(request, f'{len(imagens_para_remover)} imagem(ns) removida(s) da galeria')
                    
                    # Processa remoção de imagens do Dropzone
                    imagens_removidas_dropzone = request.POST.get('imagens_removidas_dropzone', '')
                    if imagens_removidas_dropzone:
                        ids_removidos = [id.strip() for id in imagens_removidas_dropzone.split(',') if id.strip()]
                        print(f"Removendo {len(ids_removidos)} imagens da galeria (via Dropzone)")
                        for img_id in ids_removidos:
                            try:
                                img_obj = ProdutoImagem.objects.get(id=img_id, produto=produto)
                                print(f"Removendo imagem do Dropzone: {img_obj.id} - {img_obj.imagem.name}")
                                img_obj.delete()
                            except ProdutoImagem.DoesNotExist:
                                print(f"Imagem com ID {img_id} não encontrada")
                        messages.success(request, f'{len(ids_removidos)} imagem(ns) removida(s) do Dropzone')
                    
                    # Múltiplas imagens da galeria (se enviadas)
                    print("=== DEBUG GALERIA ===")
                    print(f"request.FILES completo: {dict(request.FILES)}")
                    print(f"request.FILES.keys(): {list(request.FILES.keys())}")
                    
                    # Busca todos os arquivos que começam com 'imagens'
                    imagens_galeria = []
                    for key, file_list in request.FILES.items():
                        if key.startswith('imagens'):
                            # Se é uma lista (como vem do MultiValueDict), pega o primeiro arquivo
                            if isinstance(file_list, list):
                                imagens_galeria.extend(file_list)
                            else:
                                imagens_galeria.append(file_list)
                    
                    print(f"Imagens da galeria encontradas: {len(imagens_galeria)} arquivos")
                    
                    # Processa apenas NOVAS imagens (com upload real de arquivo)
                    if imagens_galeria:
                        print(f"PROCESSANDO {len(imagens_galeria)} NOVAS imagens da galeria")
                        # Conta imagens existentes para continuar a ordem
                        existing_count = ProdutoImagem.objects.filter(produto=produto).count()
                        print(f"Existem {existing_count} imagens na galeria. Adicionando novas...")
                        
                        # Processa cada nova imagem (mantém as existentes)
                        for idx, img in enumerate(imagens_galeria):
                            # A ordem continua a partir das imagens existentes
                            nova_ordem = existing_count + idx
                            nova_img = ProdutoImagem.objects.create(produto=produto, imagem=img, ordem=nova_ordem)
                            print(f"Criada NOVA imagem da galeria {nova_ordem + 1}: {nova_img.id} - {img.name}")
                        
                        total_imagens = existing_count + len(imagens_galeria)
                        messages.success(request, f'{len(imagens_galeria)} nova(s) imagem(ns) adicionada(s)! Total na galeria: {total_imagens}')
                    else:
                        print("NENHUMA nova imagem da galeria recebida")
                    
                    show_edit_success_modal = True
                    messages.success(request, 'Produto atualizado com sucesso!')
                    
                except Category.DoesNotExist:
                    messages.error(request, 'Categoria não encontrada.')
            else:
                messages.error(request, 'Nome e categoria são obrigatórios.')
        
        # Formata preço para exibição
        produto.price = formatar_brl(produto.price)

        localizacao = [
                {"n1": "Produtos", "url": "painel_produtos"},
                {"n2": "Editar Produto", "url": "painel_produtos_edit", "id": produto.id}
            ]
        context = {
            'produto': produto,
            'localizacao': localizacao,
            'galeria': galeria,
            'categorias': categorias,
            'show_edit_success_modal': show_edit_success_modal,
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }

        return render(request, 'painel/produto_edit.html', context)
    else:
        return redirect('login')

def logout_view(request):
    logout(request)
    return redirect('login')