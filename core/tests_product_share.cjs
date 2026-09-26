const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(__dirname + '/assets/app/estabelecimento/js/product-share.js', 'utf8');
const data = {title: 'Ação & "Produto"', native_text: 'Ação — R$ 89,90', url: 'https://loja.example/loja/datail/31', whatsapp_url: 'https://api.whatsapp.com/send?text=mensagem'};
function setup(share) {
    const button = {disabled: false};
    const redirects = [];
    const context = {navigator: {share}, document: {getElementById: id => id === 'shareProductWhatsApp' ? button : {textContent: JSON.stringify(data)}}, window: {location: {assign: url => redirects.push(url)}}};
    vm.createContext(context);
    vm.runInContext(source, context);
    return {context, button, redirects};
}
test('compartilha título, texto e URL uma vez, sem fallback', async () => {
    let payload;
    const state = setup(async value => {payload = value;});
    await state.context.compartilharProduto();
    assert.equal(payload.title, data.title);
    assert.equal(payload.text, data.native_text);
    assert.equal(payload.url, data.url);
    assert.equal(payload.files, undefined);
    assert.deepEqual(state.redirects, []);
    assert.equal(state.button.disabled, false);
});
test('cancelamento não abre WhatsApp', async () => {
    const state = setup(async () => {throw {name: 'AbortError'};});
    await state.context.compartilharProduto();
    assert.deepEqual(state.redirects, []);
    assert.equal(state.button.disabled, false);
});
for (const [name, share] of [['sem API', undefined], ['erro da API', async () => {throw {name: 'NotAllowedError'};}]]) {
    test(name + ' usa fallback na mesma aba', async () => {
        const state = setup(share);
        await state.context.compartilharProduto();
        assert.deepEqual(state.redirects, [data.whatsapp_url]);
        assert.equal(state.button.disabled, false);
    });
}
test('ignora segundo clique enquanto o menu está aberto', async () => {
    let complete;
    let calls = 0;
    const state = setup(() => {calls++; return new Promise(resolve => {complete = resolve;});});
    const pending = state.context.compartilharProduto();
    await state.context.compartilharProduto();
    assert.equal(calls, 1);
    complete();
    await pending;
    assert.equal(state.button.disabled, false);
});
