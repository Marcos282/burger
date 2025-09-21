from django.db import models
from tenants.models import Tenant


class Cliente(models.Model):
    # Cada cliente pertence a um tenant específico
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    ENUM_GENERO = [
        ('M', 'Masculino'),
        ('F', 'Feminino')
    ]
    nome = models.CharField(max_length=200)
    senha = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    genero = models.CharField(choices=ENUM_GENERO, max_length=1, default='M')
    endereco = models.CharField(max_length=200, null=True, blank=True)
    referencia = models.CharField(max_length=200, null=True, blank=True)
    cidade = models.CharField(max_length=200, default='Brasília')
    telefone = models.CharField(max_length=200, null=True, blank=True)
    autenticado = models.BooleanField(default=False)

    def __str__(self):
        return self.nome + " (" + str(self.id) + ")"
    
    # Propriedade para retornar o adjetivo correto com base no gênero
    @property
    def adjetivo(self):
        return 'o' if self.genero == 'M' else 'a'


class EnderecoEntrega(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    # Pega o cliente e a ordem como strings para evitar importações circulares
    cliente = models.ForeignKey("customers.Cliente", on_delete=models.SET_NULL, null=True)
    ordem = models.ForeignKey("orders.Ordem", on_delete=models.SET_NULL, null=True)
    
    endereco = models.CharField(max_length=200, null=False)
    referencia = models.CharField(max_length=200, null=False)
    cidade = models.CharField(max_length=200, null=False)
    dataHora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.endereco
    class Meta:
        verbose_name = "Endereço de Entrega"
        verbose_name_plural = "Endereços de Entrega"