# burger

## Compartilhamento de produtos

A página pública usa a rota existente `/loja/datail/<id>` (grafia preservada).
O produto é consultado pelo ID e pelo tenant identificado no subdomínio.
Open Graph e Twitter Cards são renderizados no servidor, e o botão WhatsApp
prioriza a Web Share API com título, texto e URL. Sem suporte ou em caso de
erro, usa `api.whatsapp.com/send?text=...`, sem telefone de destinatário.
Cancelar o menu nativo encerra o fluxo. Sem JavaScript, há um link de fallback.

A imagem principal tem prioridade; na ausência dela são usadas galeria,
imagem extra, foto/logo da loja, logo global ou a imagem estática existente.
A descrição é limpa de HTML e limitada a 180 caracteres antes do preço.
`core.utils.product_share_data` concentra os dados para reutilização futura;
não há dependência da Evolution API.

As URLs compartilhadas são HTTPS, inclusive atrás de proxy. Em produção, o
servidor/CDN deve oferecer HTTPS válido e acesso público sem login tanto à
página quanto a `/media/` e aos arquivos estáticos. A configuração Django
para servir mídia em desenvolvimento não substitui essa configuração em
produção. URLs externas de logos/imagens também precisam suportar HTTPS.

Após publicar, verificar a URL de `og:image` sem autenticação e compartilhar
um produto no WhatsApp em celular e desktop. O preview é controlado pelo
WhatsApp e pode ficar em cache após alterações de imagem ou texto.

Testes: `python manage.py test core.tests.ProductSharingTests` (banco de testes
PostgreSQL). A verificação local também pode usar SQLite em memória, criando
as tabelas pelos models com migrations desativadas, pois há migrations do
projeto com SQL específico de PostgreSQL.
