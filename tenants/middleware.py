# Biblioteca padrão para validação de IP (usada para diferenciar host/IP de subdomínio).
import ipaddress
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

# Biblioteca padrão de logging para observabilidade do fluxo de tenant.
import logging
# Armazenamento local por thread para expor contexto do tenant globalmente na requisição.
from threading import local

# Model principal de tenant do sistema.
from tenants.models import Tenant

# Logger deste módulo.
logger = logging.getLogger(__name__)

# Contexto local da requisição atual (thread local).
_tenant_context = local()


def get_current_tenant_id():
    """Retorna o tenant_id da requisição atual (ou None)."""
    return getattr(_tenant_context, 'tenant_id', None)


def _get_configuracao_site_model():
    # Import opcional para evitar quebra caso o model não exista em algum ambiente.
    """Importa ConfiguracaoSite de forma opcional para evitar quebra se o model não existir."""
    try:
        # Import tardio para reduzir acoplamento e evitar erro em startup.
        from core.models import ConfiguracaoSite  # type: ignore
    except Exception:
        # Se não conseguir importar, segue sem configuração global.
        return None
    # Retorna a classe quando disponível.
    return ConfiguracaoSite


def _extract_subdomain(host):
    # Extrai subdomínio real do host removendo porta e ignorando casos sem domínio válido.
    """Retorna o subdomínio quando existir, ignorando IP e domínio raiz."""
    # Remove porta do host, ex.: loja.localhost:8000 -> loja.localhost.
    host_without_port = host.split(':')[0]

    try:
        # Se for IP (127.0.0.1, ::1 etc.), não deve ser tratado como subdomínio.
        ipaddress.ip_address(host_without_port)
        return None
    except ValueError:
        # Não é IP, então segue o fluxo normal de parsing de domínio.
        pass

    # localhost puro não possui subdomínio.
    if host_without_port == 'localhost':
        return None

    # Separa o host em partes para identificar subdomínio.
    parts = host_without_port.split('.')
    # Sem ponto suficiente, não há subdomínio.
    if len(parts) <= 1:
        return None

    # Ex.: loja.localhost -> loja
    if parts[-1] == 'localhost':
        return parts[0] if len(parts) >= 2 else None

    # Ex.: loja.exemplo.com -> loja
    return parts[0]


def _is_loja_path(path):
    # Define quais rotas precisam de tenant obrigatório.
    """Define quais rotas exigem tenant resolvido."""
    return path.startswith('/loja')


def _get_tenant_from_authenticated_user(request):
    # Fallback para recuperar tenant a partir do usuário autenticado.
    """Recupera tenant do usuário logado quando não há subdomínio na URL."""
    # Usa getattr para evitar erro caso request.user não exista no contexto.
    user = getattr(request, 'user', None)
    # Só retorna tenant quando usuário está autenticado e com vínculo válido.
    if user and user.is_authenticated and getattr(user, 'tenant_id', None):
        return user.tenant
      
    # Sem tenant válido, retorna None.
    # Sem tenant autenticado, retorna None.
    
    
    return None


def _redirect_home_if_needed(request):
    # Evita loop quando a requisição já está na própria home.
    try:
        home_path = reverse('home_view')
    except NoReverseMatch:
        # Fallback seguro caso a URL nomeada não exista neste ambiente.
        home_path = '/home_view/'

    current_path = request.path.rstrip('/')
    normalized_home_path = home_path.rstrip('/')

    if current_path == normalized_home_path:
        logger.warning("[TENANT] Redirect para home evitado para prevenir loop: %s", request.path)
        return None

    return redirect('home_view')


class SubdomainMiddleware:
    # Middleware padrão: recebe próximo handler no pipeline do Django.
    def __init__(self, get_response):
        # Função que continua o processamento da requisição.
        self.get_response = get_response

    def __call__(self, request):
        # Lê host atual da requisição.
        host = request.get_host()
        # Tenta extrair subdomínio válido.
        subdomain = _extract_subdomain(host)

        # Inicializa tenant no request para sempre existir esse atributo.
        request.tenant = None

        # Se há subdomínio, tenta resolver tenant no banco.
        if subdomain:
            # Busca case-insensitive por segurança com variações de caixa.
            request.tenant = Tenant.objects.filter(subdomain__iexact=subdomain).first()
            if request.tenant:
                # Log de sucesso na resolução do tenant.
                logger.info("[TENANT] Tenant encontrado: '%s'", subdomain)
            else:
                # Log de falha na resolução do tenant pelo subdomínio.
                logger.warning("[TENANT] Tenant nao encontrado: '%s'", subdomain)
                # Bloco opcional para enriquecer log com nome do site.
                configuracao_site_model = _get_configuracao_site_model()
                if configuracao_site_model is not None:
                    configuracao_site = configuracao_site_model.objects.first()
                    if configuracao_site:
                        logger.info("[CONFIG] Nome do site: %s", getattr(configuracao_site, 'nome_site', 'N/A'))
                safe_redirect = _redirect_home_if_needed(request)
                if safe_redirect:
                    return safe_redirect
        else:
            # Acesso sem subdomínio (domínio raiz/localhost).
            logger.debug("[TENANT] Sem subdominio - acesso direto")

        # Fallback para manter tenant na sessão em rotas sem subdomínio
        # (ex.: login/painel no domínio raiz).
        if request.tenant is None:
            request.tenant = _get_tenant_from_authenticated_user(request)

        # Em rotas de loja, tenant é obrigatório.
        if _is_loja_path(request.path) and request.tenant is None:
            safe_redirect = _redirect_home_if_needed(request)
            if safe_redirect:
                return safe_redirect

        # Expõe subdomínio resolvido para uso em views/templates.
        request.subdomain = subdomain
        # Expõe tenant_id direto no request para acesso rápido no código.
        request.tenant_id = request.tenant.id if request.tenant else None
        # Persiste subdomínio na sessão para reaproveitamento entre requests.
        request.session['subdomain'] = subdomain
        # Persiste ID do tenant para uso global no sistema.
        request.session['tenant_id'] = request.tenant_id
        # Persiste tenant_id no contexto local para uso fora do request (na mesma thread).
        _tenant_context.tenant_id = request.tenant_id
        # Log técnico da rota processada e contexto de subdomínio.
        logger.debug("[TENANT] %s %s - subdominio: %s", request.method, request.path, subdomain)
        logger.debug("[TENANT] Tenant ID atual: %s", request.tenant_id)
        # Continua pipeline normal do Django.
        return self.get_response(request)
# Mantém compatibilidade com settings atuais: tenants.middleware.TenantMiddleware
TenantMiddleware = SubdomainMiddleware