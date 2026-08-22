from django.urls import path
from . import views

urlpatterns = [
    path('', views.pagamento, name='pagamento'),
    path('callback', views.pagamento_callback, name='pagamento_callback'),
]