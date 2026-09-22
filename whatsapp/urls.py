from django.urls import path

from . import views


urlpatterns = [
    path('', views.configuracao, name='painel_whatsapp_api'),
]
