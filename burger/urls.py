"""
URL configuration for burger project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from django.urls import include
from core.views import loja, detalhe, add_to_cart, sacola, checkout, remove_from_cart



urlpatterns = [
    path('admin/', admin.site.urls),
    path('loja/', loja, name='loja'),
    path('loja/datail/<int:produto_id>', detalhe, name='detalhe'),
    path('add-to-cart/', add_to_cart, name='add_to_cart'),
    path('loja/sacola', sacola, name='sacola'),
    path('loja/checkout', checkout, name='finalizar_pedido'),
    path('loja/remover_item/<int:produto_id>', remove_from_cart, name='remover_do_carrinho'),
    path('', RedirectView.as_view(url='/loja/')),  # redireciona a raiz
]