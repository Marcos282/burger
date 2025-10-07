def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace('.', ',')

def formatar_brl_noS(valor):
    return f"{valor:,.2f}".replace('.', ',')

def formatar_brl_to_float(valor_str):
    try:
        valor_str = valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(valor_str)
    except ValueError:
        return 0.0