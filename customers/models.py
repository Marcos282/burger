from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from tenants.models import Tenant

# --- User customizado para multi-tenant ---
class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('O campo username é obrigatório')
        # Cria ou recupera o Tenant com subdomain igual ao username
        tenant, _ = Tenant.objects.get_or_create(subdomain=username, defaults={'name': username})
        user = self.model(username=username, tenant=tenant, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'customers_user'
    username = models.CharField(max_length=150, unique=True)
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        # Garante que o Tenant existe e está sincronizado
        if not self.tenant_id:
            tenant, _ = Tenant.objects.get_or_create(subdomain=self.username, defaults={'name': self.username})
            self.tenant = tenant
        else:
            # Atualiza o subdomain do tenant se username mudar 
            if self.tenant.subdomain != self.username:
                self.tenant.subdomain = self.username
                self.tenant.name = self.username
                self.tenant.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.username} ({self.tenant.subdomain})'
#customers/models.py
from django.db import models
from tenants.models import Tenant
from django.core.validators import RegexValidator


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
    cep = models.CharField(
    max_length=10,
    default="00000000",
    validators=[RegexValidator(regex='^[0-9-]+$', message='Apenas números e hífen são permitidos.')]
    )
    endereco_bairro = models.CharField(max_length=100, null=True, blank=True)
    endereco_numero = models.CharField(max_length=20, null=True, blank=True)
    endereco_complemento = models.CharField(max_length=100, null=True, blank=True)


    def __str__(self):
        return self.endereco
    class Meta:
        verbose_name = "Endereço de Entrega"
        verbose_name_plural = "Endereços de Entrega"