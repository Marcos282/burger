const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(__dirname + '/../core/assets/app/estabelecimento/js/commerce-analytics.js', 'utf8');
const product = {tenant_id: 7, product_id: 31, currency: 'BRL', value: 10, items: [{item_id: '31', price: 10, quantity: 1}]};
function boot({nodes = {}, measurement = 'G-STORE', gtm = '', storage = {}, clipboardFails = false} = {}) {
    const calls = [], listeners = {}, prompts = [];
    let ajax;
    const context = {
        document: {currentScript: {dataset: {measurement, gtm}}, getElementById: id => nodes[id] ? {textContent: JSON.stringify(nodes[id])} : null,
            addEventListener: (name, fn) => {listeners[name] = fn;}},
        window: {gtag: (...args) => calls.push(args), jQuery: () => ({ajaxSuccess: fn => {ajax = fn;}}), prompt: (...args) => prompts.push(args)},
        navigator: {clipboard: {writeText: async () => {if (clipboardFails) throw Error('Denied');}}},
        sessionStorage: {getItem: key => storage[key], setItem: (key, value) => {storage[key] = value;}},
    };
    vm.runInNewContext(source, context);
    return {calls, listeners, context, ajax, prompts};
}
test('view_item usa somente o ID da loja', () => {
    const app = boot({nodes: {productAnalyticsData: product}});
    assert.equal(app.calls[0][1], 'view_item');
    assert.equal(app.calls[0][2].send_to, 'G-STORE');
});
test('sem configuração não envia eventos', () => {
    assert.equal(boot({measurement: '', nodes: {productAnalyticsData: product}}).calls.length, 0);
});
test('GTM recebe evento e ecommerce', () => {
    const app = boot({measurement: '', gtm: 'GTM-STORE', nodes: {productAnalyticsData: product}});
    assert.equal(app.context.window.dataLayer[1].event, 'view_item');
    assert.equal(app.context.window.dataLayer[1].ecommerce.tenant_id, 7);
});
test('cliques medem intenção sem interceptar link HTML', async () => {
    const app = boot({nodes: {productAnalyticsData: product}});
    await app.listeners.click({target: {closest: selector => selector === '[data-share-method]' ? {dataset: {shareMethod: 'whatsapp'}} : null}});
    assert.deepEqual(app.calls.map(x => x[1]), ['view_item', 'share_product', 'click_whatsapp']);
});
test('cópia falha sem emitir sucesso', async () => {
    const app = boot({nodes: {productAnalyticsData: product}, clipboardFails: true});
    await app.listeners.click({target: {closest: selector => selector === '[data-copy-product-link]' ? {dataset: {copyProductLink: 'https://store/product'}} : null}});
    assert.equal(app.prompts.length, 1);
    assert.equal(app.calls.length, 1);
});
test('add_to_cart exige resposta de sucesso com payload', () => {
    const app = boot();
    app.ajax(null, {responseJSON: {status: 'error', analytics: product}});
    assert.equal(app.calls.length, 0);
    app.ajax(null, {responseJSON: {status: 'ok', analytics: product}});
    assert.equal(app.calls[0][1], 'add_to_cart');
});
test('begin_checkout emitido uma vez', () => {
    const app = boot({nodes: {checkoutAnalyticsData: product}});
    app.listeners.submit({target: {matches: () => true}});
    app.listeners.submit({target: {matches: () => true}});
    assert.equal(app.calls.length, 1);
    assert.equal(app.calls[0][1], 'begin_checkout');
});
test('purchase não repete em recarregamento e isola transaction_id', () => {
    const storage = {};
    const options = {storage, nodes: {purchaseAnalyticsData: {...product, transaction_id: '7-123'}}};
    assert.equal(boot(options).calls.length, 1);
    assert.equal(boot(options).calls.length, 0);
    options.nodes.purchaseAnalyticsData.transaction_id = '8-123';
    assert.equal(boot(options).calls.length, 1);
});
