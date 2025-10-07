from customers.views_auth import (
    login_view,
    register_view,
    painel_view,
    logout_view,
    painel_home,
    painel_categorias,
    painel_categorias_add,
    painel_categoria_delete,
    painel_categorias_edit,
    painel_produtos,
    painel_produtos_add,
    painel_produto_delete,
    painel_produtos_edit,
)
 
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from django.urls import include
from django.conf import settings
from django.conf.urls.static import static
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
    path('painel/pedidos', painel_view, name='painel_pedidos'),
    path('painel/home/', painel_home, name='painel_home'),
    path('painel/categorias/', painel_categorias, name='painel_categorias'),
    path('painel/categorias/adicionar/', painel_categorias_add, name='painel_categorias_add'),
    path('painel/categorias/deletar/<int:categoria_id>/', painel_categoria_delete, name='painel_categoria_delete'),
    path('painel/categorias/editar/<int:categoria_id>/', painel_categorias_edit, name='painel_categorias_edit'),
    path('painel/produtos/', painel_produtos, name='painel_produtos'),
    path('painel/produtos/adicionar/', painel_produtos_add, name='painel_produtos_add'),
    path('painel/produtos/deletar/<int:produto_id>/', painel_produto_delete, name='painel_produto_delete'),
    path('painel/produtos/editar/<int:produto_id>/', painel_produtos_edit, name='painel_produtos_edit'),
    path('logout/', logout_view, name='logout'), 
    path('register/', register_view, name='register'),
    path('', RedirectView.as_view(url='/loja/')),  # redireciona a raiz
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


