from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from .models import AcessoSite


@login_required
def relatorio_acessos(request):
    if not getattr(request, 'tenant', None) or request.user.tenant_id != request.tenant.id:
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
