const { chromium } = require('playwright');
const fs = require('fs');
const SECRET = process.env.SECRET;
const hook = (u) => fetch('http://127.0.0.1:8787/telegram', { method: 'POST', headers: { 'x-telegram-bot-api-secret-token': SECRET }, body: JSON.stringify(u) });
const calls = () => fs.readFileSync(process.env.CALLS, 'utf8').trim().split('\n').map(JSON.parse);
const edits = () => calls().filter(c => c.method.startsWith('edit'));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const step = (s) => console.log('▸', s);

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, locale: 'he-IL', permissions: ['clipboard-read', 'clipboard-write'] });
  await ctx.route('https://t.me/**', r => r.fulfill({ body: 'telegram' })); // don't leave the sandbox
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  let startUrl = null;
  p.on('response', async r => { if (r.url().endsWith('/api/connect')) startUrl = (await r.json()).start_url; });

  step('welcome');
  await p.goto('http://localhost:8766/');
  await p.waitForSelector('.welcome'); await sleep(1600);
  await p.screenshot({ path: process.env.OUT + '/j1-welcome.png' });
  await p.fill('#gname', 'מילון הערוץ');
  await p.click('text=יצירת מילון');
  await p.waitForSelector('.setup', { timeout: 20000 });
  await p.screenshot({ path: process.env.OUT + '/j2-empty.png' });

  step('step 1: first term from the checklist');
  await p.click('.steps li:nth-child(1) button');
  await p.fill('#f-term', 'API');
  await p.fill('#f-def', '**ממשק תכנות** שדרכו תוכנות מדברות זו עם זו.');
  await p.fill('#f-aka', 'APIs, ממשק תכנות');
  await p.screenshot({ path: process.env.OUT + '/j3-term.png' });
  await p.click('dialog >> text=שמירה');
  await p.waitForSelector('dialog', { state: 'detached', timeout: 20000 });
  console.log('  step1 done:', await p.$eval('.steps li:nth-child(1)', e => e.className));

  step('step 2: connect channel');
  await p.click('.steps li:nth-child(2) button');
  await p.screenshot({ path: process.env.OUT + '/j4-channel.png' });
  const [popup] = await Promise.all([ctx.waitForEvent('page'), p.click('text=חיבור ערוץ')]);
  await sleep(800);
  const code = startUrl.split('start=')[1];
  console.log('  start url:', startUrl);
  console.log('  waiting text:', await p.textContent('.row .muted'));
  // what Telegram would send when the user presses Start, then adds the bot to a channel
  await hook({ update_id: 1, message: { message_id: 1, chat: { id: 7, type: 'private' }, from: { id: 7, language_code: 'he', first_name: 'Dana' }, text: `/start ${code}` } });
  await sleep(1500);
  await hook({ update_id: 2, my_chat_member: { chat: { id: -100555, type: 'channel', title: 'ערוץ הפיתוח' }, from: { id: 7, language_code: 'he' }, date: 0,
    old_chat_member: { status: 'left' }, new_chat_member: { status: 'administrator', can_edit_messages: true, user: { id: 1 } } } });
  await sleep(1500);
  await popup.close();
  await p.bringToFront();
  await p.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await p.waitForSelector('.chans li', { timeout: 10000 });
  console.log('  channels:', await p.$$eval('.chans li', l => l.map(x => x.textContent)));
  const dms = calls().filter(c => c.method === 'sendMessage').map(c => c.params.text.split('\n')[0]);
  console.log('  bot DMs:', dms);
  console.log('  add-to-channel button:', calls().find(c => c.params.reply_markup)?.params.reply_markup.inline_keyboard[0][0].url);
  await p.screenshot({ path: process.env.OUT + '/j5-connected.png' });

  step('user posts in the channel');
  await hook({ update_id: 3, channel_post: { message_id: 42, chat: { id: -100555, type: 'channel', title: 'ערוץ הפיתוח' }, date: 0,
    text: 'היום נלמד על API ועל Docker 🚀', entities: [{ type: 'bold', offset: 0, length: 4 }] } });
  await sleep(2500);
  const e1 = edits().at(-1);
  console.log('  edit:', e1?.method, JSON.stringify(e1?.params.entities));

  step('step 3: save key');
  await p.click('.steps li:nth-child(3) button');
  await p.waitForSelector('dialog');
  await p.screenshot({ path: process.env.OUT + '/j6-settings.png' });
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('dialog >> text=הורדה')]);
  console.log('  downloaded:', dl.suggestedFilename());
  await p.keyboard.press('Escape');
  await sleep(300);
  console.log('  checklist gone:', !(await p.$('.setup')));

  step('add a term later -> old post updates');
  const before = edits().length;
  await p.click('[role=tab]:has-text("מונחים")');
  await p.click('.toolbar >> text=מונח חדש');
  await p.fill('#f-term', 'Docker');
  await p.fill('#f-def', 'כלי שמריץ תוכנה בתוך "קונטיינר" מבודד.');
  await p.click('dialog >> text=שמירה');
  await p.waitForSelector('dialog', { state: 'detached', timeout: 20000 });
  await sleep(4000);
  const e2 = edits().slice(before).find(e => e.params.message_id === 42);
  console.log('  re-edit of post 42:', JSON.stringify(e2?.params.entities?.filter(x => x.type === 'text_link').map(x => [x.offset, x.length])));
  await p.screenshot({ path: process.env.OUT + '/j7-terms.png' });

  step('post tab');
  await p.click('[role=tab]:has-text("פוסט")');
  await p.fill('.post textarea', 'מריצים Docker ומדברים עם ה-API של השרת. API נוסף.');
  await sleep(200);
  await p.screenshot({ path: process.env.OUT + '/j8-post.png' });

  step('agents tab');
  await p.click('[role=tab]:has-text("סוכני AI")');
  await p.screenshot({ path: process.env.OUT + '/j9-agents.png' });
  await p.click('.ag >> text=העתקה');
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  const token = await p.evaluate(() => JSON.parse(localStorage.getItem('tgg.token')));
  console.log('  copied command has real key:', clip.includes(token), '| shown masked:', !(await p.textContent('pre.cmd')).includes(token));
  fs.writeFileSync(process.env.OUT + '/token.txt', token);

  step('forward an old post to the bot');
  await hook({ update_id: 4, message: { message_id: 5, chat: { id: 7, type: 'private' }, from: { id: 7, language_code: 'he' }, date: 0, text: 'פוסט ישן על API',
    forward_origin: { type: 'channel', chat: { id: -100555, type: 'channel', title: 'ערוץ הפיתוח' }, message_id: 7, date: 0 } } });
  await sleep(2000);
  console.log('  edited old post 7:', !!edits().find(e => e.params.message_id === 7), '| reply:', calls().filter(c => c.method === 'sendMessage').at(-1).params.text);

  step('language switch');
  await p.click('.top .lang-switch button[lang=en]');
  console.log('  tabs in English:', await p.$$eval('[role=tab]', ts => ts.map(t => t.textContent)), '| dir:', await p.getAttribute('html', 'dir'));
  await p.screenshot({ path: process.env.OUT + '/j11-english.png' });
  await p.click('.top .lang-switch button[lang=he]');
  console.log('  back to Hebrew:', await p.getAttribute('html', 'dir'));

  step('mobile');
  const m = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'he-IL' });
  const mp = await m.newPage();
  await mp.goto('http://localhost:8766/#key=' + encodeURIComponent(token));
  await mp.waitForSelector('.top', { timeout: 20000 });
  await mp.click('[role=tab]:has-text("ערוץ")');
  await sleep(500);
  await mp.screenshot({ path: process.env.OUT + '/j10-mobile-channel.png', fullPage: true });
  console.log('  mobile overflow:', await mp.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  console.log('errors:', errs);
  await b.close();
})().catch(e => { console.error('FAILED', e); process.exit(1); });
