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

  // ---- 1b. the membership matrix at a desk width -------------------------
  await browser.viewport(1280, 900);
  await browser.navigate(`${base}/`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=membership]"))', 20000);
  await browser.evaluate(`document.querySelector('#membership').scrollIntoView({ block: 'start' }); true`);
  await delay(600);
  const matrix = await browser.evaluate(`(() => {
    const section = document.querySelector('[data-testid=membership]');
    const heads = [...section.querySelectorAll('thead th[data-tier]')].map(n => ({ tier: n.dataset.tier, text: n.innerText.replace(/\\s+/g, ' ').trim() }));
    const table = section.querySelector('[data-testid=mm-table]');
    return {
      heads,
      prices: [...table.querySelectorAll('[data-testid=mm-price]')].map(n => n.innerText.trim()),
      rows: 6 + (section.querySelector('.mm-extra-wrap').getBoundingClientRect().height > 1 ? 7 : 0),
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  })()`);
  assert.deepEqual(matrix.heads.map(head => head.tier), ['free', 'lite', 'plus', 'pro'], 'four tier columns, Ultra excluded');
  assert.deepEqual(matrix.prices, ['¥0', '¥68', '¥198', '¥98/mo'], 'CNY prices come from the export, pro carries /mo');
  assert.equal(matrix.rows, 6, 'six rows are shown before the fold');
  assert.equal(matrix.overflow, 0, 'the matrix does not scroll sideways at 1280');
  await browser.evaluate(`document.querySelector('[data-testid=mm-usd]').click(); true`);
  await delay(300);
  const usd = await browser.evaluate(`[...document.querySelectorAll('[data-testid=mm-price]')].map(n => n.innerText.trim())`);
  assert.deepEqual(usd, ['US$0', 'US$19.9', 'US$69.9', 'US$19.9/mo'], 'switching currency flips every price');
  await browser.evaluate(`document.querySelector('[data-testid=mm-more]').click(); true`);
  await delay(400);
  const expandedRows = await browser.evaluate(`6 + (document.querySelector('.mm-extra-wrap').getBoundingClientRect().height > 1 ? 7 : 0)`);
  assert.equal(expandedRows, 13, 'showing every row reveals the whole capability list');
  ok('membership matrix: four tiers, two currencies, expandable rows', { prices: matrix.prices, rowCount: expandedRows });

  // ---- 1c. the same table on a phone ---------------------------------------
  await browser.viewport(390, 844);
  await browser.navigate(`${base}/`);
  await delay(500);
  const phoneMatrix = await browser.evaluate(`(() => {
    const section = document.querySelector('[data-testid=membership]');
    const rail = section.querySelector('[data-testid=mm-rail]');
    return { cards: rail.querySelectorAll('.mm-card').length, list: section.querySelectorAll('[data-testid=mm-list] li').length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  })()`);
  assert.equal(phoneMatrix.cards, 4, 'four tier cards on a phone');
  assert.equal(phoneMatrix.overflow, 0, 'the card rail does not push the page sideways');
  ok('membership cards on a phone', phoneMatrix);
  await browser.viewport(WIDTH, 900);

  // ---- 1d. the screenshot tour follows the scroll --------------------------
  await browser.navigate(`${base}/`);
  await delay(500);
  const firstFigure = await browser.evaluate(`document.querySelector('.wl-cap-name').innerText`);
  await browser.evaluate(`(() => {
    const el = document.querySelector('[data-testid=wl-tour]');
    const top = el.getBoundingClientRect().top + window.scrollY;
    const span = el.offsetHeight - window.innerHeight * 0.9;
    window.scrollTo({ top: top + span * 0.6, behavior: 'auto' });
    return true;
  })()`);
  await delay(400);
  const tourState = await browser.evaluate(`(() => ({
    figure: document.querySelector('.wl-cap-name').innerText,
    on: document.querySelectorAll('.wl-tshot.is-on').length,
    prev: document.querySelectorAll('.wl-tshot.is-prev').length,
    rail: document.querySelector('.wl-tour-rail i').style.width,
    dot: [...document.querySelectorAll('.wl-tour-dots button')].map(b => b.getBoundingClientRect().height).sort((a, b) => a - b)[0],
  }))()`);
  assert.notEqual(tourState.figure, firstFigure, 'scrolling moved the figure');
  assert.equal(tourState.on, 1, 'exactly one figure is in front');
  assert.equal(tourState.prev, 2, 'passed figures stay behind the current one');
  assert.ok(parseFloat(tourState.rail) > 50 && parseFloat(tourState.rail) < 70, `progress line follows the scroll (${tourState.rail})`);
  assert.ok(tourState.dot >= 44, 'dots are at least 44 px');
  ok('screenshot tour is scroll driven', tourState);


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
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      minControl: Math.min(...[...host.querySelectorAll('[data-testid^=cal-view-], [data-testid=cal-today], .cal-nav button')].map(n => n.getBoundingClientRect().height)),
    };
  })()`);
  assert.equal(weekView.cols, 7, 'the week view arranges seven days');
  assert.ok(weekView.cards >= 1, 'the week view shows the sessions in that week');
  assert.ok(weekView.statuses.every(text => /Planned|Completed|Skipped|Missed/i.test(text)), 'status is written out, never colour alone');
  assert.ok(weekView.detail, 'a selected day owns a read-only detail block');
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

  // ---- 4. a real session day ---------------------------------------------
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(400);
  const day = await browser.evaluate(`({
    rows: document.querySelectorAll('.exercise').length,
    main: document.querySelectorAll('.exercise.main').length,
    gear: Boolean(document.querySelector('[data-testid=gear-plates]')),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    innerWidth: window.innerWidth,
  })`);
  assert.ok(day.rows >= 4, 'a session day lists its prescribed rows');
  assert.ok(day.main >= 1, 'the main lift is present');
  assert.ok(day.gear, 'the plate cabinet is on the session day');
  assert.equal(day.overflow, 0, 'the session day does not scroll sideways');
  await shot('session-day');
  ok('session day renders', day);

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
  const weekCard = await browser.evaluate(`[...document.querySelectorAll('.week-card')].find(n => n.innerText.includes('W01')).querySelector('.week-stats').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.ok(weekCard.includes(`${handWeekT} t`), 'the week card tonnage carries two decimals');
  assert.ok(new RegExp(`\\b${handWeekSets}\\b`).test(weekCard), 'the week card counts the same sets as its rows');
  await browser.navigate(`${base}/cycle/week/1`);
  await browser.waitFor('Boolean(document.querySelector(".week-summary"))', 20000);
  const weekHead = await browser.evaluate(`document.querySelector('.week-summary').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.ok(weekHead.includes(`${handWeekT} t`), 'the week header tonnage matches the week card to 0.01 t');
  await shot('totals-week');
  ok('one number on every page', { day: `${handDaySets} sets`, week: `${handWeekSets} sets / ${handWeekT} t`, cycle: `${handCycleSets} sets / ${handCycleT} t`, block: `${handBlockT} t` });

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

  // ---- 6. the collar switch: default off, remembered per device -----------
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
  await browser.waitFor('Boolean(document.querySelector("[data-testid=collar-toggle]"))', 20000);
  const collar = await browser.evaluate(`(async () => {
    const box = document.querySelector('[data-testid=collar-toggle]');
    box.closest('details').open = true;
    const before = { checked: box.checked, stored: localStorage.getItem('rr.gear.collars') };
    box.click();
    await new Promise(r => setTimeout(r, 300));
    return { before, after: { checked: box.checked, stored: localStorage.getItem('rr.gear.collars') } };
  })()`);
  assert.equal(collar.before.checked, false, 'collars start switched off');
  assert.equal(collar.before.stored, null, 'nothing is stored until the owner chooses');
  assert.equal(collar.after.stored, '1', 'switching on stores the choice on this device');
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=collar-chip]"))', 20000);
  const chip = await browser.evaluate(`document.querySelector('[data-testid=collar-chip]').innerText.replace(/\\s+/g, ' ').trim()`);
  assert.match(chip, /\+5 KG/, 'the gear summary shows the collar pair once enabled');
  await shot('gear-collars');
  ok('collars default off and follow the switch', collar.after);

  // ---- 7. the share card draws --------------------------------------------
  const share = await browser.evaluate(`(async () => {
    const button = [...document.querySelectorAll('button')].find(n => /share/i.test(n.textContent));
    if (!button) return { opened: false };
    button.click();
    await new Promise(r => setTimeout(r, 1200));
    const card = document.querySelector('[data-testid=share-card]');
    if (!card) return { opened: false };
    const canvas = card.querySelector('canvas');
    const ctx = canvas.getContext('2d');
    const pixels = ctx.getImageData(0, canvas.height - 120, canvas.width, 100).data;
    let ink = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) ink += 1;
    return { opened: true, width: canvas.width, height: canvas.height, ink };
  })()`);
  assert.ok(share.opened, 'the share card opens from a day page');
  assert.equal(share.width, 1080, 'the card keeps its 1080 px canvas');
  assert.ok(share.ink > 0, 'the card actually paints');
  await shot('share-card');
  ok('the share card opens and paints', share);

  // ---- 8. the narrow floor -------------------------------------------------
  await browser.viewport(320, 800);
  await browser.navigate(`${base}/cycle/week/1/day/A`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=daily-record]"))', 20000);
  await delay(300);
  const narrow = await browser.evaluate(`({ width: window.innerWidth, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth })`);
  assert.equal(narrow.width, 320, 'the narrow viewport is really 320 px');
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
