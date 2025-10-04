from customers.views_auth import login_view, register_view, painel_view, logout_view
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from django.urls import include
from core.views import (
    loja,
    detalhe,
    add_to_cart,
    sacola,
    checkout,
    remover_do_carrinho_ajax,
    atualizar_carrinho_ajax,
    checkout_sucesso,
)

from orders.views import pedido_delivery, cadastro_form


urlpatterns = [
    path('admin/', admin.site.urls),
    path('loja/', loja, name='loja'),
    path('loja/datail/<int:produto_id>', detalhe, name='detalhe'),
    path('add-to-cart/', add_to_cart, name='add_to_cart'),
    path('loja/sacola', sacola, name='sacola'),
    path('loja/checkout', checkout, name='finalizar_pedido'),
    path('carrinho/remover-ajax/', remover_do_carrinho_ajax, name='remover_do_carrinho_ajax'),
    path('atualizar-carrinho/', atualizar_carrinho_ajax, name='atualizar_carrinho_ajax'),
    path('pedido_delivery/', pedido_delivery, name='pedido_delivery'),
    path('cadastro_form',cadastro_form, name='cadastro_form'),
    path('checkout_sucesso/',checkout_sucesso, name='checkout_sucesso'),
    path('login/', login_view, name='login'),
    path('painel/', painel_view, name='painel'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('', RedirectView.as_view(url='/loja/')),  # redireciona a raiz
]


