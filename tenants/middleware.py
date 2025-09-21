# tenants/middleware.py
from django.db import connections
from tenants.models import Tenant

class TenantDBMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split('.')
        subdomain = host[0] if len(host) > 2 else None
        tenant = Tenant.objects.filter(subdomain=subdomain).first()
        request.tenant = tenant

        if tenant:
            connections.databases['tenant'] = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': tenant.db_name,
                'USER': tenant.db_user,
                'PASSWORD': tenant.db_pass,
                'HOST': 'localhost',
                'PORT': 5432,
            }
        return self.get_response(request)
