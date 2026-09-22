from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.conf import settings as django_settings
from django.contrib.auth.hashers import constant_time_compare
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import AcessoSite
from .google_analytics import GoogleAnalyticsError, get_google_analytics_report
from orders.models import Ordem
from tenants.models import TenantSettings


@login_required
def relatorio_acessos(request):
    host_tenant = getattr(request, 'tenant', None)
    user_tenant_id = getattr(request.user, 'tenant_id', None)
    if user_tenant_id is None or (host_tenant is not None and user_tenant_id != host_tenant.id):
        from django.http import Http404
        raise Http404('Tenant inválido.')

    try:
        days = int(request.GET.get('dias', 7))
    except (TypeError, ValueError):
        days = 7
    days = days if days in (7, 30, 90) else 7

    start = timezone.localdate() - timedelta(days=days - 1)
    accesses = AcessoSite.objects.filter(
        tenant_id=request.user.tenant_id,
        data_hora__date__gte=start,
    )
    daily = list(
        accesses.annotate(dia=TruncDate('data_hora'))
        .values('dia')
        .annotate(views=Count('id'), visitors=Count('visitor_key', distinct=True))
        .order_by('dia')
    )
    pages = list(
        accesses.values('pagina')
        .annotate(views=Count('id'), visitors=Count('visitor_key', distinct=True))
        .order_by('-views', 'pagina')[:10]
    )
    context = {
        'localizacao': [
            {'n1': 'Home', 'url': 'painel_home'},
            {'n2': 'Relatórios de acesso', 'url': 'relatorio_acessos'},
        ],
        'user': request.user,
        'period_days': days,
        'total_views': accesses.count(),
        'total_visitors': accesses.values('visitor_key').distinct().count(),
        'daily': daily,
        'pages': pages,
        'max_daily_views': max((item['views'] for item in daily), default=1),
    }
    return render(request, 'painel/relatorio_acessos.html', context)


@login_required
def google_stats(request):
    host_tenant = getattr(request, 'tenant', None)
    tenant = getattr(request.user, 'tenant', None)
    if tenant is None or (host_tenant is not None and tenant.pk != host_tenant.pk):
        from django.http import Http404
        raise Http404('Loja não encontrada.')

    session_key = f'google_stats_pin_ok_{tenant.pk}'
    pin_error = ''
    if request.method == 'POST' and request.POST.get('stats_pin') is not None:
        supplied_pin = request.POST.get('stats_pin', '').strip()
        if len(supplied_pin) == 4 and supplied_pin.isdigit() and constant_time_compare(
            supplied_pin, django_settings.GOOGLE_STATS_PIN,
        ):
            request.session[session_key] = True
            request.session.set_expiry(0)
            return redirect('google_stats')
        pin_error = 'PIN incorreto.'
    if not request.session.get(session_key):
        return render(request, 'painel/google_stats_pin.html', {
            'pin_error': pin_error,
            'tenant': tenant,
        }, status=403 if pin_error else 200)

    try:
        days = int(request.GET.get('dias', 30))
    except (TypeError, ValueError):
        days = 30
    days = days if days in (7, 30, 90) else 30
    settings = TenantSettings.load(tenant)
    report = None
    error = ''
    try:
        report = get_google_analytics_report(
            tenant_id=tenant.pk,
            property_id=(settings.google_analytics_property_id or '').strip(),
            days=days,
        )
    except GoogleAnalyticsError as exc:
        error = str(exc)

    return render(request, 'painel/google_stats.html', {
        'localizacao': [
            {'n1': 'Home', 'url': 'painel_home'},
            {'n2': 'Google Analytics', 'url': 'google_stats'},
        ],
        'qt_items_cliente': Ordem.objects.filter(tenant=tenant).count(),
        'period_days': days,
        'report': report,
        'stats_error': error,
        'property_id': settings.google_analytics_property_id,
    })
