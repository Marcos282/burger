# orders/models.py
from django.db import models
from tenants.models import Tenant
from menu.models import Produto


class Ordem(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    
    # Assumindo que o modelo Cliente está em um aplicativo chamado 'customers'
    cliente = models.ForeignKey("customers.Cliente", on_delete=models.SET_NULL, null=True, blank=True)
    dataHora = models.DateTimeField(auto_now_add=True)
    completo = models.BooleanField(default=False)
    transacao_id = models.CharField(max_length=100, null=True)

    def __str__(self):
        return str(self.id)

    @property
    def get_car_total(self):
        ordemitens = self.ordemitem_set.all()
        return sum([item.get_total for item in ordemitens])

    @property
    def get_car_itens(self):
        ordemitens = self.ordemitem_set.all()
        return sum([item.quantidade for item in ordemitens])
    

class OrdemItem(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.SET_NULL, null=True)
    ordem = models.ForeignKey(Ordem, on_delete=models.SET_NULL, null=True)
    quantidade = models.IntegerField(default=0, null=True, blank=True)
    dataHora = models.DateTimeField(auto_now_add=True)

    @property
    def get_total(self):
        if self.produto:
            return self.produto.price * self.quantidade
        return 0
    def __str__(self):
        return str(self.id) 