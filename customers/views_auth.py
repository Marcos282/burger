from menu.models import Produto, ProdutoImagem, Category, Banners
from tenants.models import Tenant
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from itertools import count
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.shortcuts import render, redirect, HttpResponse
from .forms import UserLoginForm, UserCreationForm, CategoryModelForm
from orders.models import Ordem, OrdemItem
from customers.models import EnderecoEntrega, Cliente
from menu.models import Category, Produto, ProdutoImagem
from core.utils import formatar_brl, formatar_brl_to_float, build_full_url, get_tenant_url, build_tenant_url_for_user, verificar_loja_aberta
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
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        
        print(f"🔐 Tentativa de login: {email}")
        
        # Autenticar usando email (que agora é o USERNAME_FIELD)
        user = authenticate(request, username=email, password=password)
        if user is not None:
            print(f"✅ Login bem-sucedido para: {user.email}")
            login(request, user)
            return redirect('painel_home')  
        else:
            print(f"❌ Falha no login para: {email}")
            error = 'Email ou senha incorretos. Tente novamente.'
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
        ordens_pendentes_count = ordens.filter(completo=False).count()

        

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
            'ordens_pendentes_count': ordens_pendentes_count,
            'url_marketplace': get_tenant_url(request, '/loja/'),
            
        }
        return render(request, 'painel/index.html', context)
    else:
        return redirect('login')


def painel_pedidos_pendentes_count(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'unauthorized'}, status=401)

    user = request.user
    pendentes = Ordem.objects.filter(tenant=user.tenant, completo=False).count()
    return JsonResponse({'pendentes': pendentes})


def painel_home(request):
    if request.user.is_authenticated:
        
        status_loja = verificar_loja_aberta(request)
        print(f"Status da loja: {status_loja['status_texto']} - Aberta: {status_loja['aberta']}")

        user = request.user

        localizacao = [
            {"n1": "Home", "url": "painel_home"}
        ]

        

        context = {
            'localizacao': localizacao,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request),
            'url_marketplace': get_tenant_url(request, '/loja/'),
            'status_loja': status_loja,
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
                tenant = getattr(request, 'tenant', None) or getattr(user, 'tenant', None)
                if tenant is None:
                    messages.error(request, 'Tenant não identificado para criar categoria.')
                    return redirect('painel_categorias')

                nova_categoria = form.save(commit=False)
                nova_categoria.tenant = tenant
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

def painel_configuracao(request):
    if request.user.is_authenticated:
        user = request.user
        
        # Obter configurações do tenant
        from tenants.models import TenantSettings, HorarioFuncionamento
        from datetime import time
        import json
        
        tenant = user.tenant
        settings = TenantSettings.load(tenant)
        
        if request.method == 'POST':
            try:
                print(f"POST data received: {dict(request.POST)}")  # Debug
                
                # ==== STEP 1: DADOS GERAIS ====
                if 'name' in request.POST:
                    settings.nome_loja = request.POST['name']
                if 'descricao_loja' in request.POST:
                    settings.descricao_loja = request.POST['descricao_loja']
                if 'subdomain' in request.POST:
                    settings.subdomain = request.POST['subdomain']
                if 'CEP' in request.POST:
                    settings.cep = request.POST['CEP']
                if 'bairro' in request.POST:
                    settings.bairro = request.POST['bairro']
                if 'endereco' in request.POST:
                    settings.endereco = request.POST['endereco']
                if 'numero_endereco' in request.POST:
                    settings.numero_endereco = request.POST['numero_endereco']
                if 'complemento' in request.POST:
                    settings.complemento = request.POST['complemento']
                if 'referencia' in request.POST:
                    settings.referencia = request.POST['referencia']
                if 'estado' in request.POST:
                    settings.estado = request.POST['estado']
                if 'cidade' in request.POST:
                    settings.cidade = request.POST['cidade']
                if 'segmento' in request.POST:
                    settings.segmento = request.POST['segmento']
                
                # ==== STEP 2: APARÊNCIA ====
                if 'foto_perfil' in request.FILES:
                    settings.foto_perfil = request.FILES['foto_perfil']
                if 'foto_capa' in request.FILES:
                    settings.foto_capa = request.FILES['foto_capa']
                if 'color_theme' in request.POST:
                    settings.color_theme = request.POST['color_theme']
                if 'delivery' in request.POST:
                    settings.exibicao_produtos = request.POST['delivery']
                
                # ==== STEP 3: PAGAMENTO ====
                if 'pagamento_minimo' in request.POST:
                    pagamento_minimo_value = request.POST['pagamento_minimo'].strip()
                    print(f"pagamento_minimo raw value: '{request.POST['pagamento_minimo']}'")  # Debug
                    print(f"pagamento_minimo stripped: '{pagamento_minimo_value}'")  # Debug
                    if pagamento_minimo_value:
                        try:
                            # Remove caracteres não numéricos exceto vírgula e ponto
                            pagamento_minimo_value = pagamento_minimo_value.replace('R$', '').replace('.', '').replace(',', '.')
                            settings.pagamento_minimo = float(pagamento_minimo_value)
                            print(f"pagamento_minimo converted: {settings.pagamento_minimo}")  # Debug
                        except (ValueError, TypeError) as e:
                            print(f"Error converting pagamento_minimo: {e}")  # Debug
                            settings.pagamento_minimo = 0.0
                    else:
                        settings.pagamento_minimo = 0.0
                        print(f"pagamento_minimo empty, set to 0.0")  # Debug
                else:
                    print(f"pagamento_minimo not in POST data")  # Debug
                if 'dinheiro' in request.POST:
                    settings.dinheiro = request.POST['dinheiro'] == 'True'
                if 'debito' in request.POST:
                    settings.debito = request.POST['debito'] == 'True'
                if 'bandeiras_cartao_debito' in request.POST:
                    settings.bandeiras_cartao_debito = request.POST['bandeiras_cartao_debito']
                if 'credito' in request.POST:
                    settings.credito = request.POST['credito'] == 'True'
                if 'bandeiras_cartao_credito' in request.POST:
                    settings.bandeiras_cartao_credito = request.POST['bandeiras_cartao_credito']
                if 'pix' in request.POST:
                    settings.pix = request.POST['pix'] == 'True'
                if 'chave_pix' in request.POST:
                    settings.chave_pix = request.POST['chave_pix']
                if 'nome_pix' in request.POST:
                    settings.nome_pix = request.POST['nome_pix']
                
                # ==== STEP 4: HORÁRIOS DE FUNCIONAMENTO ====
                for dia in range(7):  # 0 = domingo, 1 = segunda, ..., 6 = sábado
                    fechado_key = f'fechado_{dia}'
                    abertura_key = f'horario_abertura_{dia}'
                    fechamento_key = f'horario_fechamento_{dia}'
                    
                    fechado = fechado_key in request.POST
                    horario_abertura = request.POST.get(abertura_key, '').strip()
                    horario_fechamento = request.POST.get(fechamento_key, '').strip()
                    
                    if not fechado and horario_abertura and horario_fechamento:
                        # Buscar ou criar horário para este dia
                        horario, created = HorarioFuncionamento.objects.get_or_create(
                            tenant=tenant,
                            dia_semana=dia,
                            data_especifica=None,
                            defaults={
                                'horario_abre': time.fromisoformat(horario_abertura),
                                'horario_fecha': time.fromisoformat(horario_fechamento),
                                'ativo': True,
                            }
                        )
                        
                        if not created:
                            # Atualizar horário existente
                            horario.horario_abre = time.fromisoformat(horario_abertura)
                            horario.horario_fecha = time.fromisoformat(horario_fechamento)
                            horario.ativo = True
                            horario.save()
                    else:
                        # Se marcado como fechado ou não tem horários, desativar ou remover
                        HorarioFuncionamento.objects.filter(
                            tenant=tenant,
                            dia_semana=dia, 
                            data_especifica=None
                        ).delete()
                
                # Delivery config from step 4
                if 'delivery' in request.POST:
                    settings.delivery = request.POST['delivery'] == 'True'
                
                # ==== STEP 5: CONTATOS ====
                if 'whatsapp' in request.POST:
                    settings.whatsapp = request.POST['whatsapp']
                if 'facebook' in request.POST:
                    settings.facebook = request.POST['facebook']
                if 'instagram' in request.POST:
                    settings.instagram = request.POST['instagram']
                if 'googleanalytics' in request.POST:
                    settings.googleanalytics = request.POST['googleanalytics']
                if 'facebook_pixel' in request.POST:
                    settings.facebook_pixel = request.POST['facebook_pixel']
                if 'instagram_pixel' in request.POST:
                    settings.instagram_pixel = request.POST['instagram_pixel']
                
                # ==== STEP 6: RESPONSÁVEL E AUTENTICAÇÃO ====
                if 'nome_responsavel' in request.POST:
                    settings.nome_responsavel = request.POST['nome_responsavel']
                if 'dt_nascimento' in request.POST:
                    settings.dt_nascimento = request.POST['dt_nascimento']
                if 'cpf_ou_cnpj' in request.POST:
                    settings.cpf_ou_cnpj = request.POST['cpf_ou_cnpj']
                if 'documento' in request.POST:
                    settings.documento = request.POST['documento']
                
                # ATUALIZAR EMAIL DO USUÁRIO (não do tenant settings)
                if 'email' in request.POST and request.POST['email']:
                    user.email = request.POST['email']
                    user.save()
                    print(f"🔄 Email do usuário atualizado para: {user.email}")
                
                # ATUALIZAR SENHA DO USUÁRIO (CRIPTOGRAFADA)
                if 'password' in request.POST and request.POST['password']:
                    password = request.POST['password']
                    confirm_password = request.POST.get('confirm_password', '')
                    
                    print(f"🔐 Processando atualização de senha...")
                    print(f"    Senha fornecida: {'*' * len(password)} (tamanho: {len(password)})")
                    print(f"    Confirmação: {'*' * len(confirm_password)} (tamanho: {len(confirm_password)})")
                    
                    # Validação das senhas (redundante com frontend, mas importante para segurança)
                    if password != confirm_password:
                        print(f"❌ Erro: Senhas não coincidem")
                        return JsonResponse({
                            'success': False,
                            'message': 'As senhas não coincidem!'
                        })
                    
                    # Validação de força mínima da senha
                    if len(password) < 6:
                        print(f"⚠️ Aviso: Senha muito fraca (menos de 6 caracteres)")
                        # Permitir, mas avisar (pode ser mudado para bloquear se necessário)
                    
                    # Obter hash da senha antes da atualização (para comparação)
                    old_password_hash = user.password
                    print(f"    Hash anterior: {old_password_hash[:50]}...")
                    
                    # SALVAR SENHA CRIPTOGRAFADA NO MODELO USER
                    user.set_password(password)  # Este método já criptografa a senha
                    user.save()
                    
                    # 🔄 MANTER USUÁRIO LOGADO APÓS MUDANÇA DE SENHA
                    # Atualiza o hash de autenticação da sessão para evitar logout automático
                    update_session_auth_hash(request, user)
                    
                    # Verificar se o hash mudou
                    new_password_hash = user.password
                    print(f"    Hash novo: {new_password_hash[:50]}...")
                    print(f"🔒 Senha do usuário atualizada e criptografada com sucesso")
                    print(f"    Hash alterado: {old_password_hash != new_password_hash}")
                    print(f"🔐 Sessão mantida ativa após mudança de senha")
                    
                    # Verificar se a senha funciona
                    senha_verifica = user.check_password(password)
                    print(f"    Verificação da senha: {senha_verifica}")
                
                # Não salvar senha no TenantSettings (remover do modelo se existir)
                # A senha deve estar apenas no modelo User
                print(f"Attempting to save settings...")  # Debug
                settings.save()
                print(f"Settings saved successfully!")  # Debug
                
                return JsonResponse({
                    'success': True,
                    'message': 'Configurações salvas com sucesso!'
                })
                
            except Exception as e:
                import traceback
                print(f"Error saving settings: {str(e)}")  # Debug
                print(f"Traceback: {traceback.format_exc()}")  # Debug
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao salvar configurações: {str(e)}'
                })

        # Obter horários existentes para pré-carregar no formulário
        horarios_existentes = {}
        horarios = HorarioFuncionamento.objects.filter(tenant=tenant, data_especifica=None, ativo=True)
        for horario in horarios:
            horarios_existentes[horario.dia_semana] = {
                'fechado': False,
                'abertura': horario.horario_abre.strftime('%H:%M') if horario.horario_abre else '',
                'fechamento': horario.horario_fecha.strftime('%H:%M') if horario.horario_fecha else '',
            }
        
        # Para dias sem horário definido, marcar como fechado
        for dia in range(7):
            if dia not in horarios_existentes:
                horarios_existentes[dia] = {
                    'fechado': True,
                    'abertura': '',
                    'fechamento': '',
                }

        # Preparar dados do settings para JavaScript (pre-selecionar campos)
        settings_data = {
            'estado': settings.estado or '',
            'cidade': settings.cidade or '',
            'segmento': settings.segmento or '7',  # Padrão: Comércio em Geral
            'exibicao_produtos': settings.exibicao_produtos or '1',
            'dinheiro': settings.dinheiro if settings.dinheiro is not None else True,
            'debito': settings.debito if settings.debito is not None else True,
            'credito': settings.credito if settings.credito is not None else True,
            'pix': settings.pix if settings.pix is not None else True,
            'nome_pix': settings.nome_pix or 'CPF',
            'delivery': settings.delivery if settings.delivery is not None else True,
            'cpf_ou_cnpj': settings.cpf_ou_cnpj or 'CPF',
            'color_theme': settings.color_theme or '#ff0000',
        }

        localizacao = [
            {"n1": "Configuração", "url": "painel_configuracao"}
        ]

        context = {
            'localizacao': localizacao,
            'user': user,
            'settings': settings,
            'settings_data': json.dumps(settings_data),
            'horarios_existentes': json.dumps(horarios_existentes),
            'qt_items_cliente': qt_items_cliente(request),
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/configuracao.html', context)
    else:
        return redirect('login')

def upload_foto_perfil(request):
    """View específica para upload da foto de perfil via Dropzone"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Usuário não autenticado'})
    
    if request.method == 'POST' and 'foto_perfil' in request.FILES:
        try:
            from tenants.models import TenantSettings
            
            tenant = request.user.tenant
            settings = TenantSettings.load(tenant)
            settings.foto_perfil = request.FILES['foto_perfil']
            settings.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Foto de perfil atualizada com sucesso!',
                'url': settings.foto_perfil.url
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao salvar foto: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Nenhum arquivo enviado'})

def upload_foto_capa(request):
    """View específica para upload da foto de capa via Dropzone"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Usuário não autenticado'})
    
    # Debug: listar arquivos recebidos
    print("=== DEBUG UPLOAD FOTO CAPA ===")
    print(f"Method: {request.method}")
    print(f"FILES: {list(request.FILES.keys())}")
    print(f"POST: {list(request.POST.keys())}")
    
    if request.method == 'POST':
        if 'foto_capa' in request.FILES:
            try:
                from tenants.models import TenantSettings
                
                tenant = request.user.tenant
                settings = TenantSettings.load(tenant)
                settings.foto_capa = request.FILES['foto_capa']
                settings.save()
                
                print(f"Foto de capa salva com sucesso: {settings.foto_capa.url}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Foto de capa atualizada com sucesso!',
                    'url': settings.foto_capa.url
                })
            except Exception as e:
                print(f"Erro ao salvar foto de capa: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao salvar foto: {str(e)}'
                })
        else:
            print("Campo 'foto_capa' não encontrado nos arquivos")
            return JsonResponse({'success': False, 'message': 'Campo foto_capa não encontrado'})
    
    return JsonResponse({'success': False, 'message': 'Método não permitido'})

def painel_qrcode(request):
    if request.user.is_authenticated:
        import qrcode
        from io import BytesIO
        import base64

        user = request.user
        tenant = user.tenant
        settings = tenant.settings

        loja_url = get_tenant_url(request, '/loja/')

        # Gera QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(loja_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Converte imagem para base64 para embutir no HTML
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        localizacao = [
            {"n1": "QR Code", "url": "painel_qrcode"}
        ]

        context = {
            'localizacao': localizacao,
            'user': user,
            'settings': settings,
            'loja_url': loja_url,
            'qr_code_base64': img_str,
            'qt_items_cliente': qt_items_cliente(request),
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/qrcode.html', context)
    else:
        return redirect('login')
    
def painel_banners(request):
    if request.user.is_authenticated:
        user = request.user        
        banners = Banners.objects.filter(tenant=user.tenant).order_by('ordem_exibicao')
        qt_banners = banners.count()
        localizacao = [
            {"n1": "Banners", "url": "painel_banners"}
        ]
        
        show_success_modal = False
        if request.method == 'POST':
            titulo = request.POST.get('titulo', '')
            link = request.POST.get('link', '')
            ordem_exibicao = request.POST.get('ordem_exibicao', 0)
            image = request.FILES.get('image', None)
            
            if titulo and image:
                novo_banner = Banners.objects.create(
                    tenant=user.tenant,
                    titulo=titulo,
                    link=link,
                    ordem_exibicao=ordem_exibicao,
                    image=image
                )
                show_success_modal = True
        
        context = {
            'localizacao': localizacao,
            'banners': banners,
            'user': user,
            'qt_banners': qt_banners,
            'show_success_modal': show_success_modal,
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/banners.html', context)
    else:
        return redirect('login')

def painel_banners_add(request):
    if request.user.is_authenticated:
        user = request.user        
        localizacao = [
            {"n1": "Banners", "url": "painel_banners"},
            {"n2": "Adicionar Banner", "url": "painel_banners_add"}
        ]
        
        # Processar POST - salvar banner
        if request.method == 'POST':
            try:
                # Capturar dados do formulário
                titulo = request.POST.get('titulo', '').strip()
                link = request.POST.get('link', '').strip()
                ativo = request.POST.get('ativo') == 'on'
                ordem_exibicao = int(request.POST.get('ordem_exibicao', 1))
                
                # Validações básicas
                if not titulo:
                    messages.error(request, 'O título é obrigatório.')
                    return render(request, 'painel/banners_add.html', {
                        'localizacao': localizacao,
                        'user': user,
                        'url_marketplace': get_tenant_url(request, '/loja/'),
                        'error': 'O título é obrigatório.'
                    })
                
                # Capturar arquivos de imagem
                banner_pc = request.FILES.get('banner_pc')
                banner_mobile = request.FILES.get('banner_mobile')
                
                # Verificar se pelo menos uma imagem foi enviada
                if not banner_pc and not banner_mobile:
                    messages.error(request, 'É necessário enviar pelo menos uma imagem (PC ou Mobile).')
                    return render(request, 'painel/banners_add.html', {
                        'localizacao': localizacao,
                        'user': user,
                        'url_marketplace': get_tenant_url(request, '/loja/'),
                        'error': 'É necessário enviar pelo menos uma imagem (PC ou Mobile).'
                    })
                
                # Criar novo banner
                banner = Banners(
                    tenant=user.tenant,
                    titulo=titulo,
                    link=link if link else None,
                    ativo=ativo,
                    ordem_exibicao=ordem_exibicao
                )
                
                # Adicionar imagens se fornecidas
                if banner_pc:
                    banner.banner_pc = banner_pc
                if banner_mobile:
                    banner.banner_mobile = banner_mobile
                
                # Salvar no banco
                banner.save()
                
                # Mensagem de sucesso
                messages.success(request, f'Banner "{titulo}" criado com sucesso!')
                
                # Redirecionar para listagem de banners
                return redirect('painel_banners')
                
            except ValueError as e:
                messages.error(request, 'Erro nos dados fornecidos. Verifique os campos numéricos.')
                return render(request, 'painel/banners_add.html', {
                    'localizacao': localizacao,
                    'user': user,
                    'url_marketplace': get_tenant_url(request, '/loja/'),
                    'error': 'Erro nos dados fornecidos. Verifique os campos numéricos.'
                })
            except Exception as e:
                messages.error(request, f'Erro ao salvar banner: {str(e)}')
                return render(request, 'painel/banners_add.html', {
                    'localizacao': localizacao,
                    'user': user,
                    'url_marketplace': get_tenant_url(request, '/loja/'),
                    'error': f'Erro ao salvar banner: {str(e)}'
                })
        
        # GET - exibir formulário
        context = {
            'localizacao': localizacao,
            'user': user,
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/banners_add.html', context)
    else:
        return redirect('login')


def painel_banners_delete(request, banner_id):
    if request.method == 'POST':
        user = request.user
        banner = Banners.objects.filter(id=banner_id, tenant=getattr(user, 'tenant', None)).first()
        if banner:
            banner.delete()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Banner não encontrado.'}, status=404)
    return JsonResponse({'success': False, 'error': 'Método não permitido.'}, status=405)

def painel_banners_edit(request, banner_id):
    if request.user.is_authenticated:
        user = request.user
        banner = Banners.objects.filter(id=banner_id, tenant=getattr(user, 'tenant', None)).first()
        
        if not banner:
            messages.error(request, 'Banner não encontrado ou você não tem permissão para editá-lo.')
            return redirect('painel_banners')
        
        show_success_modal = False
        
        if request.method == 'POST':
            titulo = request.POST.get('titulo', '').strip()
            link = request.POST.get('link', '').strip()
            ativo = request.POST.get('ativo') == 'on'
            ordem_exibicao = int(request.POST.get('ordem_exibicao', 1))
            
            if not titulo:
                messages.error(request, 'O título é obrigatório.')
                return redirect('painel_banners_edit', banner_id=banner.id)
            
            banner.titulo = titulo
            banner.link = link if link else None
            banner.ativo = ativo
            banner.ordem_exibicao = ordem_exibicao
            
            # Verifica se novas imagens foram enviadas
            banner_pc = request.FILES.get('banner_pc')
            banner_mobile = request.FILES.get('banner_mobile')
            
            if banner_pc:
                banner.banner_pc = banner_pc
            if banner_mobile:
                banner.banner_mobile = banner_mobile
            
            banner.save()
            show_success_modal = True
            messages.success(request, f'Banner "{titulo}" atualizado com sucesso!')
        
        localizacao = [
            {"n1": "Banners", "url": "painel_banners"},
            {"n2": "Editar Banner", "url": "painel_banners_edit", "id": banner.id}
        ]
        
        context = {
            'localizacao': localizacao,
            'banner': banner,
            'user': user,
            'show_success_modal': show_success_modal,
            'url_marketplace': get_tenant_url(request, '/loja/'),
        }
        return render(request, 'painel/banners_edit.html', context)
    else:
        return redirect('login')

def logout_view(request):
    logout(request)
    return redirect('login')