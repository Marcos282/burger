from django.utils import timezone
from datetime import timedelta


def estender_expiracao(user, dias=30):
    """Soma `dias` à data de expiração do usuário, chamado quando o cliente realiza um pagamento."""
    base = user.data_expiracao if user.data_expiracao and user.data_expiracao > timezone.now() else timezone.now()
    user.data_expiracao = base + timedelta(days=dias)
    user.save(update_fields=['data_expiracao'])
    return user.data_expiracao


def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace('.', ',')

def formatar_brl_noS(valor):
    return f"{valor:,.2f}".replace('.', ',')

def formatar_brl_to_float(valor_str):
    try:
        valor_str = valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(valor_str)
    except ValueError:
        return 0.0

def build_full_url(request, path='', user=None):
    """
    Constrói uma URL completa incluindo o subdomínio do tenant
    
    Args:
        request: HttpRequest object
        path: Caminho relativo (opcional)
        user: User object (opcional, se não fornecido usa request.user)
    
    Returns:
        str: URL completa com subdomínio do tenant
    
    Exemplo:
        build_full_url(request, '/painel/produtos/')
        # Retorna: http://marcos.localhost:8000/painel/produtos/
    """
    # Obtém o protocolo (http ou https)
    protocol = 'https' if request.is_secure() else 'http'
    
    # Determina qual user usar
    target_user = user if user else getattr(request, 'user', None)
    
    # Obtém o subdomínio do tenant
    if target_user and hasattr(target_user, 'tenant') and target_user.tenant:
        subdomain = target_user.tenant.subdomain
        
        # Para desenvolvimento local
        if 'localhost' in request.get_host() or request.get_host().startswith('127.0.0.1'):
            # Preserva a porta se existir
            port = ':8000' if ':' not in request.get_host() or ':8000' in request.get_host() else ''
            host = f"{subdomain}.localhost{port}"
        else:
            # Para produção - ajuste conforme seu domínio
            host = f"{subdomain}.seudominio.com"
    else:
        # Fallback: usa o host atual se não conseguir determinar o tenant
        host = request.get_host()
    
    # Remove a barra inicial do path se existir para evitar duplicação
    if path.startswith('/'):
        path = path[1:]
    
    # Constrói a URL completa
    full_url = f"{protocol}://{host}/{path}"
    
    return full_url

def get_tenant_url(request, path='', user=None):
    """
    Alias para build_full_url com foco no tenant (mantido para compatibilidade)
    
    Args:
        request: HttpRequest object  
        path: Caminho relativo (opcional)
        user: User object (opcional, se não fornecido usa request.user)
    
    Returns:
        str: URL completa com subdomínio do tenant
    """
    return build_full_url(request, path, user)

def build_tenant_url_for_user(user, path='', protocol='http', domain='localhost:8000'):
    """
    Constrói URL completa para um usuário específico (útil para emails, notificações, etc.)
    
    Args:
        user: User object
        path: Caminho relativo (opcional)
        protocol: 'http' ou 'https' (padrão: 'http')
        domain: Domínio base (padrão: 'localhost:8000')
    
    Returns:
        str: URL completa com subdomínio do tenant
    
    Exemplo:
        build_tenant_url_for_user(user, '/produto/123/', 'https', 'meusite.com')
        # Retorna: https://marcos.meusite.com/produto/123/
    """
    if user and hasattr(user, 'tenant') and user.tenant:
        subdomain = user.tenant.subdomain
        
        # Remove protocolo do domain se existir
        if domain.startswith(('http://', 'https://')):
            domain = domain.split('://', 1)[1]
        
        host = f"{subdomain}.{domain}"
    else:
        # Fallback sem subdomínio
        host = domain
    
    # Remove a barra inicial do path se existir
    if path.startswith('/'):
        path = path[1:]
    
    return f"{protocol}://{host}/{path}"


def verificar_loja_aberta(request, user=None):
    """
    Função utilitária para verificar se a loja está aberta.
    
    Args:
        request: HttpRequest object
        user: User object (opcional, se não fornecido usa request.user)
    
    Returns:
        dict: {
            'aberta': bool,
            'status_texto': str,
            'proximo_evento': dict ou None,
            'horarios_hoje': QuerySet
        }
    """
    from datetime import datetime, timedelta
    
    # Determina qual tenant usar - prioriza request.tenant (multi-tenant) sobre user.tenant
    tenant = None
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
    else:
        target_user = user if user else getattr(request, 'user', None)
        if target_user and hasattr(target_user, 'tenant') and target_user.tenant:
            tenant = target_user.tenant
    
    if not tenant:
        return {
            'aberta': False,
            'status_texto': 'Loja não configurada',
            'proximo_evento': None,
            'horarios_hoje': None,
            'is_open': False,
        }
    
    agora = datetime.now()
    
    # DEBUG: Adicionar logs detalhados
    print(f"=== DEBUG VERIFICAR_LOJA_ABERTA ===")
    print(f"Tenant: {tenant.name}")
    print(f"Data/Hora atual: {agora}")
    print(f"Dia da semana: {agora.weekday()} (0=segunda, 6=domingo)")
    print(f"Hora atual: {agora.time()}")
    
    # Verificar horários cadastrados
    from tenants.models import HorarioFuncionamento
    todos_horarios = HorarioFuncionamento.objects.filter(tenant=tenant)
    print(f"Total de horários cadastrados: {todos_horarios.count()}")
    
    for h in todos_horarios:
        print(f"  - Dia {h.dia_semana} ({h.get_dia_semana_display()}): {h.horario_abre}-{h.horario_fecha}, Ativo: {h.ativo}, Data específica: {h.data_especifica}")
    
    # Verificar horários para hoje
    horarios_hoje = tenant.get_horarios_hoje(agora)
    print(f"Horários para hoje: {horarios_hoje.count()}")
    for h in horarios_hoje:
        print(f"  - {h.horario_abre}-{h.horario_fecha}, Ativo: {h.ativo}")
    
    esta_aberta = tenant.esta_aberto_agora(agora)
    print(f"Resultado esta_aberto_agora: {esta_aberta}")
    
    proximo_evento = tenant.get_proximo_horario(agora)
    print(f"Próximo evento: {proximo_evento}")
    
    if esta_aberta:
        is_open = True
        status_texto = "🟢 ABERTA"
        if proximo_evento and proximo_evento['acao'] == 'fecha':
            horario_str = proximo_evento['horario'].strftime('%H:%M')
            if proximo_evento['data'] == agora.date():
                status_texto += f" - Fecha às {horario_str}"
            else:
                status_texto += f" - Fecha amanhã às {horario_str}"
    else:
        is_open = False
        status_texto = "🔴 FECHADA"
        if proximo_evento and proximo_evento['acao'] == 'abre':
            horario_str = proximo_evento['horario'].strftime('%H:%M')
            if proximo_evento['data'] == agora.date():
                status_texto += f" - Abre às {horario_str}"
            elif proximo_evento['data'] == agora.date() + timedelta(days=1):
                status_texto += f" - Abre amanhã às {horario_str}"
            else:
                dia_nome = [
                    'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'
                ][proximo_evento['data'].weekday()]
                status_texto += f" - Abre {dia_nome} às {horario_str}"
    
    return {
        'aberta': esta_aberta,
        'status_texto': status_texto,
        'proximo_evento': proximo_evento,
        'horarios_hoje': horarios_hoje,
        'is_open': is_open,
    }

