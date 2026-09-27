"""Gera cartão tipográfico de marca em PNG, sem serviços externos."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
image = Image.new('RGB', (1200, 630), '#111827')
draw = ImageDraw.Draw(image)
font_dir = Path('/usr/share/fonts/truetype/dejavu')
def font(size, bold=False):
    return ImageFont.truetype(str(font_dir / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size)

draw.rectangle((0, 0, 1199, 11), fill='#25d366')
draw.rounded_rectangle((72, 62, 136, 115), radius=16, outline='#25d366', width=5)
draw.polygon([(82, 111), (78, 129), (104, 115)], fill='#25d366')
draw.text((158, 53), 'ViaZap', font=font(56, True), fill='white')
draw.text((72, 182), 'Sua loja online.', font=font(64, True), fill='white')
draw.text((72, 273), 'Seus produtos. Seus pedidos.', font=font(43), fill='#e5e7eb')
draw.text((72, 346), 'Seu WhatsApp.', font=font(60, True), fill='#25d366')
draw.line((72, 465, 1128, 465), fill='#374151', width=2)
draw.text((72, 512), 'viazap.net', font=font(34, True), fill='white')
draw.text((692, 520), 'Delivery • Varejo • Negócios', font=font(24), fill='#d1d5db')
image.save(ROOT / 'core/assets/institucional/viazap-social.png', optimize=True)
