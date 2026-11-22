// Captures the new-user walkthrough for docs/GUIDE.md and docs/GUIDE.he.md:
// docs/guide/{he,en}/NN-name.png. Starts from an empty fake Telegraph and drives the real UI.
// Fully offline, see fake-env.cjs. Run:  NODE_PATH=$(npm root -g) node e2e/guide.cjs
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { start, CONTENT } = require('./fake-env.cjs');

const OUT = path.resolve(__dirname, '..', 'docs', 'guide');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function capture(browser, lang) {
  const C = CONTENT[lang];
  const env = await start();
  const dir = path.join(OUT, lang);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const ctx = await env.newContext(browser, { locale: C.locale });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });

  const shot = (name, opts = {}) => page.screenshot({ path: path.join(dir, name + '.png'), ...opts });
  const shotContent = async (name) => { // crop the empty space under the content
    const bottom = await page.evaluate(() => Math.ceil(document.querySelector('main').getBoundingClientRect().bottom));
    await shot(name, { fullPage: true, clip: { x: 0, y: 0, width: 420, height: bottom + 32 } });
  };
  const tab = (i) => page.click(`[role=tab] >> nth=${i}`);
  const fillTerm = async (t) => {
    await page.fill('#f-term', t.term);
    await page.fill('#f-def', t.def);
    if (t.aliases.length) await page.fill('#f-aka', t.aliases.join(', '));
  };
  const submitTerm = async () => {
    await page.click('dialog .df .btn.primary');
    await page.waitForSelector('dialog', { state: 'detached', timeout: 20000 });
  };

  // 01 welcome
  await page.goto(env.base);
  await page.waitForSelector('.welcome');
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(500);
  await shot('01-welcome', { fullPage: true });

  // 02 name typed
  await page.fill('#gname', C.title);
  await shot('02-name', { fullPage: true });

  // 03 empty glossary + setup checklist
  await page.click('.create button[type=submit]');
  await page.waitForSelector('.setup');
  await sleep(2600); // let the toast go
  await shotContent('03-empty');

  // 04 new-term form
  await page.click('.empty .btn.primary');
  await page.waitForSelector('dialog');
  await fillTerm(C.terms[0]);
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(300);
  await shot('04-new-term');
  await submitTerm();

  // 05 terms list
  for (const t of C.terms.slice(1)) {
    await page.click('.toolbar .btn.primary');
    await page.waitForSelector('dialog');
    await fillTerm(t);
    await submitTerm();
  }
  await page.waitForSelector('.terms li >> nth=3');
  await sleep(2600);
  await shotContent('05-terms');

  // 08 post tab (no channel: copy path). Captured here, before a channel is connected.
  await tab(1);
  await page.fill('.post textarea', C.post);
  await page.evaluate(() => document.activeElement?.blur());
  await sleep(300);
  await shotContent('08-post');

  // 06 channel tab, not connected
  await tab(2);
  await page.waitForSelector('.ba');
  await sleep(300);
  await shotContent('06-channel');

  // the button opens the bot link in a new tab (faked, not captured); then the bot reports the channel
  const [popup] = await Promise.all([ctx.waitForEvent('page'), page.click('.row .btn.primary')]);
  await page.waitForSelector('.row .muted .spin');
  env.bot.channels = [{ id: -100123, title: C.channel }];
  await popup.close();
  await page.click('.row .btn.quiet.sm'); // "check again"
  await page.waitForSelector('.chans li');
  await sleep(500);

  // 07 channel tab, connected
  await shotContent('07-channel-connected');

  // 09 settings: save the key
  await page.click('.top-in > .btn.quiet');
  await page.waitForSelector('dialog');
  await sleep(300);
  await shot('09-key');
  await page.keyboard.press('Escape');

  await ctx.close();
  env.close();
  console.log(lang, fs.readdirSync(dir).map((f) => `${f} ${Math.round(fs.statSync(path.join(dir, f)).size / 1024)}KB`).join(', '));
  if (env.outside.length) console.log(lang, 'blocked outside requests:', env.outside);
  if (errs.length) console.log(lang, 'page errors:', errs);
}

(async () => {
  const browser = await chromium.launch();
  for (const lang of ['he', 'en']) await capture(browser, lang);
  await browser.close();
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
