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