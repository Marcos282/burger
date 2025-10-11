# tenants/middleware.py

from django.http import Http404, HttpResponseForbidden
from django.urls import resolve
from tenants.models import Tenant
from datetime import datetime

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Pega o host e remove a porta, se presente
        host = request.get_host().split(':')[0]  # Ex: 'andre.localhost:8000' -> 'andre.localhost'
        parts = host.split('.')

        # Para localhost, aceita subdomínio com len(parts) >= 2
        subdomain = parts[0] if len(parts) >= 2 and parts[-1] == 'localhost' else None

        # Proteção: bloquear acesso ao painel com subdomínio
        if subdomain and request.path.startswith('/painel/'):
            # Constrói URL sem subdomínio para redirecionamento
            protocol = 'https' if request.is_secure() else 'http'
            base_domain = '.'.join(parts[1:])  # Remove o subdomínio
            port = f":{request.get_port()}" if request.get_port() not in ['80', '443'] else ''
            painel_url = f"{protocol}://{base_domain}{port}/painel/home/"
            
            return HttpResponseForbidden(
                f"Acesso negado: URLs do painel não podem ser acessadas via subdomínio. "
                f"Acesse diretamente pelo domínio principal.<br> "
                f"<a href='{painel_url}'>Ir para o painel</a>"
            )
        
        # Busca tenant no banco
        tenant = Tenant.objects.filter(subdomain=subdomain).first()
        
        # Lista de paths que não precisam de tenant (incluindo media e static)
        no_tenant_required = [
            '/admin/',
            '/painel/',
            '/media/',
            '/static/',
            '/logout/',
            '/login/',
            '/cdn-cgi/',
            '/favicon.ico',
            '/robots.txt',
            '/manifest.json',
            '/placeholder.png',
        ]
        
        # Verifica se a rota não precisa de tenant
        skip_tenant_check = any(request.path.startswith(path) for path in no_tenant_required)
        
        # Se não encontrar tenant e não for uma rota que dispensa tenant, lança 404
        if not tenant and not skip_tenant_check:
            raise Http404("Tenant não encontrado :: Administrador:  Verificar middleware TenantMiddleware")
        elif tenant:
            request.tenant = tenant  # Adiciona tenant ao request

        # Processa a requisição primeiro
        response = self.get_response(request)
        
        # Define quais rotas devem ser logadas
        should_log = False
        log_type = ""
        
        # Lista de paths que devem ser ignorados
        ignored_paths = [
            '/cdn-cgi/',
            '/favicon.ico',
            '/robots.txt',
            '/logout/',
            'rum?',  # Cloudflare RUM requests
            '.css',
            '.js',
            '.png',
            '.jpg',
            '.jpeg',
            '.gif',
            '.ico',
            '.woff',
            '.woff2',
            '.svg'
        ]
        
        # Verifica se a rota deve ser ignorada
        path_ignored = any(ignore in request.path for ignore in ignored_paths)
        
        if not path_ignored:
            if request.path.startswith('/painel/'):
                should_log = True
                log_type = "PAINEL ADMINISTRATIVO"
            elif request.path.startswith('/loja/'):
                should_log = True
                log_type = "MARKETPLACE"
            elif request.path in ['/', '/manifest.json']:
                should_log = True
                log_type = "SISTEMA"
        
        # Faz log apenas para rotas importantes
        if should_log:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ip_address = request.META.get('REMOTE_ADDR', 'N/A')
            
            # Verifica se o user está disponível
            user_info = "Anônimo"
            if hasattr(request, 'user'):
                if request.user.is_authenticated:
                    user_info = f"{request.user.username} ({request.user.email})"
                else:
                    user_info = "Não autenticado"
            
            # Adiciona informações do tenant quando aplicável
            tenant_info = ""
            if hasattr(request, 'tenant') and request.tenant:
                tenant_info = f" | 🏪 {request.tenant.name}"
            
            # Log formatado e elegante
            print("\n" + "🟦" * 50)
            print(f"🏢 {log_type} | {timestamp}")
            print("🟦" * 50)
            print(f"📍 IP: {ip_address} | 👤 Usuário: {user_info}{tenant_info}")
            print(f"🔗 Rota: {request.method} {request.path}")
            
            # Pega apenas o telefone do cliente do cookie
            telefone_cliente = request.COOKIES.get('telefone_cliente', 'Não informado')
            print(f"📞 Telefone Cliente (cookie): {telefone_cliente}")
            
            print(f"📊 Status: {response.status_code}")            
            print("🟦" * 50 + "\n")
            
        return response