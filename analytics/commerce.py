"""Payloads sem dados pessoais, reutilizáveis em integrações e relatórios futuros."""
from core.product_metadata import product_item
from menu.models import Produto


def ecommerce_data(tenant, items):
    return {'tenant_id': tenant.pk, 'currency': 'BRL',
            'value': round(sum(item['price'] * item['quantity'] for item in items), 2),
            'items': items}


def cart_data(request):
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return None
    cart = request.session.get('cart', {})
    ids = [int(pk) for pk in cart if str(pk).isdigit()]
    products = Produto.objects.filter(tenant=tenant, pk__in=ids, status=True, exibir=True).select_related('category')
    items = [product_item(product, tenant, cart[str(product.pk)]) for product in products
             if type(cart.get(str(product.pk))) is int and cart[str(product.pk)] > 0]
    return ecommerce_data(tenant, items)


def order_data(order):
    items = []
    for entry in order.ordemitem_set.filter(tenant_id=order.tenant_id, produto__tenant_id=order.tenant_id).select_related('produto__category'):
        items.append(product_item(entry.produto, order.tenant, entry.quantidade, entry.preco_unitario))
    data = ecommerce_data(order.tenant, items)
    data['transaction_id'] = f'{order.tenant_id}-{order.pk}'
    data['shipping'] = float(order.tx_entrega or 0)
    return data
