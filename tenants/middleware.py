import logging
import tldextract
from .models import Tenant
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Extrai o subdomínio
        host = request.get_host().split(':')[0]
        dados = tldextract.extract(host)
        subdominio = dados.subdomain

        if subdominio:
            logger.info(f"Subdomínio nao detectado:")

        nr = 0  # ✅ Definida AQUI (fora do if/else) → existe em todo lugar
        #subdominio = "www.marcos.dominio.com.br"
        # 2. Busca o Tenant no banco
        if subdominio:
            try:
                request.tenant = Tenant.objects.get(subdomain=subdominio)
                nr = request.tenant.id  # ✅ Agora nr recebe o ID do tenant
                logger.info(f"✅ Tenant encontrado: {request.tenant} | ID: {nr}")
            except Tenant.DoesNotExist:
                logger.warning(f"⚠️ Tenant '{subdominio}' NÃO encontrado")
                request.tenant = None
                nr = 0
        else:
            # Sem subdomínio = site principal
            request.tenant = None
            nr = 0
            logger.info("ℹ️ Sem subdomínio (site principal)")


            

        # 3. Continua o fluxo
        resposta = self.get_response(request)
        logger.info(f"✅ Resposta gerada — Tenant ID: {nr}")

        if not subdominio:
            # Evita loop: se a requisição já for para a rota `home_view`, não redirecionar
            try:
                home_path = reverse('home_view')
            except Exception:
                home_path = '/home_view/'

            if request.path != home_path:
                logger.info("ℹ️ Sem subdomínio (site principal) — redirecionando para /home_view/")
                return redirect('home_view')

        return resposta
