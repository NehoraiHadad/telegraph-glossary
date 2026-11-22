// Regenerates the README screenshots in docs/screenshots/.
// Fully offline: web/ is served locally, Telegraph and the bot are faked in memory.
// Run:  NODE_PATH=$(npm root -g) node e2e/screenshots.cjs
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..');
const WEB = path.join(ROOT, 'web');
const OUT = path.join(ROOT, 'docs', 'screenshots');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.txt': 'text/plain; charset=utf-8' };
const FAKE_KEY = 'fake-key-for-screenshots'; // not a real Telegraph token
const TITLE = 'מילון הערוץ';
const TERMS = [
  { term: 'API', aliases: [], def: '**ממשק תכנות**: הדרך שבה תוכנה אחת מבקשת מידע או פעולה מתוכנה אחרת.' },
  { term: 'פייתון', aliases: ['Python'], def: 'שפת תכנות פשוטה לקריאה, נפוצה באנליזה, באוטומציה ובבינה מלאכותית.' },
  { term: 'Docker', aliases: [], def: 'כלי שמריץ תוכנה בתוך "קונטיינר" מבודד, כך שהיא עובדת אותו דבר בכל מחשב.' },
  { term: 'JSON', aliases: [], def: 'פורמט טקסט פשוט להעברת נתונים בין תוכנות, בנוי מזוגות של שם וערך.' },
];

// ---------------------------------------------------------------- fake Telegraph (in memory)
function makeTelegraph(core) {
  const pages = new Map();
  let n = 0;
  const account = { short_name: TITLE, author_name: TITLE, author_url: '', page_count: 0 };
  const newPath = (title) => `${title.replace(/[^A-Za-z0-9]/g, '') || 'p'}-${++n}`;
  const put = (title, content) => { const p = newPath(title); pages.set(p, { path: p, title, content, views: 0 }); return p; };
  const url = (p) => `https://telegra.ph/${encodeURIComponent(p)}`;

  const termList = TERMS.map((t) => {
    const p = put(t.term, core.markdownToNodes(t.def));
    return { term: t.term, aliases: t.aliases, path: p };
  });
  const indexPath = put(TITLE, core.buildIndex(termList, TITLE));
  account.author_url = url(indexPath);

  const handle = (method, q) => {
    const j = (k) => (q.get(k) === null ? undefined : JSON.parse(q.get(k)));
    switch (method) {
      case 'createAccount': return { ...account, short_name: q.get('short_name'), author_name: q.get('author_name'), access_token: FAKE_KEY };
      case 'getAccountInfo': return { ...account, page_count: pages.size };
      case 'editAccountInfo': return account;
      case 'createPage': { const p = put(q.get('title'), j('content')); return { path: p, url: url(p), title: q.get('title') }; }
      case 'editPage': { const pg = pages.get(q.get('path')); Object.assign(pg, { title: q.get('title'), content: j('content') }); return pg; }
      case 'getPage': { const pg = pages.get(q.get('path')); if (!pg) throw new Error('PAGE_NOT_FOUND'); return pg; }
      case 'getPageList': return { total_count: pages.size, pages: [...pages.values()] };
      case 'getViews': return { views: 0 };
      default: throw new Error(`fake Telegraph: unexpected method ${method}`);
    }
  };
  return { handle, indexPath };
}

// ---------------------------------------------------------------- static server for web/
function serve() {
  const srv = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
    const file = path.join(WEB, rel);
    if (!file.startsWith(WEB) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' }).end(fs.readFileSync(file));
  });
  return new Promise((r) => srv.listen(0, '127.0.0.1', () => r(srv)));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const core = await import(pathToFileURL(path.join(WEB, 'core', 'glossary.js')).href);
  const md = await import(pathToFileURL(path.join(WEB, 'core', 'markdown.js')).href);
  const tele = makeTelegraph({ ...core, ...md });
  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}/`;
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 420, height: 860 }, deviceScaleFactor: 2, colorScheme: 'light', locale: 'he-IL' });
  const outside = [];
  // nothing leaves the machine except through these fakes
  await ctx.route('**/*', (r) => {
    const u = r.request().url();
    if (u.startsWith(base) || u.startsWith('data:') || u.startsWith('blob:')) return r.fallback();
    if (u.startsWith('https://api.telegra.ph/')) {
      const method = new URL(u).pathname.slice(1);
      let body;
      try { body = { ok: true, result: tele.handle(method, new URLSearchParams(r.request().postData() || '')) }; }
      catch (e) { body = { ok: false, error: e.message }; }
      return r.fulfill({ json: body, headers: { 'access-control-allow-origin': '*' } });
    }
    if (u.startsWith('http://bot.test/')) {
      const p = new URL(u).pathname;
      const json = p === '/api/info' ? { bot_username: 'GlossaryDemoBot' }
        : p === '/api/status' ? { channels: [{ id: -100123, title: 'ערוץ הדוגמה' }] } : {};
      return r.fulfill({ json, headers: { 'access-control-allow-origin': '*' } });
    }
    if (/^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(u)) return r.continue(); // web fonts only
    if (u.startsWith('https://telegram.org/js/')) return r.fulfill({ body: '', contentType: 'text/javascript' }); // Mini App SDK: not wanted here
    outside.push(u); r.abort();
  });
  await ctx.route(base + 'config.json', (r) => r.fulfill({ json: { bot_api: 'http://bot.test' } }));

  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  const shot = (name, opts = {}) => page.screenshot({ path: path.join(OUT, name), ...opts });
  // app screens: crop the empty space under the content
  const shotContent = async (name) => {
    const bottom = await page.evaluate(() => Math.ceil(document.querySelector('main').getBoundingClientRect().bottom));
    await shot(name, { clip: { x: 0, y: 0, width: 420, height: Math.min(860, bottom + 32) } });
  };

  // 1. welcome (no key yet)
  await page.goto(base);
  await page.waitForSelector('.welcome');
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(500);
  await shot('welcome.png', { fullPage: true });

  // open the seeded glossary with its fake key, finished setup, Hebrew UI
  await page.evaluate((key) => {
    const s = (k, v) => localStorage.setItem('tgg.' + k, JSON.stringify(v));
    s('token', key); s('lang', 'he'); s('keySaved', true); s('tried', true); s('tab', 'terms');
  }, FAKE_KEY);
  await page.goto(base);
  await page.waitForSelector('.terms li');
  await sleep(500);
  await shotContent('terms.png');

  // 3. post tab
  await page.click('[role=tab]:has-text("פוסט")');
  await page.fill('.post textarea', 'מתחילים היום עם פייתון: נכתוב סקריפט קטן שקורא ל-API ושומר את התשובה כ-JSON. בסוף נארוז הכול ב-Docker.');
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(300);
  await shotContent('post.png');

  // 4. channel tab, connected
  await page.click('[role=tab]:has-text("ערוץ")');
  await page.waitForSelector('.chans li');
  await sleep(300);
  await shotContent('channel.png');

  await browser.close();
  srv.close();
  const big = fs.readdirSync(OUT).filter((f) => f.endsWith('.png')).map((f) => [f, Math.round(fs.statSync(path.join(OUT, f)).size / 1024)]);
  console.log('written:', big.map(([f, k]) => `${f} ${k}KB`).join(', '));
  if (outside.length) console.log('blocked outside requests:', outside);
  if (errs.length) console.log('page errors:', errs);
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
