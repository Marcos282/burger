/* Dados escapados pelo json_script do Django; nenhuma imagem é enviada como arquivo. */
async function compartilharProduto() {
    const button = document.getElementById('shareProductWhatsApp');
    if (button.disabled) return;
    const data = JSON.parse(document.getElementById('productShareData').textContent);
    button.disabled = true;
    try {
        if (typeof navigator.share === 'function') {
            try {
                await navigator.share({title: data.title, text: data.native_text, url: data.url});
                return;
            } catch (error) {
                if (error && error.name === 'AbortError') return;
            }
        }
        // Na mesma aba: funciona também quando o erro assíncrono perde a
        // ativação do clique e o navegador bloquearia uma nova janela.
        window.location.assign(data.whatsapp_url);
    } finally {
        button.disabled = false;
    }
}
