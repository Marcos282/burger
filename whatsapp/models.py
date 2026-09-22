from django.db import models

from orders.models import Ordem
from tenants.models import Tenant


class MensagemAutomatica(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='mensagens_whatsapp')
    status_pedido = models.CharField(max_length=20, choices=Ordem.Status.choices)
    ativa = models.BooleanField(default=True)
    mensagem = models.TextField(max_length=1000)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'status_pedido'],
                name='whatsapp_mensagem_unica_por_tenant_status',
            ),
        ]
        ordering = ['id']

    def __str__(self):
        return f'{self.tenant} — {self.get_status_pedido_display()}'
