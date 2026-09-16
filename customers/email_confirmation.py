"""Confirmação de cadastro por link assinado e com validade limitada."""
import logging
from smtplib import SMTPException

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods

from .forms import PasswordResetRequestForm
from .models import User

logger = logging.getLogger(__name__)
SALT = 'customers.email-confirmation'
MAX_AGE = 24 * 60 * 60


def confirmation_token(user):
    return signing.dumps({'user_id': user.pk, 'email': user.email}, salt=SALT)


@sensitive_variables('token', 'url')
def send_confirmation(request, user):
    key = f'email-confirmation:{user.pk}'
    if not cache.add(key, True, timeout=60):
        return False
    token = confirmation_token(user)
    path = reverse('email_confirm', args=[token])
    base = settings.EMAIL_CONFIRMATION_BASE_URL.rstrip('/')
    url = base + path if base else request.build_absolute_uri(path)
    try:
        send_mail(
            'Confirme seu e-mail — ViaZap',
            'Confirme seu e-mail para ativar sua conta ViaZap:\n\n'
            f'{url}\n\nEste link é válido por 24 horas.\n'
            'Se você não fez este cadastro, ignore esta mensagem.',
            None, [user.email], fail_silently=False,
        )
    except (SMTPException, OSError):
        cache.delete(key)
        # Não registrar mensagem de exceção: provedores podem incluir credenciais.
        logger.warning('Falha no envio da confirmação de cadastro.')
        return False
    return True


@never_cache
@require_http_methods(['GET', 'POST'])
def email_confirmation_request(request):
    form = PasswordResetRequestForm(request.POST or None)
    submitted = False
    if request.method == 'POST' and form.is_valid():
        user = User.objects.filter(
            email__iexact=form.cleaned_data['email'],
            email_confirmation_pending=True, is_active=False,
        ).first()
        if user:
            send_confirmation(request, user)
        submitted = True
    return render(request, 'login/email_confirmation.html', {
        'form': form, 'submitted': submitted,
        'registered': request.session.pop('email_confirmation_registered', False),
        'delivery_failed': request.session.pop('email_confirmation_delivery_failed', False),
    })


@never_cache
@require_http_methods(['GET', 'POST'])
def email_confirm(request, token):
    user = None
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        user = User.objects.filter(
            pk=data['user_id'], email=data['email'],
            email_confirmation_pending=True, is_active=False,
        ).first()
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        pass
    if user and request.method == 'POST':
        with transaction.atomic():
            updated = User.objects.filter(
                pk=user.pk, email=user.email,
                email_confirmation_pending=True, is_active=False,
            ).update(is_active=True, email_confirmation_pending=False,
                     email_verified_at=timezone.now())
        if updated:
            from django.contrib import messages
            messages.success(request, 'E-mail confirmado! Sua conta está ativa. Faça login.')
            return redirect('login')
        user = None
    # GET não ativa: evita consumir o link em verificadores automáticos de e-mail.
    return render(request, 'login/email_confirmation.html', {
        'confirming': True, 'valid_link': user is not None,
    })
