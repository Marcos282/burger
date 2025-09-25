# tenants/middleware.py


from tenants.models import Tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Pega o host e remove a porta, se presente
        host = request.get_host().split(':')[0]  # Ex: 'andre.localhost:8000' -> 'andre.localhost'
        parts = host.split('.')

        # Para localhost, aceita subdomínio com len(parts) >= 2
        subdomain = parts[0] if len(parts) >= 2 and parts[-1] == 'localhost' else None

        # Busca tenant no banco
        tenant = Tenant.objects.filter(subdomain=subdomain).first()
        request.tenant = tenant  # Adiciona tenant ao request

        return self.get_response(request)