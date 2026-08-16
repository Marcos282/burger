from tenants.models import Tenant


def buscar_tenant_por_email(email):
    """Busca o tenant relacionado ao usuário autenticado pelo email."""
    if not email:
        return None

    try:
        from customers.models import User

        user = User.objects.filter(email=email).first()
        if user and getattr(user, 'tenant', None):
            return user.tenant
    except Exception:
        return None

    return None


def salvar_tenant_em_sessao(request, email=None, user=None):
    """Salva o tenant autenticado na sessão do usuário."""
    if not hasattr(request, 'session'):
        return None

    if user is None:
        user = getattr(request, 'user', None)

    if email is None and user is not None:
        email = getattr(user, 'email', None)

    tenant = None

    if email:
        tenant = buscar_tenant_por_email(email)

    if tenant is None and user is not None and getattr(user, 'is_authenticated', False):
        tenant = getattr(user, 'tenant', None)

    if tenant is None:
        tenant_id = request.session.get('tenant_id') or request.session.get('id_tenant')
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()

    if tenant is not None:
        request.session['tenant_id'] = tenant.id
        request.session['id_tenant'] = tenant.id
        request.session['tenant_subdomain'] = tenant.subdomain
        request.session['tenant_nome'] = tenant.name
        request.session.modified = True
        request.tenant = tenant

        print("=== TENANT BUSCADO PELO LOGIN ===")
        print({
            'id': tenant.id,
            'name': tenant.name,
            'subdomain': tenant.subdomain,
            'email': email,
        })
        print("=== SESSION TENANT DEBUG ===")
        print({
            'tenant_id': request.session.get('tenant_id'),
            'id_tenant': request.session.get('id_tenant'),
            'tenant_subdomain': request.session.get('tenant_subdomain'),
            'tenant_nome': request.session.get('tenant_nome'),
        })
        print("===========================")
        return tenant

    return None


def recuperar_tenant_do_contexto(request):
    """Recupera o tenant da sessão e o expõe no contexto do template."""
    tenant = None
    tenant_id = request.session.get('tenant_id') if hasattr(request, 'session') else None

    if tenant_id is None and hasattr(request, 'session'):
        tenant_id = request.session.get('id_tenant')

    if tenant_id:
        tenant = Tenant.objects.filter(id=tenant_id).first()

    if tenant is None and getattr(request, 'user', None) is not None:
        tenant = getattr(request.user, 'tenant', None)

    if tenant is not None:
        request.tenant = tenant

    return {'tenant': tenant}
