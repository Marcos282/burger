def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace('.', ',')

def formatar_brl_noS(valor):
    return f"{valor:,.2f}".replace('.', ',')