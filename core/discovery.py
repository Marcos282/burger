"""Descoberta de URLs públicas, sempre limitada ao host/tenant da requisição."""
from urllib.parse import urlencode
from xml.etree.ElementTree import Element, SubElement, tostring

from django.http import Http404, HttpResponse
from django.urls import reverse
from menu.models import Category, Produto
from core.product_metadata import absolute_https


def sitemap(request):
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        from core.institutional import PUBLIC_PATHS, public_url
        root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for path in PUBLIC_PATHS:
            SubElement(SubElement(root, 'url'), 'loc').text = public_url(path)
        return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')
    # Índice paginado para respeitar o limite de 50 mil URLs por sitemap.
    products = Produto.objects.filter(tenant=tenant, status=True, exibir=True).order_by('pk')
    categories = Category.objects.filter(tenant=tenant, status=True, exibir=True,
                                        produto__tenant=tenant, produto__status=True,
                                        produto__exibir=True).distinct().order_by('pk')
    paths = [reverse('loja')]
    paths.extend(reverse('loja') + '?' + urlencode({'categoria_id': pk}) for pk in categories.values_list('pk', flat=True))
    paths.extend(reverse('detalhe', args=[pk]) for pk in products.values_list('pk', flat=True))
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    page_size = 45000
    page = request.GET.get('page')
    if len(paths) > page_size and page is None:
        root = Element('sitemapindex', xmlns=namespace)
        for offset in range(0, len(paths), page_size):
            entry = SubElement(root, 'sitemap')
            SubElement(entry, 'loc').text = absolute_https(request, reverse('tenant_sitemap') + '?' + urlencode({'page': offset // page_size + 1}))
    else:
        try:
            number = int(page or 1)
        except ValueError:
            raise Http404('Página inválida.')
        if number < 1 or (number - 1) * page_size >= len(paths):
            raise Http404('Página inválida.')
        root = Element('urlset', xmlns=namespace)
        for path in paths[(number - 1) * page_size:number * page_size]:
            SubElement(SubElement(root, 'url'), 'loc').text = absolute_https(request, path)
    return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')


def robots(request):
    lines = ['User-agent: *', 'Disallow: /painel/', 'Disallow: /admin/']
    if getattr(request, 'tenant', None):
        lines += ['Sitemap: ' + absolute_https(request, reverse('tenant_sitemap'))]
    else:
        from core.institutional import public_url
        lines += ['Sitemap: ' + public_url('/sitemap.xml')]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')
