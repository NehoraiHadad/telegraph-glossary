// Mini App journey: the app runs inside a simulated Telegram client.
// The stub mimics Telegram.WebApp (signed initData, CloudStorage, openTelegramLink, theme).
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const BOT_TOKEN = '123:fake';
const OUT = process.env.OUT, CALLS = process.env.CALLS, SECRET = process.env.SECRET;
const hook = (u) => fetch('http://127.0.0.1:8787/telegram', { method: 'POST', headers: { 'x-telegram-bot-api-secret-token': SECRET }, body: JSON.stringify(u) });
const calls = () => fs.readFileSync(CALLS, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const step = (s) => console.log('▸', s);

function initData(user) {
  const p = new URLSearchParams({ auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'AAE', user: JSON.stringify(user) });
  const check = [...p.entries()].map(([k, v]) => `${k}=${v}`).sort().join('\n');
  const secret = crypto.createHmac('sha256', 'WebAppData').update(BOT_TOKEN).digest();
  p.set('hash', crypto.createHmac('sha256', secret).update(check).digest('hex'));
  return p.toString();
}

// The "Telegram cloud" lives in node, shared by every simulated device of the same user.
const cloud = {};
function stub(user, scheme) {
  return `(() => {
    const listeners = {};
    const call = (name, arg) => window.__tg(name, arg);
    window.Telegram = { WebApp: {
      initData: ${JSON.stringify(initData(user))},
      initDataUnsafe: { user: ${JSON.stringify(user)} },
      version: '9.1', platform: 'android', colorScheme: '${scheme}',
      themeParams: ${scheme === 'dark'
        ? "{ bg_color:'#17212b', secondary_bg_color:'#0e1621', text_color:'#f5f5f5', hint_color:'#708499', link_color:'#6ab3f3', button_color:'#5288c1', button_text_color:'#ffffff', destructive_text_color:'#ec3942', section_separator_color:'#111921' }"
        : "{ bg_color:'#ffffff', secondary_bg_color:'#f1f1f1', text_color:'#000000', hint_color:'#999999', link_color:'#2481cc', button_color:'#2481cc', button_text_color:'#ffffff' }"},
      isVersionAtLeast: (v) => parseFloat(v) <= 9.1,
      ready: () => call('ready'), expand: () => call('expand'), setHeaderColor: () => {},
      onEvent: (e, fn) => { (listeners[e] ||= []).push(fn); }, __emit: (e) => (listeners[e] || []).forEach((f) => f()),
      openTelegramLink: (u) => call('openTelegramLink', u), openLink: (u) => call('openLink', u),
      showConfirm: (m, cb) => call('showConfirm', m).then((ok) => cb(ok)),
      HapticFeedback: { notificationOccurred: () => {} },
      CloudStorage: {
        getItem: (k, cb) => call('cloudGet', k).then((v) => cb(null, v ?? '')),
        setItem: (k, v, cb) => call('cloudSet', [k, v]).then(() => cb && cb(null, true)),
        removeItem: (k, cb) => call('cloudRemove', k).then(() => cb && cb(null, true)),
      },
    } };
  })();`;
}

async function device(browser, user, scheme, viewport) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2, locale: 'en-US' });
  const log = [];
  await ctx.exposeFunction('__tg', async (name, arg) => {
    log.push([name, arg]);
    if (name === 'cloudGet') return cloud[arg] ?? null;
    if (name === 'cloudSet') { cloud[arg[0]] = arg[1]; return true; }
    if (name === 'cloudRemove') { delete cloud[arg]; return true; }
    if (name === 'showConfirm') return true;
  });
  await ctx.route('https://telegram.org/js/telegram-web-app.js*', (r) => r.fulfill({ contentType: 'text/javascript', body: stub(user, scheme) }));
  const page = await ctx.newPage();
  const errs = []; page.on('pageerror', (e) => errs.push(e.message));
  return { page, log, errs, ctx };
}

(async () => {
  const browser = await chromium.launch();
  const user = { id: 4242, first_name: 'Noa', language_code: 'he' };

  step('phone 1: first open from the bot');
  const a = await device(browser, user, 'dark', { width: 390, height: 844 });
  await a.page.goto('http://localhost:8766/#tgWebAppData=x&tgWebAppVersion=9.1');
  await a.page.waitForSelector('.welcome');
  console.log('  language from Telegram:', await a.page.getAttribute('html', 'lang'), '| ready/expand:', a.log.filter(([n]) => n === 'ready' || n === 'expand').length === 2);
  await a.page.fill('#gname', 'מילון מהטלפון');
  await a.page.click('.create button[type=submit]');
  await a.page.waitForSelector('.setup', { timeout: 20000 });
  console.log('  key stored in Telegram cloud:', !!cloud.tgg_key);
  console.log('  step 3 already done:', await a.page.$eval('.steps li:nth-child(3)', (e) => e.className));
  await a.page.screenshot({ path: OUT + '/m1-created-dark.png' });

  step('add a term');
  await a.page.click('.steps li:nth-child(1) button');
  await a.page.fill('#f-term', 'API');
  await a.page.fill('#f-def', 'ממשק תכנות.');
  await a.page.click('dialog .btn.primary');
  await a.page.waitForSelector('dialog', { state: 'detached', timeout: 20000 });

  step('connect a channel without leaving for /start');
  await a.page.click('.steps li:nth-child(2) button');
  await a.page.click('main .btn.primary.lg');
  await sleep(1500);
  const opened = a.log.filter(([n]) => n === 'openTelegramLink').map(([, u]) => u);
  console.log('  openTelegramLink:', opened);
  await hook({ update_id: 10, my_chat_member: { chat: { id: -100777, type: 'channel', title: 'ערוץ הטלפון' }, from: user, date: 0,
    old_chat_member: { status: 'left' }, new_chat_member: { status: 'administrator', can_edit_messages: true, user: { id: 1 } } } });
  await sleep(1500);
  await a.page.evaluate(() => window.Telegram.WebApp.__emit('activated'));
  await a.page.waitForSelector('.chans li', { timeout: 10000 });
  console.log('  connected:', await a.page.$$eval('.chans li', (l) => l.map((x) => x.textContent)));
  console.log('  bot DM:', calls().filter((c) => c.method === 'sendMessage').at(-1).params.text.split('\n')[0]);
  await a.page.screenshot({ path: OUT + '/m2-connected-dark.png' });

  step('links go through Telegram, not window.open');
  await a.page.click('[role=tab]:nth-child(1)');
  await a.page.click('.terms a.btn');
  console.log('  openLink:', a.log.filter(([n]) => n === 'openLink').map(([, u]) => u));

  step('settings: key section inside Telegram');
  await a.page.click('.top [aria-label="הגדרות"]');
  await a.page.waitForSelector('dialog');
  console.log('  download hidden:', !(await a.page.$('dialog >> text=הורדה')), '| cloud note:', !!(await a.page.$('dialog .ok.small')));
  await a.page.screenshot({ path: OUT + '/m3-settings-dark.png' });

  step('phone 2: same Telegram user, new device, light theme');
  const b = await device(browser, user, 'light', { width: 390, height: 844 });
  await b.page.goto('http://localhost:8766/#tgWebAppData=x');
  await b.page.waitForSelector('.top', { timeout: 20000 });
  console.log('  opened straight into:', await b.page.textContent('.brand'), '| no welcome:', !(await b.page.$('.welcome')));
  await b.page.screenshot({ path: OUT + '/m4-second-device-light.png' });

  step('normal browser is unaffected');
  const c = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await c.route('https://telegram.org/js/telegram-web-app.js*', (r) => r.fulfill({ contentType: 'text/javascript', body: 'window.Telegram={WebApp:{initData:"",initDataUnsafe:{}}}' }));
  const cp = await c.newPage();
  await cp.goto('http://localhost:8766/');
  await cp.waitForSelector('.welcome');
  console.log('  browser shows welcome:', true);

  console.log('errors:', [...a.errs, ...b.errs]);
  await browser.close();
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
