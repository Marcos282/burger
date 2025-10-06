from itertools import count
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, HttpResponse
from .forms import UserLoginForm, UserCreationForm
from orders.models import Ordem, OrdemItem
from customers.models import EnderecoEntrega, Cliente
from core.utils import formatar_brl

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
            return redirect('painel_pedidos')  
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
        print('Sessão do usuário:', dict(request.session))
        user = request.user
        print('Dados do usuário:', dict(username=user.username, email=user.email, id=user.id))

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
        print('Sessão do usuário:', dict(request.session))
        user = request.user
        print('Dados do usuário logado:', dict(username=user.username, password=user.password, email=user.email, id=user.id))
                        

        localizacao = "Home"
        context = {
            'localizacao': localizacao,
            'user': user,
            'qt_items_cliente': qt_items_cliente(request)
        }
        return render(request, 'painel/home.html', context)
    else:
        return redirect('login')

def logout_view(request):
    logout(request)
    return redirect('loja') 