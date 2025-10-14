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
    dt_nascimento = models.DateField(null=True, blank=True)
    documento = models.CharField(max_length=20, blank=True, null=True)
    cpf_ou_cnpj = models.CharField(max_length=20, blank=True, null=True)
    nome_responsavel = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name
    
    def esta_aberto_agora(self, dt=None):
        """Verifica se o tenant está aberto no momento"""
        from datetime import datetime, date
        if dt is None:
            dt = datetime.now()
        
        dia_semana = dt.weekday()  # 0=segunda, 6=domingo
        hora_atual = dt.time()
        data_atual = dt.date()
        
        # Primeiro verifica se há horário especial para hoje
        horarios_especiais = self.horarios.filter(
            data_especifica=data_atual,
            ativo=True
        )
        
        if horarios_especiais.exists():
            return any(h.esta_no_horario(hora_atual) for h in horarios_especiais)
        
        # Se não há horário especial, verifica horário normal
        horarios_normais = self.horarios.filter(
            dia_semana=dia_semana,
            data_especifica=None,
            ativo=True
        )
        
        return any(h.esta_no_horario(hora_atual) for h in horarios_normais)
    
    def get_horarios_hoje(self, dt=None):
        """Retorna os horários de funcionamento para hoje"""
        from datetime import datetime
        if dt is None:
            dt = datetime.now()
        
        dia_semana = dt.weekday()
        data_atual = dt.date()
        
        # Primeiro verifica horários especiais
        horarios_especiais = self.horarios.filter(
            data_especifica=data_atual,
            ativo=True
        ).order_by('horario_abre')
        
        if horarios_especiais.exists():
            return horarios_especiais
        
        # Se não há horários especiais, retorna horários normais
        return self.horarios.filter(
            dia_semana=dia_semana,
            data_especifica=None,
            ativo=True
        ).order_by('horario_abre')
    
    def get_proximo_horario(self, dt=None):
        """Retorna informações sobre quando a loja abrirá novamente"""
        from datetime import datetime, timedelta
        if dt is None:
            dt = datetime.now()
        
        if self.esta_aberto_agora(dt):
            # Se está aberto, encontra quando fecha
            horarios_hoje = self.get_horarios_hoje(dt)
            hora_atual = dt.time()
            
            for horario in horarios_hoje:
                if horario.esta_no_horario(hora_atual):
                    if horario.is_overnight():
                        # Se é overnight, fecha no dia seguinte
                        return {
                            'acao': 'fecha',
                            'horario': horario.horario_fecha,
                            'data': dt.date() + timedelta(days=1)
                        }
                    else:
                        return {
                            'acao': 'fecha',
                            'horario': horario.horario_fecha,
                            'data': dt.date()
                        }
        
        # Se está fechado, encontra quando abre
        # Procura no resto de hoje
        horarios_hoje = self.get_horarios_hoje(dt)
        hora_atual = dt.time()
        
        for horario in horarios_hoje:
            if horario.horario_abre > hora_atual:
                return {
                    'acao': 'abre',
                    'horario': horario.horario_abre,
                    'data': dt.date()
                }
        
        # Se não abre mais hoje, procura nos próximos 7 dias
        for i in range(1, 8):
            data_futura = dt.date() + timedelta(days=i)
            dia_semana_futuro = (dt.weekday() + i) % 7
            
            horarios_futuros = self.horarios.filter(
                dia_semana=dia_semana_futuro,
                data_especifica=None,
                ativo=True
            ).order_by('horario_abre')
            
            if horarios_futuros.exists():
                return {
                    'acao': 'abre',
                    'horario': horarios_futuros.first().horario_abre,
                    'data': data_futura
                }
        
        return None

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
    complemento = models.CharField(max_length=100, blank=True, null=True)
    referencia = models.CharField(max_length=200, blank=True, null=True)
    foto_perfil = models.ImageField(upload_to='fotoperfil/', blank=True, null=True)
    foto_capa = models.ImageField(upload_to='fotocapa/', blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    color_theme = models.CharField(max_length=7, default="#DD7B0A")  # Hex color code
    tipo_catalogo = models.CharField(max_length=20, default="grid")  # "grid" ou "list"
    pagamento_minimo = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    debito = models.BooleanField(default=True)
    credito = models.BooleanField(default=True)
    pix = models.BooleanField(default=True)
    dinheiro = models.BooleanField(default=True)
    bandeiras_cartao_debito = models.CharField(max_length=200, blank=True, null=True, help_text="Ex: Visa, MasterCard")
    bandeiras_cartao_credito = models.CharField(max_length=200, blank=True, null=True, help_text="Ex: Visa, MasterCard, Amex")
    chave_pix = models.CharField(max_length=100, blank=True, null=True)
    nome_pix = models.CharField(max_length=100, blank=True, null=True)
    delivery = models.BooleanField(default=True)
    googleanalytics = models.CharField(max_length=100, blank=True, null=True, help_text="ID do Google Analytics")
    facebook_pixel = models.CharField(max_length=100, blank=True, null=True, help_text="ID do Facebook Pixel")
    instagram_pixel = models.CharField(max_length=100, blank=True, null=True, help_text="ID do Instagram Pixel")
    
    # Campos adicionais para o formulário
    subdomain = models.CharField(max_length=50, blank=True, null=True, help_text="Subdomínio da loja")
    segmento = models.CharField(max_length=50, blank=True, null=True, help_text="Segmento de negócio")
    exibicao_produtos = models.CharField(max_length=20, default="1", help_text="Tipo de exibição dos produtos")
    tipo_chave_pix = models.CharField(max_length=50, blank=True, null=True, help_text="Tipo da chave PIX")
    
    # Dados do responsável
    nome_responsavel = models.CharField(max_length=100, blank=True, null=True)
    dt_nascimento = models.DateField(blank=True, null=True)
    cpf_ou_cnpj = models.CharField(max_length=10, default="CPF", choices=[("CPF", "CPF"), ("CNPJ", "CNPJ")])
    documento = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    
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


class HorarioFuncionamento(models.Model):
    DIAS_SEMANA = [
        (0, 'Domingo'),
        (1, 'Segunda-feira'),
        (2, 'Terça-feira'),
        (3, 'Quarta-feira'),
        (4, 'Quinta-feira'),
        (5, 'Sexta-feira'),
        (6, 'Sábado'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    horario_abre = models.TimeField()
    horario_fecha = models.TimeField()
    ativo = models.BooleanField(default=True)
    
    # Campos opcionais para casos especiais
    data_especifica = models.DateField(null=True, blank=True, help_text="Para feriados/eventos específicos")
    descricao = models.CharField(max_length=100, blank=True, help_text="Ex: Feriado, Promoção especial")
    
    class Meta:
        unique_together = ['tenant', 'dia_semana', 'data_especifica']
        ordering = ['dia_semana', 'horario_abre']
        verbose_name = 'Horário de Funcionamento'
        verbose_name_plural = 'Horários de Funcionamento'
    
    def __str__(self):
        dia_nome = dict(self.DIAS_SEMANA)[self.dia_semana]
        if self.data_especifica:
            return f"{self.tenant.name} - {dia_nome} ({self.data_especifica}) - {self.horario_abre}-{self.horario_fecha}"
        return f"{self.tenant.name} - {dia_nome} - {self.horario_abre}-{self.horario_fecha}"
    
    def is_overnight(self):
        """Verifica se o horário atravessa a meia-noite"""
        return self.horario_abre > self.horario_fecha
    
    def esta_no_horario(self, hora_atual):
        """Verifica se uma hora específica está dentro do horário de funcionamento"""
        if self.is_overnight():
            return hora_atual >= self.horario_abre or hora_atual < self.horario_fecha
        else:
            return self.horario_abre <= hora_atual < self.horario_fecha