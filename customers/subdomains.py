import re

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from tenants.models import Tenant
from .models import User

RESERVED = {'www', 'admin', 'api', 'static', 'media', 'localhost', 'mail',
            'smtp', 'support', 'suporte', 'ftp', 'ns1', 'ns2'}


def validate_subdomain(value):
    name = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?', name):
        raise ValidationError('Use de 1 a 50 letras, números ou hífens, sem hífen no início ou fim.')
    if name in RESERVED:
        raise ValidationError('Este nome está reservado. Escolha outro.')
    if User.objects.filter(username__iexact=name).exists():
        raise ValidationError('Este username já está em uso.')
    if Tenant.objects.filter(subdomain__iexact=name).exists():
        raise ValidationError('Este subdomínio já está em uso. Escolha outro.')
    return name


@never_cache
@require_GET
def subdomain_availability(request):
    try:
        name = validate_subdomain(request.GET.get('subdomain', ''))
    except ValidationError as error:
        return JsonResponse({'available': False, 'message': error.messages[0]})
    return JsonResponse({'available': True, 'subdomain': name,
                         'message': f'{name}.viazap.net está disponível!'})
