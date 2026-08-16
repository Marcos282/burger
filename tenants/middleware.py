import logging
from typing import Iterable

import tldextract
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from customers.contexto import salvar_tenant_em_sessao
from .models import Tenant


logger = logging.getLogger(__name__)


def _default_allowed_subdomains() -> Iterable[str]:
    return (
        "www",
        "admin",
        "api",
        "static",
        "media",
        "localhost",
        "lignetbrasil",
        "lignetbrasil.com.br",
        "lignetbrasil.com",
        "burger",
        "burger.com.br",
        "burger.com",
    )


class TenantMiddleware:
    """
    Resolve a Tenant from the request host subdomain.

    Behavior:
    - Normalizes host (removes port, trailing dots, lowercases).
    - Uses settings.TENANT_ALLOWED_SUBDOMAINS when present, otherwise a sensible default.
    - Sets `request.tenant` to a Tenant instance or None.
    - Raises Http404 when a non-allowed subdomain has no Tenant.
    - If downstream returns None (incorrectly), redirects to `home_view` to avoid middleware errors.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Normalize host and extract subdomain
        host = (request.get_host() or "").split(":")[0].strip().lower().strip(".")
        try:
            extracted = tldextract.extract(host)
            subdomain = (extracted.subdomain or "").lower()
        except Exception:
            logger.exception("Erro ao extrair subdomínio do host: %s", host)
            subdomain = ""

        # Prepare allowed subdomains (configurable)
        allowed = getattr(settings, "TENANT_ALLOWED_SUBDOMAINS", None)
        if allowed is None:
            allowed = set(_default_allowed_subdomains())
        else:
            allowed = set(str(x).lower() for x in allowed)

        # Default values
        request.tenant = None
        tenant_id = 0

        # Resolve tenant when appropriate
        if subdomain:
            logger.debug("Subdomínio detectado: %s", subdomain)
            if subdomain in allowed:
                logger.debug("Subdomínio '%s' está na lista de liberados", subdomain)
                request.tenant = None
            else:
                try:
                    tenant = Tenant.objects.get(subdomain=subdomain)
                    request.tenant = tenant
                    tenant_id = tenant.id
                    logger.info("✅ Tenant encontrado: %s | ID: %s", tenant, tenant_id)
                except Tenant.DoesNotExist:
                    logger.warning(
                        "⚠️ Tenant '%s' NÃO encontrado para path %s", subdomain, request.path
                    )
                    request.tenant = None
                    # If subdomain is not allowed, block access
                    if subdomain not in allowed:
                        raise Http404("Tenant não encontrado")
        else:
            logger.info("ℹ️ Sem subdomínio (site principal)")

        # Continue processing
        response = self.get_response(request)

        if request.user.is_authenticated:
            tenant_do_login = getattr(request.user, 'tenant', None)
            if tenant_do_login is not None:
                print("=== TENANT NO FINAL DO MIDDLEWARE ===")
                print({
                    'request_user': getattr(request.user, 'email', None),
                    'tenant_id': tenant_do_login.id,
                    'tenant_name': tenant_do_login.name,
                    'tenant_subdomain': tenant_do_login.subdomain,
                    'session_tenant_id': request.session.get('tenant_id'),
                    'session_id_tenant': request.session.get('id_tenant'),
                })
                print("====================================")

        # Guard: if downstream mistakenly returned None, redirect to home_view
        if response is None:
            logger.warning("⚠️ get_response retornou None; redirecionando para home_view")
            try:
                home_path = reverse("home_view")
            except Exception:
                home_path = "/home_view/"

            if request.path != home_path:
                return redirect("home_view")

        return response

