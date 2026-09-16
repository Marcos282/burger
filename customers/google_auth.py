import secrets
from functools import wraps, partial

from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from tenants.models import Tenant, TenantSettings
from .contexto import salvar_tenant_em_sessao
from .models import User
from .subdomains import validate_subdomain


def google_page(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if settings.GOOGLE_CLIENT_ID:
            response['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
            if settings.DEBUG and not request.is_secure():
                response['Referrer-Policy'] = 'no-referrer-when-downgrade'
        return response
    return wrapped


def google_context(request):
    if request.GET.get('logged_out') == '1':
        request.session['google_signed_out'] = True
    nonce = request.session.get('google_nonce')
    if not nonce:
        nonce = secrets.token_urlsafe(32)
        request.session['google_nonce'] = nonce
    return {'google_client_id': settings.GOOGLE_CLIENT_ID, 'google_nonce': nonce,
            'google_auto_select': settings.GOOGLE_AUTO_SELECT and not request.session.get('google_signed_out')}


def error(message, status=400, **extra):
    return JsonResponse({'message': message, **extra}, status=status)


@never_cache
@require_POST
@sensitive_post_parameters('credential', 'password')
def google_login(request):
    if not settings.GOOGLE_CLIENT_ID:
        return error('Login com Google ainda não configurado.', 503)
    credential = request.POST.get('credential', '')
    if not credential or len(credential) > 10000:
        return error('Credencial do Google ausente ou inválida.')
    try:
        claims = id_token.verify_oauth2_token(credential, partial(Request(), timeout=10), settings.GOOGLE_CLIENT_ID)
        nonce = request.session.get('google_nonce', '')
        if not nonce or not secrets.compare_digest(nonce, str(claims.get('nonce', ''))):
            return error('Sessão expirada. Atualize a página e tente novamente.', 403)
        subject = claims.get('sub')
        email = claims.get('email', '').strip().lower()
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError('Invalid subject')
        validate_email(email)
        if claims.get('email_verified') is not True:
            return error('Confirme o endereço de e-mail na sua conta Google primeiro.')
    except (ValueError, ValidationError, GoogleAuthError):
        return error('Não foi possível validar sua conta Google. Tente novamente.', 401)

    authoritative = email.endswith('@gmail.com') or bool(claims.get('hd'))
    try:
        with transaction.atomic():
            user = User.objects.select_for_update().filter(google_sub=subject).first()
            if user is None:
                user = User.objects.select_for_update().filter(email__iexact=email).first()
                if user:
                    if user.google_sub:
                        return error('Esta conta já está vinculada a outra identidade Google.', 409)
                    if not request.POST.get('password'):
                        return error('Esta conta já existe. Confira sua senha para continuar com o Google.',
                                     409, requires_password=True, email=email)
                    if not user.check_password(request.POST['password']):
                        return error('Senha incorreta. Tente novamente.', 403, requires_password=True, email=email)
                    if not user.is_active:
                        return error('Confirme seu e-mail ou solicite suporte para ativar sua conta.', 403)
                    host_tenant = getattr(request, 'tenant', None)
                    if host_tenant and host_tenant.pk != user.tenant_id:
                        return error('Entre pelo endereço da sua loja ou pelo site principal.', 403)
                    user.google_sub = subject
                    user.save(update_fields=['google_sub'])
                else:
                    if request.POST.get('mode') != 'register' or not request.POST.get('username', '').strip():
                        return JsonResponse({
                            'requires_registration': True, 'email': email,
                            'message': 'Conta Google confirmada. Escolha o nome do seu site para continuar.',
                        })
                    name = validate_subdomain(request.POST.get('username', ''))
                    tenant = Tenant.objects.create(name=name, subdomain=name)
                    user = User.objects.create_user(email=email, username=name, tenant=tenant,
                        password=None, google_sub=subject, is_active=authoritative,
                        email_confirmation_pending=not authoritative,
                        email_verified_at=timezone.now() if authoritative else None)
    except ValidationError as exc:
        return error(' '.join(exc.messages))
    except (IntegrityError, ValueError):
        return error('Este cadastro já existe ou o nome do site foi ocupado. Atualize e tente novamente.', 409)

    if not user.is_active:
        if user.email_confirmation_pending:
            from .email_confirmation import send_confirmation
            sent = send_confirmation(request, user)
            request.session['email_confirmation_registered'] = True
            request.session['email_confirmation_delivery_failed'] = not sent
            return JsonResponse({'redirect': reverse('email_confirmation_request')})
        return error('Conta desativada. Entre em contato com o suporte.', 403)
    host_tenant = getattr(request, 'tenant', None)
    if host_tenant and host_tenant.pk != user.tenant_id:
        return error('Entre pelo endereço da sua loja ou pelo site principal.', 403)
    google_name = claims.get('name')
    if isinstance(google_name, str) and google_name.strip():
        profile = TenantSettings.load(user.tenant)
        if not (profile.nome_responsavel or '').strip():
            profile.nome_responsavel = google_name.strip()[:100]
            profile.save(update_fields=['nome_responsavel'])

    request.session.pop('google_nonce', None)
    request.session.pop('google_signed_out', None)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    salvar_tenant_em_sessao(request, email=user.email)
    return JsonResponse({'redirect': reverse('painel_configuracao')})
