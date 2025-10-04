# tenants/models.py
from django.db import models
from django.core.exceptions import ValidationError

class SingletonModel(models.Model):
    """
    Base para models Singleton.
    Garante que só exista um registro.
    """
    class Meta:
        abstract = True
 
    def save(self, *args, **kwargs):
        if not self.pk and self.__class__.objects.exists():
            raise ValidationError("Já existe uma instância desse Singleton.")
        return super().save(*args, **kwargs)
 
    @classmethod  #Esse comando faz da função um metodo para ser chamado no objeto
    def load(cls):
        """
        Retorna a única instância, ou cria se não existir.
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj



class Tenant(models.Model):
    name = models.CharField(max_length=100)
    subdomain = models.CharField(max_length=50, unique=True)    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Configurações específicas do Tenant, como tema, cores, etc. É um Singleton por Tenant.
class TenantSettings(models.Model):
    
    
    # Horários de funcionamento (exemplo: 08:00 às 18:00)
    horario_abre = models.TimeField(default="08:00")
    horario_fecha = models.TimeField(default="18:00")

    # Dias da semana em que a loja está aberta (0=segunda, 6=domingo)
    dias_funcionamento = models.CharField(
        max_length=20,
        default="0,1,2,3,4,5,6",  # todos os dias por padrão
        help_text="Dias da semana abertos, separados por vírgula. 0=Segunda, 6=Domingo"
    )
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='settings')
    theme_color = models.CharField(max_length=7, default='#FFFFFF')  # Hex color code
    logo_url = models.URLField(blank=True, null=True)
    support_email = models.EmailField(blank=True, null=True)
    nome_loja = models.CharField(max_length=100, default='Minha Loja')
    descricao_loja = models.TextField(blank=True, null=True)
    whatsapp = models.CharField(max_length=20, default='21976857525')
    taxa_entrega = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    endereco = models.CharField(max_length=200, blank=True, null=True)
    numero_endereco = models.CharField(max_length=20, blank=True, null=True)
    bairro = models.CharField(max_length=100, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=100, blank=True, null=True)
    cep = models.CharField(max_length=20, blank=True, null=True)    

    # método para verificar se a loja está aberta em um dado momento
    def is_open_now(self, dt=None):
        """
        Retorna True se a loja está aberta no momento (ou no datetime dt).
        """
        from datetime import datetime, time
        if dt is None:
            dt = datetime.now()
        dia_semana = dt.weekday()  # 0=segunda, 6=domingo
        dias = [int(x) for x in self.dias_funcionamento.split(',') if x.strip().isdigit()]
        
        if dia_semana not in dias:
            return False
        hora_atual = dt.time()
        # Considera funcionamento normal (abre < fecha)
        if self.horario_abre < self.horario_fecha:
            return self.horario_abre <= hora_atual < self.horario_fecha
        # Considera funcionamento virando a meia-noite (ex: 22:00 às 06:00)
        else:
            return hora_atual >= self.horario_abre or hora_atual < self.horario_fecha

    def get_hora_fechamento_hoje(self, dt=None):
        """
        Retorna um objeto datetime.datetime representando até que horas a loja estará aberta HOJE.
        Se a loja fecha depois da meia-noite, retorna o horário de fechamento no dia seguinte.
        Se hoje não é dia de funcionamento, retorna None.
        """
        from datetime import datetime, timedelta
        if dt is None:
            dt = datetime.now()
        dia_semana = dt.weekday()  # 0=segunda, 6=domingo
        dias = [int(x) for x in self.dias_funcionamento.split(',') if x.strip().isdigit()]
        if dia_semana not in dias:
            return 'Não abre hoje'
        data_base = dt.date()
        # funcionamento normal (abre < fecha)
        if self.horario_abre < self.horario_fecha:
            return datetime.combine(data_base, self.horario_fecha)
        # funcionamento atravessa a meia-noite (ex: 22:00 às 06:00)
        else:
            # Se já passou da meia-noite, o fechamento é amanhã
            if dt.time() < self.horario_fecha:
                data_base = data_base
            else:
                data_base = data_base + timedelta(days=1)
            return datetime.combine(data_base, self.horario_fecha)

    @classmethod
    def load(cls, tenant):
        """
        Retorna a única instância, ou cria se não existir.
        """
        obj, created = cls.objects.get_or_create(tenant=tenant)
        return obj

    def __str__(self):
        return f"Settings for {self.tenant.name}"