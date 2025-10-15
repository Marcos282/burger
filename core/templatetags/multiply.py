from django import template
import os

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def basename(value):
    """Retorna apenas o nome do arquivo (sem o caminho)"""
    if value:
        return os.path.basename(str(value))
    return ''
