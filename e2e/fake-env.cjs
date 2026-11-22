// Offline environment shared by the screenshot scripts (screenshots.cjs, guide.cjs).
// web/ is served from a local port; Telegraph and the channel bot are faked in memory.
// Nothing leaves the machine except web fonts. No real tokens: the key below is a placeholder.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..');
const WEB = path.join(ROOT, 'web');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.txt': 'text/plain; charset=utf-8' };
const FAKE_KEY = 'fake-key-for-screenshots';
const BOT_USERNAME = 'GlossaryDemoBot';
const CORS = { 'access-control-allow-origin': '*' };

// ---------------------------------------------------------------- fake Telegraph (in memory)
// `seed` = { title, terms: [{ term, aliases, def }] } starts with a glossary; omit it to start empty.
function makeTelegraph(core, seed) {
  const pages = new Map();
  let n = 0;
  const account = { short_name: '', author_name: '', author_url: '' };
  const newPath = (title) => `${title.replace(/[^A-Za-z0-9]/g, '') || 'p'}-${++n}`;
  const put = (title, content) => { const p = newPath(title); pages.set(p, { path: p, title, content, views: 0 }); return p; };
  const url = (p) => `https://telegra.ph/${encodeURIComponent(p)}`;

  if (seed) {
    const list = seed.terms.map((t) => ({ term: t.term, aliases: t.aliases, path: put(t.term, core.markdownToNodes(t.def)) }));
    const indexPath = put(seed.title, core.buildIndex(list, seed.title));
    Object.assign(account, { short_name: seed.title, author_name: seed.title, author_url: url(indexPath) });
  }

  const handle = (method, q) => {
    const j = (k) => (q.get(k) === null ? undefined : JSON.parse(q.get(k)));
    switch (method) {
      case 'createAccount':
        Object.assign(account, { short_name: q.get('short_name'), author_name: q.get('author_name') });
        return { ...account, access_token: FAKE_KEY };
      case 'getAccountInfo': return { ...account, page_count: pages.size };
      case 'editAccountInfo':
        for (const k of ['short_name', 'author_name', 'author_url']) if (q.get(k) !== null) account[k] = q.get(k);
        return account;
      case 'createPage': { const p = put(q.get('title'), j('content')); return { path: p, url: url(p), title: q.get('title') }; }
      case 'editPage': { const pg = pages.get(q.get('path')); Object.assign(pg, { title: q.get('title'), content: j('content') }); return pg; }
      case 'getPage': { const pg = pages.get(q.get('path')); if (!pg) throw new Error('PAGE_NOT_FOUND'); return pg; }
      case 'getPageList': return { total_count: pages.size, pages: [...pages.values()] };
      case 'getViews': return { views: 0 };
      default: throw new Error(`fake Telegraph: unexpected method ${method}`);
    }
  };
  return { handle };
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

/**
 * Starts the site + fakes. Returns { base, bot, outside, newContext(browser, opts), close() }.
 * `bot.channels` is what the fake bot reports as connected (the script changes it to "connect").
 */
async function start({ seed = null } = {}) {
  const core = { ...(await import(pathToFileURL(path.join(WEB, 'core', 'glossary.js')).href)), ...(await import(pathToFileURL(path.join(WEB, 'core', 'markdown.js')).href)) };
  const tele = makeTelegraph(core, seed);
  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}/`;
  const bot = { channels: [] };
  const outside = [];

  async function newContext(browser, opts = {}) {
    const ctx = await browser.newContext({ viewport: { width: 420, height: 860 }, deviceScaleFactor: 2, colorScheme: 'light', ...opts });
    await ctx.route('**/*', (r) => {
      const u = r.request().url();
      if (u.startsWith(base) || u.startsWith('data:') || u.startsWith('blob:') || u === 'about:blank') return r.fallback();
      if (u.startsWith('https://api.telegra.ph/')) {
        const method = new URL(u).pathname.slice(1);
        let body;
        try { body = { ok: true, result: tele.handle(method, new URLSearchParams(r.request().postData() || '')) }; }
        catch (e) { body = { ok: false, error: e.message }; }
        return r.fulfill({ json: body, headers: CORS });
      }
      if (u.startsWith('http://bot.test/')) {
        const p = new URL(u).pathname;
        const json = p === '/api/info' ? { bot_username: BOT_USERNAME }
          : p === '/api/status' ? { channels: bot.channels }
          : p === '/api/connect' ? { start_url: `https://t.me/${BOT_USERNAME}?start=demo` } : {};
        return r.fulfill({ json, headers: CORS });
      }
      if (u.startsWith('https://t.me/')) return r.fulfill({ body: 'telegram' }); // the "Connect" button opens this; the guide describes the Telegram side in text
      if (/^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(u)) return r.continue(); // web fonts only
      if (u.startsWith('https://telegram.org/js/')) return r.fulfill({ body: '', contentType: 'text/javascript' }); // Mini App SDK: not wanted here
      outside.push(u); r.abort();
    });
    await ctx.route(base + 'config.json', (r) => r.fulfill({ json: { bot_api: 'http://bot.test' } }));
    return ctx;
  }

  return { base, bot, outside, newContext, close: () => srv.close() };
}

// Sample content in both UI languages (the first term is the one typed in the guide's "new term" form).
const CONTENT = {
  he: {
    locale: 'he-IL',
    title: 'מילון הערוץ',
    channel: 'ערוץ הדוגמה',
    terms: [
      { term: 'פייתון', aliases: ['Python'], def: 'שפת תכנות פשוטה לקריאה, נפוצה באנליזה, באוטומציה ובבינה מלאכותית.' },
      { term: 'API', aliases: [], def: '**ממשק תכנות**: הדרך שבה תוכנה אחת מבקשת מידע או פעולה מתוכנה אחרת.' },
      { term: 'Docker', aliases: [], def: 'כלי שמריץ תוכנה בתוך "קונטיינר" מבודד, כך שהיא עובדת אותו דבר בכל מחשב.' },
      { term: 'JSON', aliases: [], def: 'פורמט טקסט פשוט להעברת נתונים בין תוכנות, בנוי מזוגות של שם וערך.' },
    ],
    post: 'מתחילים היום עם פייתון: נכתוב סקריפט קטן שקורא ל-API ושומר את התשובה כ-JSON. בסוף נארוז הכול ב-Docker.',
  },
  en: {
    locale: 'en-US',
    title: 'Channel glossary',
    channel: 'Demo channel',
    terms: [
      { term: 'Python', aliases: ['py'], def: 'A programming language that is easy to read, popular for data work, automation and AI.' },
      { term: 'API', aliases: [], def: '**Application programming interface**: the way one program asks another for data or an action.' },
      { term: 'Docker', aliases: [], def: 'A tool that runs software in an isolated "container", so it behaves the same on every computer.' },
      { term: 'JSON', aliases: [], def: 'A simple text format for passing data between programs, made of names and values.' },
    ],
    post: 'Today we start with Python: a small script that calls an API and saves the answer as JSON. Then we pack it all in Docker.',
  },
};

module.exports = { start, FAKE_KEY, CONTENT };
