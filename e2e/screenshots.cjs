// Regenerates the README screenshots in docs/screenshots/ (Hebrew UI, a finished glossary).
// Fully offline, see fake-env.cjs.
// Run:  NODE_PATH=$(npm root -g) node e2e/screenshots.cjs
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { start, FAKE_KEY, CONTENT } = require('./fake-env.cjs');

const OUT = path.resolve(__dirname, '..', 'docs', 'screenshots');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const C = CONTENT.he;

(async () => {
  const env = await start({ seed: { title: C.title, terms: C.terms } });
  env.bot.channels = [{ id: -100123, title: C.channel }]; // a connected channel, so the setup checklist is done
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await env.newContext(browser, { locale: C.locale });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  const shot = (name, opts = {}) => page.screenshot({ path: path.join(OUT, name), ...opts });
  // app screens: crop the empty space under the content
  const shotContent = async (name) => {
    const bottom = await page.evaluate(() => Math.ceil(document.querySelector('main').getBoundingClientRect().bottom));
    await shot(name, { fullPage: true, clip: { x: 0, y: 0, width: 420, height: bottom + 32 } });
  };
  const tab = (i) => page.click(`[role=tab] >> nth=${i}`);

  // welcome (no key yet)
  await page.goto(env.base);
  await page.waitForSelector('.welcome');
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(500);
  await shot('welcome.png', { fullPage: true });

  // open the seeded glossary with its fake key, finished setup
  await page.evaluate((key) => {
    const s = (k, v) => localStorage.setItem('tgg.' + k, JSON.stringify(v));
    s('token', key); s('lang', 'he'); s('keySaved', true); s('tried', true); s('tab', 'terms');
  }, FAKE_KEY);
  await page.goto(env.base);
  await page.waitForSelector('.terms li');
  await sleep(500);
  await shotContent('terms.png');

  await tab(1);
  await page.fill('.post textarea', C.post);
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(300);
  await shotContent('post.png');

  await tab(2);
  await page.waitForSelector('.chans li');
  await sleep(300);
  await shotContent('channel.png');

  await browser.close();
  env.close();
  console.log('written:', fs.readdirSync(OUT).filter((f) => f.endsWith('.png')).map((f) => `${f} ${Math.round(fs.statSync(path.join(OUT, f)).size / 1024)}KB`).join(', '));
  if (env.outside.length) console.log('blocked outside requests:', env.outside);
  if (errs.length) console.log('page errors:', errs);
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
