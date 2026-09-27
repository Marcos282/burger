const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(__dirname + '/../core/assets/institucional/analytics.js', 'utf8');
function boot() {
    const events = [];
    let click, pricing, disconnected = false;
    class Observer {
        constructor(callback) {pricing = callback;}
        observe() {}
        disconnect() {disconnected = true;}
    }
    const window = {location: {href: 'https://www.viazap.net/', origin: 'https://www.viazap.net'},
        gtag: (...args) => events.push(args), IntersectionObserver: Observer};
    vm.runInNewContext(source, {window, URL, IntersectionObserver: Observer,
        document: {getElementById: () => ({}), addEventListener: (_name, fn) => {click = fn;}}});
    return {events, click: href => click({target: {closest: () => ({href})}}), pricing: () => pricing([{isIntersecting: true}]), disconnected: () => disconnected};
}
test('cadastro e login enviam nomes de eventos sem URL ou PII', () => {
    const app = boot();
    app.click('https://www.viazap.net/register/');
    app.click('https://www.viazap.net/login/');
    assert.deepEqual(app.events.map(event => event[1]), ['sign_up_click', 'tenant_signup_start', 'login_click']);
    for (const event of app.events) assert.equal(JSON.stringify(event[2]), '{"send_to":"G-C4BWMDXFPQ"}');
});
test('link de demonstração de tenant não inicia cadastro institucional', () => {
    const app = boot();
    app.click('https://andreia.viazap.net/register/');
    assert.equal(app.events.length, 0);
});
test('pricing_view desconecta observador após visualizar seção', () => {
    const app = boot();
    app.pricing();
    assert.equal(app.events[0][1], 'pricing_view');
    assert.equal(app.disconnected(), true);
});
