"""SEO da plataforma: não consome produtos nem configurações de tenants."""
import json
from urllib.parse import urljoin, urlsplit, urlunsplit
from django.templatetags.static import static
from tenants.models import Configuracao

ORIGIN = 'https://www.viazap.net/'
TITLE = 'ViaZap | Loja Online, Pedidos e Vendas pelo WhatsApp'
DESCRIPTION = ('Crie sua loja online com o ViaZap, divulgue seus produtos, receba pedidos e venda pelo WhatsApp. '
               'Uma plataforma simples para delivery, varejo e pequenos negócios.')
PUBLIC_PATHS = ('/',)


def public_url(path):
    return urlunsplit(urlsplit(urljoin(ORIGIN, path))._replace(scheme='https', query='', fragment=''))


def home_context():
    config = Configuracao.load()
    organization = {'@context': 'https://schema.org', '@type': 'Organization', 'name': 'ViaZap', 'url': ORIGIN}
    if config.logo:
        organization['logo'] = public_url(config.logo.url)
    website = {'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'ViaZap', 'url': ORIGIN}
    def encode(value):
        return json.dumps(value, ensure_ascii=False).translate(str.maketrans({'<': r'\u003C', '>': r'\u003E', '&': r'\u0026'}))
    return {'seo': {'title': TITLE, 'description': DESCRIPTION, 'canonical': ORIGIN,
                    'image': public_url(static('institucional/viazap-social.png')), 'robots': 'index,follow'},
            'organization_json': encode(organization), 'website_json': encode(website)}
