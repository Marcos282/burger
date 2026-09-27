"""Representação pública do produto, reutilizada por SEO, redes e mensuração."""
import json
from decimal import Decimal
from html import unescape
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.core.exceptions import PermissionDenied
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator


def clean_text(value):
    return ' '.join(strip_tags(unescape(value or '')).split())


def absolute_https(request, path):
    parts = urlsplit(request.build_absolute_uri(path))
    return urlunsplit(parts._replace(scheme='https', fragment=''))


def product_item(product, tenant, quantity=1, price=None):
    if tenant is None or product.tenant_id != tenant.pk:
        raise PermissionDenied('Produto de outra loja.')
    category = product.category
    return {
        'item_id': str(product.pk), 'item_name': clean_text(product.nome),
        'item_category': clean_text(category.name) if category and category.tenant_id == tenant.pk else '',
        'price': float(product.price if price is None else price), 'quantity': quantity,
    }


def product_metadata(request, produto, imagens_galeria, config, configuracao):
    tenant = request.tenant
    item = product_item(produto, tenant)
    if config and config.tenant_id != tenant.pk:
        raise PermissionDenied('Configuração de outra loja.')
    title = item['item_name']
    price = f"{Decimal(str(produto.price)):.2f}"
    formatted_price = f"R$ {Decimal(price):,.2f}".translate(str.maketrans(',.', '.,'))
    plain_description = clean_text(produto.description) or title
    description = f'{Truncator(plain_description).chars(180)} — {formatted_price}.'
    image = produto.image or next((entry.imagem for entry in imagens_galeria
                                  if entry.produto_id == produto.pk and entry.imagem), None) or produto.imagem_extra
    image_path = image.url if image else None
    if not image_path and config:
        image_path = config.foto_perfil.url if config.foto_perfil else config.logo_url
    if not image_path:
        image_path = configuracao.logo.url if configuracao.logo else static('_core/_uploads/cadastro/2023/02/20061802236e3jji4ffg_thumb.jpg')
    image_url = absolute_https(request, image_path)
    canonical = absolute_https(request, reverse('detalhe', args=[produto.pk]))
    availability = 'InStock' if produto.status and produto.exibir else 'OutOfStock'
    text = f'Olha esse produto 👇\n\n{title}\n{formatted_price}\n\n{canonical}'
    schema = {
        '@context': 'https://schema.org', '@type': 'Product', 'name': title,
        'image': [image_url], 'description': plain_description,
        'offers': {
            '@type': 'Offer', 'url': canonical, 'priceCurrency': 'BRL', 'price': price,
            'availability': 'https://schema.org/' + availability,
            'seller': {'@type': 'Organization', 'name': tenant.name},
        },
    }
    if produto.referencia:
        schema['sku'] = produto.referencia
    if item['item_category']:
        schema['category'] = item['item_category']
    # Impede fechamento de script por conteúdo cadastrado, sem HTML-escapar o JSON.
    schema_json = json.dumps(schema, ensure_ascii=False).translate(str.maketrans({
        '<': r'\u003C', '>': r'\u003E', '&': r'\u0026', '\u2028': r'\u2028', '\u2029': r'\u2029',
    }))
    return {
        'title': title, 'description': description, 'text': text,
        'url': canonical, 'canonical_url': canonical, 'image': image_url, 'image_url': image_url,
        'site_name': tenant.name, 'tenant_id': tenant.pk, 'price': price, 'currency': 'BRL',
        'availability': availability, 'category': item['item_category'], 'sku': produto.referencia or '',
        'schema_json': schema_json,
        'whatsapp_url': 'https://api.whatsapp.com/send?' + urlencode({'text': text}),
        'facebook_url': 'https://www.facebook.com/sharer/sharer.php?' + urlencode({'u': canonical}),
        'x_url': 'https://twitter.com/intent/tweet?' + urlencode({'text': title, 'url': canonical}),
        'analytics': {'tenant_id': tenant.pk, 'product_id': produto.pk, 'product_name': title,
                      'category': item['item_category'], 'currency': 'BRL', 'value': float(price), 'items': [item]},
    }
