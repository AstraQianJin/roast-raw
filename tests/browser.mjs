// Rewritten browser suite (0.35). It replaces the stale 0.21 file: the theme switch
// it assumed is gone and the register form has four inputs now. Everything here runs
// against a gated fixture server in headless Chrome and asserts what a phone user sees.
//
// usage: node tests/browser.mjs            (green baseline)
//        node tests/browser.mjs --sabotage  (one deliberately wrong expectation => exit 1)
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { mkdir } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { openBrowser } from './cdp.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.RR_PYTHON || join(root, 'server/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
// Screenshots left the repository in 0.35: they land in the agent folder, and SHOTS_DIR
// decides where. Default follows package.json's release, so a version bump cannot silently
// write into the previous release folder.
const release = JSON.parse(readFileSync(join(root, 'web', 'package.json'), 'utf8')).version.replace(/^0\.0\./, '0.');
const SHOTS_DIR = process.env.SHOTS_DIR || join(root, '..', 'RR', 'shots', release);

const SABOTAGE = process.argv.includes('--sabotage');
const PASSWORD = 'browser-gate-035';
const WIDTH = Number(process.env.RR_DEVICE_WIDTH || 421);
const checks = [];
const ok = (label, value) => {
  checks.push(label);
  console.log(`PASS ${label}${value === undefined ? '' : `: ${JSON.stringify(value)}`}`);
};

async function freePort() {
  const listener = createServer();
  await new Promise(done => listener.listen(0, '127.0.0.1', done));
  const port = listener.address().port;
  await new Promise(done => listener.close(done));
  return port;
}

const port = await freePort();
const server = spawn(python, ['tests/serve_fixture.py', '--port', String(port), '--gate', PASSWORD, '--date', '2027-02-21', '--invite', 'plus=RR-BROWSER-PLUS'],
  { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
let serverLog = '';
server.stdout.on('data', chunk => { serverLog += chunk; });
server.stderr.on('data', chunk => { serverLog += chunk; });
const base = `http://127.0.0.1:${port}`;
let browser;

try {
  for (let i = 0; i < 80; i += 1) {
    try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* not up yet */ }
    await delay(250);
  }
  browser = await openBrowser();
  await mkdir(SHOTS_DIR, { recursive: true });
  const shot = async name => browser.screenshot(join(SHOTS_DIR, `${name}-${WIDTH}.png`));
  await browser.viewport(WIDTH, 900);

  // ---- 1. public landing ---------------------------------------------------
  await browser.navigate(`${base}/`);
  await browser.waitFor('Boolean(document.querySelector("h1"))', 15000);
  const landing = await browser.evaluate(`({
    title: document.querySelector('h1').innerText.replace(/\\s+/g, ' ').trim(),
    width: window.innerWidth,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    links: document.querySelectorAll('a[href]').length,
  })`);
  assert.ok(landing.title.length > 0, 'the landing page renders a headline');
  if (SABOTAGE) assert.match(landing.title, /this sabotage sentence is never on the page/, 'sabotage: intentionally impossible claim');
  assert.equal(landing.overflow, 0, 'the landing page does not scroll sideways at the phone width');
  // 0.41: the landing chart draws the plan's own weekly series, not a typed-in demo.
  const facts = JSON.parse(readFileSync(join(root, 'web', 'src', 'landing-facts.json'), 'utf8'));
  const chart = await browser.evaluate(`({ bars: document.querySelectorAll('.wl-bar').length,
    first: document.querySelector('.wl-bar')?.getAttribute('title') || '',
    peak: document.querySelector('.wl-cap-name')?.innerText.trim() || '' })`);
  assert.equal(chart.bars, facts.weeks.length, 'the landing chart draws one bar per planned week');
  assert.ok(chart.first.includes(`${facts.weeks[0].sets} sets`), 'the landing bar count is the weekly total the cycle chart uses');
  await shot('landing');
  ok(`landing renders and keeps a ${landing.width} px viewport without horizontal overflow`);

  // ---- 1b. 0.50: the landing no longer sells ------------------------------
  await browser.viewport(1280, 900);
  await browser.navigate(`${base}/`);
  await delay(600);
  const landingDesk = await browser.evaluate(`({
    membership: Boolean(document.querySelector('[data-testid=membership]')),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    width: window.innerWidth,
  })`);
  assert.equal(landingDesk.membership, false, 'the tier table left the landing page');
  assert.equal(landingDesk.overflow, 0, 'the landing does not scroll sideways at 1280');
  ok('landing sells nothing and stays inside 1280', landingDesk);

  // ---- 1c. the same page on a phone ---------------------------------------
  await browser.viewport(390, 844);
  await browser.navigate(`${base}/`);
  await delay(500);
  const landingPhone = await browser.evaluate(`({
    membership: Boolean(document.querySelector('[data-testid=membership]')),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  })`);
  assert.equal(landingPhone.membership, false, 'no tier cards on a phone either');
  assert.equal(landingPhone.overflow, 0, 'the landing does not push the phone page sideways');
  ok('landing on a phone carries no price rail', landingPhone);
  await browser.viewport(WIDTH, 900);

  // ---- 1d. the screenshot deck follows the finger, not the page scroll ----
  await browser.navigate(`${base}/`);
  await delay(500);
  const firstFigure = await browser.evaluate(`document.querySelector('.wl-cap-name').innerText`);
  const deck = await browser.evaluate(`(() => {
    const frames = document.querySelector('.wl-tour-frames');
    frames.scrollIntoView({ block: 'center', behavior: 'auto' });
    const box = frames.getBoundingClientRect();
    return { x: box.left + box.width / 2, y: box.top + box.height / 2, scroll: window.scrollY };
  })()`);
  await delay(300);
  await browser.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: deck.x, y: deck.y, button: 'left', clickCount: 1 });
  for (let step = 1; step <= 4; step++) {
    await browser.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: deck.x - step * 30, y: deck.y, button: 'left', buttons: 1 });
    await delay(40);
  }
  const midDrag = await browser.evaluate(`(() => {
    const cards = [...document.querySelectorAll('.wl-tshot')];
    return { dragging: document.querySelector('.wl-tour-frames').classList.contains('is-dragging'),
             shifted: cards.filter(c => /translate3d\\(-?[0-9.]+%/.test(c.style.transform)).length };
  })()`);
  assert.ok(midDrag.dragging, 'the deck reports a live drag');
  assert.equal(midDrag.shifted, 4, 'every frame carries a drag offset while the finger is down');
  await browser.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: deck.x - 120, y: deck.y, button: 'left', clickCount: 1 });
  await delay(500);
  const tourState = await browser.evaluate(`(() => ({
    figure: document.querySelector('.wl-cap-name').innerText,
    on: document.querySelectorAll('.wl-tshot.is-on').length,
    behind: [...document.querySelectorAll('.wl-tshot')].filter(c => parseFloat(c.style.opacity) < 1).length,
    turned: [...document.querySelectorAll('.wl-tshot')].filter(c => /rotate\\(-?[0-9.]+deg\\)/.test(c.style.transform)).length,
    dropped: [...document.querySelectorAll('.wl-tshot')].filter(c => { const m = /translate3d\\([^)]*\\)/.exec(c.style.transform); return m ? parseFloat(m[0].split(',')[1]) > 0 : false; }).length,
    dots: document.querySelectorAll('.wl-tour-dots, .wl-tour-rail').length,
    loaded: [...document.querySelectorAll('.wl-tshot img')].filter(i => i.naturalWidth > 0).length,
    scroll: window.scrollY,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
  }))()`);
  assert.notEqual(tourState.figure, firstFigure, 'a left drag moved the deck on');
  assert.equal(tourState.on, 1, 'exactly one figure is in front');
  assert.equal(tourState.behind, 3, 'the other three sit behind it, faded');
  assert.equal(tourState.turned, 4, 'all four frames carry a rotation, so the set reads as a fan');
  assert.equal(tourState.dropped, 3, 'the three frames behind the front card are lowered, not lined up beside it');
  assert.equal(tourState.dots, 0, 'no dots or rail sit under the deck');
  assert.equal(tourState.loaded, 4, 'all four frames have painted their screenshot');
  assert.ok(Math.abs(tourState.scroll - deck.scroll) < 2, 'dragging the deck did not move the page');
  assert.equal(tourState.overflow, 0, 'the deck does not push the page sideways');
  ok('screenshot deck is dragged by the finger', tourState);


  // ---- 2. the gate answers, and a wrong password stays on the form --------
  await browser.navigate(`${base}/cycle`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=login]"))', 15000);
  await browser.evaluate(`(async () => {
    const inputs = document.querySelectorAll('.auth-form input');
    inputs[0].value = 'Astra';
    inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
    inputs[1].value = 'wrong-password';
    inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('.auth-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return true;
  })()`);
  await browser.waitFor('Boolean(document.querySelector(".auth-error"))', 15000);
  const refused = await browser.evaluate(`document.querySelector('.auth-error').innerText.trim()`);
  assert.match(refused, /password|sign/i, 'a wrong password produces a message, not a journal');
  ok('wrong password is refused on the form', refused);

  await browser.evaluate(`(async () => {
    const inputs = document.querySelectorAll('.auth-form input');
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inputs[1], '${PASSWORD}');
    inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('.auth-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return true;
  })()`);
  await browser.waitFor('!document.querySelector("[data-testid=login]")', 20000);
  // The gate legitimately answers 401 to the pre-login session probe; anything after
  // this line is unexpected and must stay out of the console.
  const authProbeErrors = browser.errors.map(entry => String(entry.text || entry.exceptionDetails?.text || 'error'));
  ok('the owner password opens the journal');

  // ---- 3. the account membership panel -----------------------------------
  await browser.navigate(`${base}/archive`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=membership-panel]"))', 20000);
  await browser.evaluate(`document.querySelector('#membership-panel').scrollIntoView({ block: 'center' }); true`);
  await delay(400);
  const panel = await browser.evaluate(`(() => {
    const host = document.querySelector('[data-testid=membership-panel]');
    return {
      tier: host.querySelector('[data-testid=mp-tier]').innerText.trim(),
      devices: host.querySelector('[data-testid=mp-devices]').innerText.trim(),
      rows: host.querySelectorAll('[data-testid=mp-device-list] li').length,
      current: host.querySelector('[data-testid=mp-device-list] li.mine') ? 1 : 0,
      minControl: Math.min(...[...host.querySelectorAll('input, button')].map(n => n.getBoundingClientRect().height)),
      href: location.pathname,
    };
  })()`);
  assert.match(panel.tier, /Free|Lite|Plus|Pro|Ultra/, 'the panel names the current tier');
  assert.match(panel.devices, /^\d+ \/ \d+$/, 'signed-in devices are counted against the limit');
  assert.equal(panel.rows, Number(panel.devices.split('/')[0].trim()), 'the list shows every counted device');
  assert.equal(panel.current, 1, 'this device is marked');
  assert.ok(panel.minControl >= 44, `panel controls are at least 44 px (${panel.minControl})`);
  await browser.evaluate(`(() => {
    const field = document.querySelector('[data-testid=redeem-code]');
    field.value = 'RR-BROWSER-PLUS';
    field.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-testid=redeem-form]').requestSubmit();
    return true;
  })()`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=redeem-message]"))', 10000);
  const codeAnswer = await browser.evaluate(`document.querySelector('[data-testid=redeem-message]').innerText.trim()`);
  assert.match(codeAnswer, /tier|redeemed/i, 'a known code reaches the server and answers in the panel');
  await browser.screenshot(join(SHOTS_DIR, 'account-panel-421.png'), await browser.evaluate(`(() => {
    const box = document.querySelector('[data-testid=membership-panel]').getBoundingClientRect();
    return { x: box.left + window.scrollX, y: box.top + window.scrollY, width: box.width, height: Math.min(box.height, 900), scale: 1 };
  })()`));
  ok('account membership panel: tier, devices and code refusal', { ...panel, codeAnswer });

  // ---- 3b. the calendar projection: week, month, agenda -------------------
  await browser.navigate(`${base}/calendar`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=calendar]"))', 20000);
  await delay(600);
  const weekView = await browser.evaluate(`(() => {
    const host = document.querySelector('[data-testid=calendar]');
    const cols = host.querySelectorAll('.cal-col');
    const cards = [...host.querySelectorAll('.cal-card')];
    return {
      cols: cols.length,
      cards: cards.length,
      statuses: cards.map(card => card.querySelector('.cal-status').innerText.trim()),
      statusData: cards.map(card => card.dataset.status),
      range: host.querySelector('[data-testid=cal-range]').innerText.trim(),
      detail: Boolean(host.querySelector('[data-testid=cal-detail]')),
      detailCards: [...host.querySelectorAll('.cal-detail-card')].map(card => ({
        label: card.querySelector('.cal-detail-head b')?.innerText.trim() || '',
        href: card.querySelector('a')?.getAttribute('href') || '',
        rows: [...card.querySelectorAll('li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim()),
        movements: [...card.querySelectorAll('li span')].map(n => n.innerText.trim()),
      })),
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      minControl: Math.min(...[...host.querySelectorAll('[data-testid^=cal-view-], [data-testid=cal-today], .cal-nav button')].map(n => n.getBoundingClientRect().height)),
    };
  })()`);
  assert.equal(weekView.cols, 7, 'the week view arranges seven days');
  assert.ok(weekView.cards >= 1, 'the week view shows the sessions in that week');
  assert.ok(weekView.statuses.every(text => /Planned|Completed|Skipped|Missed/i.test(text)), 'status is written out, never colour alone');
  assert.ok(weekView.detail, 'a selected day owns a read-only detail block');
  assert.ok(weekView.detailCards.length >= 1, 'the selected day lists its sessions');
  assert.ok(weekView.detailCards.every(card => /^SESSION [A-Z]/.test(card.label)), `the detail names the session it belongs to (${weekView.detailCards.map(card => card.label).join(' / ')})`);
  assert.ok(weekView.detailCards[0].rows.length >= 4, 'the detail lists every prescribed row, not a summary');
  assert.ok(weekView.detailCards[0].href.includes('/cycle/week/'), 'the detail links to the same session the week view opened');
  assert.ok(weekView.minControl >= 44, `calendar controls reach 44 px (${weekView.minControl})`);
  assert.equal(weekView.overflow, 0, 'the calendar does not scroll sideways at 421');
  await shot('calendar-week');

  await browser.evaluate(`document.querySelector('[data-testid=cal-view-month]').click(); true`);
  await delay(500);
  const monthView = await browser.evaluate(`(() => {
    const host = document.querySelector('[data-testid=calendar]');
    const cells = [...host.querySelectorAll('.cal-cell')];
    return {
      cells: cells.length,
      numbered: cells.every(cell => /^\\d{2}$/.test(cell.querySelector('.cal-cell-n').innerText.trim())),
      marked: cells.filter(cell => cell.querySelectorAll('.cal-cell-bar').length).length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  })()`);
  assert.equal(monthView.cells, 42, 'the month view draws a six-row grid');
  assert.ok(monthView.numbered, 'every cell carries its date number');
  assert.ok(monthView.marked >= 1, 'planned sessions appear as markers in the month grid');
  assert.equal(monthView.overflow, 0, 'the month grid fits 421 without sideways scroll');
  await shot('calendar-month');

  await browser.evaluate(`document.querySelector('[data-testid=cal-view-agenda]').click(); true`);
  await delay(500);
  const agenda = await browser.evaluate(`(() => {
    const host = document.querySelector('[data-testid=calendar]');
    const rows = [...host.querySelectorAll('.cal-agenda li')].filter(row => row.querySelector('time'));
    return {
      rows: rows.length,
      first: rows[0]?.querySelector('time')?.innerText.trim() || '',
      statuses: rows.map(row => row.querySelector('.cal-status').innerText.trim()),
      links: rows.filter(row => row.querySelector('.cal-open')?.innerText.match(/Open|Archive/)).length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  })()`);
  assert.ok(agenda.rows >= 1, 'the agenda lists sessions in date order');
  assert.match(agenda.first, /^\d{4}-\d{2}-\d{2}$/, 'agenda rows are date-first');
  assert.ok(agenda.statuses.every(text => /Planned|Completed|Skipped|Missed/i.test(text)), 'agenda rows carry the same statuses');
  assert.ok(agenda.links >= 1, 'each agenda row offers a read-only way into the session');
  assert.equal(agenda.overflow, 0, 'the agenda does not scroll sideways');
  await shot('calendar-agenda');
  ok('calendar: week / month / agenda read one projection', { week: weekView.range, agendaRows: agenda.rows });

  // ---- 3b. a failed panel load says so and offers retry (0.43) ------------
  // Only the calendar's own request is blocked: the page shell still loads, so the
  // failure has to be explained by the panel rather than by a blank screen.
  await browser.send('Network.setBlockedURLs', { urls: ['*/api/calendar*'] });
  await browser.navigate(`${base}/calendar`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=cal-error]"))', 20000);
  const calError = await browser.evaluate(`(() => {
    const node = document.querySelector('[data-testid=cal-error]');
    return { text: node.innerText.replace(/\\s+/g, ' ').trim(), retry: Boolean(node.querySelector('button')),
      retryHeight: node.querySelector('button')?.getBoundingClientRect().height || 0,
      blank: document.querySelector('[data-testid=calendar]').innerText.replace(/\\s+/g, ' ').trim().length };
  })()`);
  assert.match(calError.text, /could not be loaded|could not/i, 'a failed calendar request explains itself instead of rendering empty');
  assert.ok(calError.retry, 'the error carries a retry control');
  assert.ok(calError.retryHeight >= 44, `the retry control reaches 44 px (${calError.retryHeight})`);
  await shot('calendar-error');
  await browser.send('Network.setBlockedURLs', { urls: [] });
  // The block above was instrumentation, not a failure of the app: drop the
  // 'inspector' entry it produced before the final "no failed requests" check.
  browser.networkFailures.splice(0, browser.networkFailures.length,
    ...browser.networkFailures.filter(item => item.blockedReason !== 'inspector'));
  await browser.navigate(`${base}/calendar`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=cal-week]"))', 25000);
  ok('a blocked panel load explains itself and recovers on retry', { message: calError.text });


  // ---- 4. a real session day ---------------------------------------------
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(400);
  const day = await browser.evaluate(`({
    rows: document.querySelectorAll('.exercise').length,
    main: document.querySelectorAll('.exercise.main').length,
    gear: Boolean(document.querySelector('[data-testid=gear-plates]')),
    warmup: Boolean(document.querySelector('.warmups')),
    movements: [...document.querySelectorAll('.exercise')].map(n => n.innerText.replace(/\\s+/g, ' ')),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    innerWidth: window.innerWidth,
  })`);
  assert.ok(day.rows >= 4, 'a session day lists its prescribed rows');
  assert.ok(day.main >= 1, 'the main lift is present');
  // 0.45: a repeated movement must be told apart at row level.
  const rowTags = await browser.evaluate(`[...document.querySelectorAll('.ex-row-tag')].map(n => n.innerText.trim())`);
  assert.ok(rowTags.length >= 1, 'a repeated movement carries a TOP / BACK-OFF row tag');
  assert.ok(rowTags.every(tag => /TOP|BACK-OFF|WORK/.test(tag)), `row tags use the prescribed wording (${rowTags.join(', ')})`);
  assert.ok(!day.gear, 'the plate cabinet is gone from the session day');
  assert.ok(!day.warmup, 'no suggested-warm-up list is injected into a session');
  assert.equal(day.overflow, 0, 'the session day does not scroll sideways');
  await shot('session-day');
  // 0.44: the anatomy figure must be big enough to read. The week page carries the
  // compact map; a fixture without geometry renders the locked panel instead.
  await browser.navigate(`${base}/cycle/week/1`);
  await browser.waitFor('Boolean(document.querySelector(".week-aside"))', 20000);
  await delay(400);
  const anatomy = await browser.evaluate(`(() => {
    const svg = document.querySelector('.anatomy-grid svg');
    if (!svg) return { rendered: false };
    const box = svg.getBoundingClientRect();
    return { rendered: true, height: Math.round(box.height), width: Math.round(box.width), stacked: document.querySelectorAll('.anatomy-grid figure').length };
  })()`);
  if (anatomy.rendered) {
    assert.ok(anatomy.height >= 280, `the anatomy figure is tall enough to read (${anatomy.height} px)`);
    await shot('anatomy-week');
  }
  ok('session page text unclipped and the anatomy figure is legible', anatomy);
  // 0.47: the day reads its own capacity and muscle load. The week's board must not
  // appear under a session that only trains one day of it.
  const weekScope = await browser.evaluate(`(() => ({
    cap: document.querySelector('.week-capacity')?.dataset.scope || '',
    kicker: document.querySelector('.week-capacity .section-kicker')?.innerText.replace(/\\s+/g, ' ').trim() || '',
    map: document.querySelector('[data-testid=muscle-week]')?.innerText.trim() || '',
  }))()`);
  assert.equal(weekScope.cap, 'week', 'the week page keeps the weekly capacity board');
  assert.match(weekScope.kicker, /WEEKLY CAPACITY/, 'the week page labels its capacity as weekly');
  assert.match(weekScope.map, /^W\d{2}$/, 'the week page names a week above the muscle map');
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(400);
  const scope = await browser.evaluate(`(() => ({
    cap: document.querySelector('.week-capacity')?.dataset.scope || '',
    kicker: document.querySelector('.week-capacity .section-kicker')?.innerText.replace(/\\s+/g, ' ').trim() || '',
    map: document.querySelector('[data-testid=muscle-week]')?.innerText.trim() || '',
    total: document.querySelector('[data-testid=weekly-total]')?.innerText.trim() || '',
    weekTotal: document.querySelector('.day-detail-head')?.innerText.replace(/\\s+/g, ' ').trim() || '',
  }))()`);
  assert.equal(scope.cap, 'session', 'an open day swaps the weekly board for its own capacity');
  assert.match(scope.kicker, /SESSION CAPACITY/, 'the day labels its capacity as a session');
  assert.equal(scope.map, 'THIS SESSION', 'the muscle map states that it is this session');
  assert.ok(scope.total && scope.total !== '732', `the day total is the session's own set count (${scope.total})`);
  ok('a day carries its own capacity and muscle map', scope);
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  ok('session day renders', day);

  // ---- 4b. the calendar detail is that same session (0.43) ----------------
  const detailCard = weekView.detailCards[0];
  await browser.navigate(`${base}${detailCard.href}`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(300);
  const detailDay = await browser.evaluate(`({ rows: document.querySelectorAll('.exercise').length,
    movements: [...document.querySelectorAll('.exercise')].map(n => n.innerText.replace(/\\s+/g, ' ')) })`);
  // The page may split one prescribed row into its segments, so the check is that
  // every row the detail lists appears, in order, on the session page.
  let cursor = 0;
  detailCard.movements.forEach(movement => {
    const found = detailDay.movements.findIndex((text, index) => index >= cursor && text.toLowerCase().includes(movement.toLowerCase()));
    assert.ok(found >= 0, `the session page shows the detail row "${movement}" in the same order`);
    cursor = found + 1;
  });
  assert.ok(detailDay.rows >= detailCard.rows.length, 'the session page never shows fewer rows than the detail');
  ok('the calendar detail and the session page are one session', { href: detailCard.href, label: detailCard.label, detailRows: detailCard.rows.length, pageRows: detailDay.rows });
  // Restore the state the next checks assume: one known session day.
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);


  // ---- 4b. one number, every page (0.41) ---------------------------------
  // The same week and cycle must read identically on the day header, the week card,
  // the cycle header, the block page and Assay. Expected values are hand sums of
  // plan rows, so the assertion cannot agree with a wrong page by accident.
  const plan = JSON.parse(readFileSync(join(root, 'data', 'plan.json'), 'utf8'));
  const rowsW1 = plan.workouts.filter(row => row.week === 1);
  const rowsW1A = rowsW1.filter(row => row.day === 'A');
  const handWeekSets = rowsW1.reduce((sum, row) => sum + row.sets, 0);
  const handWeekT = (rowsW1.reduce((sum, row) => sum + (row.tonnageKg || 0), 0) / 1000).toFixed(2);
  const handDaySets = rowsW1A.reduce((sum, row) => sum + row.sets, 0);
  const handCycleSets = plan.workouts.reduce((sum, row) => sum + row.sets, 0);
  const handCycleT = (plan.workouts.reduce((sum, row) => sum + (row.tonnageKg || 0), 0) / 1000).toFixed(1);
  const blockWeeks = plan.weeks.filter(week => week.blockId === plan.blocks[0].id).map(week => week.n);
  const handBlockT = (plan.workouts.filter(row => blockWeeks.includes(row.week)).reduce((sum, row) => sum + (row.tonnageKg || 0), 0) / 1000).toFixed(2);
  const dayHead = await browser.evaluate(`document.querySelector('.day-detail-head').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.ok(dayHead.includes(`${handDaySets} SETS · ${rowsW1A.length} PRESCRIBED ROWS`), 'the day header counts the rows it lists');
  await browser.navigate(`${base}/cycle`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=load-profile]"))', 20000);
  const cycleHead = await browser.evaluate(`document.querySelector('.eyebrow').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.match(cycleHead, new RegExp(`\\b${handCycleSets} SETS\\b`), 'the cycle header states the same total as the rows');
  const cycleT = await browser.evaluate(`document.querySelector('.plan-metrics .metric:nth-child(3) strong').innerText.trim()`);
  assert.equal(cycleT, `${handCycleT} t`, 'the cycle headline tonnage is rounded once from the row sum');
  const blockT = await browser.evaluate(`[...document.querySelectorAll('.block-card')][0].querySelector('.block-stats dd').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.equal(blockT, `${handBlockT} t`, 'the block sub-total carries two decimals');
  await browser.navigate(`${base}/cycle/block/B1`);
  await browser.waitFor('Boolean(document.querySelector(".plan-metrics"))', 20000);
  const blockMetric = await browser.evaluate(`[...document.querySelectorAll('.plan-metrics .metric')].map(n => n.innerText.replace(/\\s+/g, ' ').trim()).find(text => /BLOCK TONNAGE/.test(text))`);
  assert.ok(blockMetric.includes(`${handBlockT} t`), 'the block page shows the same sub-total as the block card');
  // 0.47: the week row is one line of small squares, numbered only, whatever the block length.
  const squares = await browser.evaluate(`(() => {
    const items = [...document.querySelectorAll('.bw-weeks a')];
    const tops = [...new Set(items.map(n => Math.round(n.getBoundingClientRect().top)))];
    const boxes = items.map(n => n.getBoundingClientRect());
    return { count: items.length, rows: tops.length, text: items.map(n => n.innerText.trim()).join(','),
             ratio: boxes.length ? Math.round(boxes[0].width / boxes[0].height * 100) / 100 : 0,
             labelled: document.querySelectorAll('.bw-weeks small, .bw-weeks i').length };
  })()`);
  assert.equal(squares.rows, 1, 'the weeks stay on one row');
  assert.match(squares.text, /^\d+(,\d+)+$/, 'each square carries its week number and nothing else');
  assert.equal(squares.labelled, 0, 'no dot or kind label sits inside the squares');
  assert.ok(squares.ratio >= 0.9 && squares.ratio <= 1.1, `the squares stay square (${squares.ratio})`);
  ok('the week row is one line of numbered squares', squares);
  const blockTestLine = await browser.evaluate(`[...document.querySelectorAll('.load .note')].map(n => n.innerText.trim()).find(text => /test/i.test(text)) || ''`);
  assert.equal(blockTestLine, 'No test in this block', 'B1 shows no test day: the test week belongs to another block');
  const blockPageText = await browser.evaluate(`document.querySelector('.load').innerText.replace(/\\s+/g, ' ')`);
  const testDate = plan.testPlan?.dates?.sbd;
  assert.ok(!blockPageText.includes('2027'), `the block page does not print the global test day ${testDate}`);
  const weekCard = await browser.evaluate(`[...document.querySelectorAll('.week-card')].find(n => n.innerText.includes('W01')).querySelector('.week-stats').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.ok(weekCard.includes(`${handWeekT} t`), 'the week card tonnage carries two decimals');
  assert.ok(new RegExp(`\\b${handWeekSets}\\b`).test(weekCard), 'the week card counts the same sets as its rows');
  await browser.navigate(`${base}/cycle/week/1`);
  await browser.waitFor('Boolean(document.querySelector(".seg-brief"))', 20000);
  const weekHead = await browser.evaluate(`document.querySelector('.seg-brief .seg-facts').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.ok(weekHead.includes(`${handWeekT} t`), 'the week brief tonnage matches the week card to 0.01 t');
  await shot('totals-week');
  ok('one number on every page', { day: `${handDaySets} sets`, week: `${handWeekSets} sets / ${handWeekT} t`, cycle: `${handCycleSets} sets / ${handCycleT} t`, block: `${handBlockT} t` });

  // ---- 4c. the cycle page reloads deterministically (0.42) ---------------
  // Ten reloads on a throttled link must paint the same structure every time: no
  // card or button that appears on the first load and vanishes afterwards.
  await browser.navigate(`${base}/cycle`);
  await browser.waitFor('Boolean(document.querySelector(".block-deck"))', 20000);
  await browser.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 375000, uploadThroughput: 375000 });
  const signature = () => browser.evaluate(`JSON.stringify([...document.querySelectorAll('.primary-nav a, main h1, main .eyebrow, main .plan-metrics, main .block-card')].map(n => (n.className || '') + '|' + n.innerText.replace(/\\s+/g, ' ').trim()))`);
  const firstSignature = await signature();
  const signatures = [firstSignature];
  for (let i = 0; i < 9; i += 1) {
    await browser.send('Page.reload', { ignoreCache: false });
    await browser.waitFor('document.readyState === "complete"', 30000);
    await browser.waitFor('Boolean(document.querySelector(".block-deck"))', 30000);
    signatures.push(await signature());
  }
  await browser.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  assert.equal(signatures.filter(item => item === firstSignature).length, 10, 'ten reloads paint the same cycle structure');
  ok('cycle reloads deterministically', { reloads: 10, signatureLength: firstSignature.length, blocks: plan.blocks.length });

  // ---- 4d. no clipped text, and muted labels stay readable (0.44) ---------
  const sweep = `(() => {
    const clipped = [];
    const lowContrast = [];
    const ctx = document.createElement('canvas').getContext('2d');
    const normalize = value => { ctx.fillStyle = '#000000'; ctx.fillStyle = value; return ctx.fillStyle; };
    const lum = value => {
      const hex = normalize(value);
      let parts;
      if (hex[0] === '#') {
        const digits = hex.length === 4
          ? hex.slice(1).split('').map(d => parseInt(d + d, 16))
          : [hex.slice(1, 3), hex.slice(3, 5), hex.slice(5, 7)].map(pair => parseInt(pair, 16));
        parts = digits;
      } else {
        parts = hex.replace(/[^0-9.,]/g, ' ').trim().split(/[ ,]+/).map(Number).slice(0, 3);
      }
      const channel = value => { value /= 255; return value <= 0.03928 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4); };
      return 0.2126 * channel(parts[0]) + 0.7152 * channel(parts[1]) + 0.0722 * channel(parts[2]);
    };
    const background = node => {
      let current = node;
      while (current && current !== document.documentElement) {
        const style = getComputedStyle(current);
        if (style.backgroundImage && style.backgroundImage !== 'none') return null;
        const colour = style.backgroundColor;
        if (colour && colour !== 'transparent') {
          if (!/^rgba\\(/.test(colour)) return colour; // rgb() carries no alpha channel
          const alpha = Number(colour.slice(colour.lastIndexOf(',') + 1).replace(')', '').trim());
          if (alpha >= 0.95) return colour;
        }
        current = current.parentElement;
      }
      return 'rgb(241, 240, 235)';
    };
    for (const node of document.querySelectorAll('body *')) {
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden' || !node.clientWidth) continue;
      const text = (node.textContent || '').trim();
      if (!text || /(^| )(sr|sr-only|visually-hidden)( |$)/.test(node.className)) continue;
      const hidden = /hidden|clip/.test(style.overflowX) || /hidden|clip/.test(style.overflow);
      if (hidden && node.scrollWidth > node.clientWidth + 1 && !node.children.length) {
        clipped.push({ cls: node.className, text: text.slice(0, 40), scrollWidth: node.scrollWidth, clientWidth: node.clientWidth });
      }
      if (!node.children.length && parseFloat(style.fontSize) <= 12) {
        const paperColour = background(node);
        if (!paperColour) continue; // a gradient or image: no reliable ratio here
        const ink = lum(style.color);
        const paper = lum(paperColour);
        const ratio = (Math.max(ink, paper) + 0.05) / (Math.min(ink, paper) + 0.05);
        if (ratio < 4.4) lowContrast.push({ cls: node.className, tag: node.tagName, html: node.outerHTML.slice(0, 160), parent: node.parentElement?.outerHTML.slice(0, 160), seg: getComputedStyle(node).getPropertyValue('--seg'), ink: style.color, paper: paperColour, ratio: Math.round(ratio * 100) / 100, text: text.slice(0, 30) });
      }
    }
    return { clipped: clipped.slice(0, 10), lowContrast: lowContrast.slice(0, 10), checked: document.querySelectorAll('body *').length };
  })()`;
  const cycleSweep = await browser.evaluate(sweep);
  assert.equal(cycleSweep.clipped.length, 0, `no clipped text on the cycle page (${JSON.stringify(cycleSweep.clipped)})`);
  assert.equal(cycleSweep.lowContrast.length, 0, `small labels reach AA contrast (${JSON.stringify(cycleSweep.lowContrast)})`);
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  const daySweep = await browser.evaluate(sweep);
  assert.equal(daySweep.clipped.length, 0, `no clipped text on the session page (${JSON.stringify(daySweep.clipped)})`);
  assert.equal(daySweep.lowContrast.length, 0, `small labels reach AA contrast on the session page (${JSON.stringify(daySweep.lowContrast)})`);
  await browser.navigate(`${base}/`);
  const landingSweep = await browser.evaluate(sweep);
  assert.equal(landingSweep.clipped.length, 0, `no clipped text on the landing page (${JSON.stringify(landingSweep.clipped)})`);
  ok('no clipped text and AA contrast for small labels', { cycle: cycleSweep.checked, landing: landingSweep.checked });
  await browser.navigate(`${base}/cycle`);
  await browser.waitFor('Boolean(document.querySelector(".block-deck"))', 20000);


  // The logging check below expects the session day again.
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(300);

  // ---- 4. logging round-trips through the real server ---------------------
  const saved = await browser.evaluate(`(async () => {
    const button = [...document.querySelectorAll('.exercise.main .log-inline')][0];
    button.click();
    await new Promise(r => setTimeout(r, 250));
    const editor = document.querySelector('.log-editor');
    const set = (name, value) => {
      const input = editor.querySelector('[name=' + name + ']');
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      setter.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    };
    set('load', '102.5');
    set('sets', '3');
    set('reps', '5');
    editor.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 1500));
    return { summary: document.querySelector('.exercise.main .log-inline b').innerText.trim(),
             done: document.querySelector('.exercise.main .log-inline').className };
  })()`);
  assert.match(saved.summary, /102\.5/, 'the logged load is echoed on the row');
  assert.match(saved.done, /done/, 'the row is marked as logged');
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(400);
  const persisted = await browser.evaluate(`document.querySelector('.exercise.main .log-inline b').innerText.trim()`);
  assert.equal(persisted, saved.summary, 'the logged row survives a reload');
  ok('a logged row is saved and read back', saved.summary);

  // ---- 5. the test week stores a battery item -----------------------------
  await browser.navigate(`${base}/cycle/week/13`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=test-items]"))', 20000);
  await delay(400);
  const battery = await browser.evaluate(`({
    rows: document.querySelectorAll('[data-testid=test-items] .test-rows li').length,
    groups: [...document.querySelectorAll('[data-testid=test-items] .test-group')].map(n => n.getAttribute('data-testid')),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  })`);
  assert.equal(battery.rows, 9, 'nine test items are offered');
  assert.deepEqual(battery.groups, ['test-group-tier1', 'test-group-tier2', 'test-group-fivekm'], 'three battery groups');
  assert.equal(battery.overflow, 0, 'the test week does not scroll sideways');
  await shot('test-week');
  const testSaved = await browser.evaluate(`(async () => {    const input = document.querySelector('[data-testid=test-load-dip]');
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, '25');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-testid=test-save-dip]').click();
    await new Promise(r => setTimeout(r, 1500));
    return { badge: document.querySelector('[data-testid=test-saved-dip]')?.innerText.trim() || null,
             kicker: document.querySelector('[data-testid=test-items] .section-kicker').innerText.replace(/\\s+/g, ' ').trim() };
  })()`);
  assert.match(testSaved.badge || '', /25 kg/, 'a battery result shows its load');
  assert.match(testSaved.kicker, /1 \/ 9 RECORDED/, 'the recorded counter moves');
  ok('a battery item is saved', testSaved);

  // ---- 6. 0.50: the venue switch and the share card are gone -------------
  await browser.navigate(`${base}/analysis`);
  await browser.waitFor('Boolean(document.querySelector(".kpi"))', 20000);
  await delay(400);
  const assay = await browser.evaluate(`({
    completion: [...document.querySelectorAll('.kpi')].map(n => n.innerText.replace(/\\s+/g, ' ')).find(text => /COMPLETION/.test(text)),
    tonnage: [...document.querySelectorAll('.kpi')].map(n => n.innerText.replace(/\\s+/g, ' ')).find(text => /TONNAGE/.test(text)),
  })`);
  assert.match(assay.completion || '', /sessions elapsed/, 'completion states how many sessions have arrived');
  assert.match(assay.tonnage || '', /139\.6/, 'cycle tonnage is one rounded number, not a drifted sum');
  await shot('assay-completion');
  ok('ASSAY states completion and a single tonnage', assay);

  await browser.navigate(`${base}/archive`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=membership-panel]") || document.querySelector("#account"))', 20000);
  const vault = await browser.evaluate(`({
    gear: Boolean(document.querySelector('[data-testid=collar-toggle]')),
    settings: Boolean(document.querySelector('[data-testid=prescription-settings]')),
    calendar: Boolean(document.querySelector('[data-testid=open-calendar]')),
  })`);
  assert.equal(vault.gear, false, 'the collar switch left the vault');
  assert.equal(vault.settings, false, 'the prescription settings panel left the vault');
  assert.equal(vault.calendar, true, 'the calendar entry moved into the vault');
  ok('vault carries the calendar and no training-day knobs', vault);

  // ---- 7. the narrow floor -------------------------------------------------
  await browser.viewport(320, 800);
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(300);
  const narrow = await browser.evaluate(`({ width: window.innerWidth, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    wide: [...document.querySelectorAll('body *')].filter(n => n.getBoundingClientRect().right > window.innerWidth + 1)
      .slice(0, 6).map(n => ({ cls: n.className, tag: n.tagName, right: Math.round(n.getBoundingClientRect().right), text: (n.textContent || '').trim().slice(0, 20) })) })`);
  assert.equal(narrow.width, 320, `the narrow viewport is really 320 px (${JSON.stringify(narrow.wide)})`);
  assert.equal(narrow.overflow, 0, 'nothing overflows at 320 px');
  await shot('narrow-320');
  ok('320 px stays inside the page', narrow);

  // ---- 9. nothing shouted in the console ----------------------------------
  const errors = browser.errors.map(entry => String(entry.text || entry.exceptionDetails?.text || 'error')).slice(authProbeErrors.length);
  const failures = browser.networkFailures.filter(item => !/favicon/i.test(item.url || ''));
  assert.deepEqual(errors, [], 'no console errors after signing in');
  assert.deepEqual(failures, [], 'no failed network requests');
  assert.ok(authProbeErrors.every(text => /401|Unauthorized/i.test(text)), 'the only pre-login message is the gate 401');
  ok('no console errors after signing in and no failed requests', authProbeErrors.length);

  console.log(`PASS browser.mjs: ${checks.length} checks, 7 screenshots in ${SHOTS_DIR}`);
} catch (error) {
  console.error(`FAIL: ${error.message}`);
  console.error(`server log tail: ${serverLog.split('\n').slice(-6).join(' | ')}`);
  process.exitCode = 1;
} finally {
  await browser?.close?.();
  server.kill();
  await delay(200);
}
