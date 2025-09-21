# tenants/middleware.py

from tenants.models import Tenant


# Middleware para identificar o tenant baseado no subdomínio
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # pega subdomínio (ex: andre.burger.net -> andre)
        host = request.get_host().split('.')
        subdomain = host[0] if len(host) > 2 else None

        # busca tenant no banco único
        tenant = Tenant.objects.filter(subdomain=subdomain).first()
        request.tenant = tenant  # adiciona tenant ao request

        return self.get_response(request)
