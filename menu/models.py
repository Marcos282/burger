#menu/models.py
from django.db import models
from tenants.models import Tenant

# Categoria de produto (lanches, bebidas, etc.)
class Category(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    exibir = models.BooleanField(default=False)

    def __str__(self):
        return f' {self.name} ({self.tenant})'

# Produtos do cardápio
class Produto(models.Model):
    
    # Pegando o tenant para multi-tenancy
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    nome = models.CharField(max_length=200)
    
    # Categoria do produto
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    image = models.ImageField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    price = models.FloatField()
    digital = models.BooleanField(default=False, null=True, blank=True)
    referencia = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
    
        if not self.referencia:
            self.referencia = f"REF-{uuid.uuid4().int % 1000000}"
        super().save(*args, **kwargs)  

    # Representação em string do produto
    def __str__(self):
        foto = ''
        try:
            foto = self.image.url
        except:
            foto = ''
        return self.nome + " (" + foto + ")"

    # Propriedade para obter a URL da imagem do produto
    @property
    def imageURL(self):
        try:
            url = self.image.url
        except:
            url = ''
        return url
