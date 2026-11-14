import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { openBrowser } from './cdp.mjs';
import { readFile } from 'node:fs/promises';
const packageInfo = JSON.parse(await readFile(new URL('../web/package.json', import.meta.url), 'utf8'));
const [major, , patch] = packageInfo.version.split('.');
const releaseVersion = `${major}.${patch.padStart(2, '0')}`;

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.RR_PYTHON || join(root, 'server/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const browser = await openBrowser();
let checks = 0;
let screenshots = 0;
function equal(actual, expected, label) { assert.deepEqual(actual, expected, label); checks++; }
async function startServer(options = []) {
  const listener = createServer();
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const child = spawn(python, ['tests/serve_fixture.py', '--port', String(port), ...options], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  let output = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  child.on('error', error => { output += error.message; });
  const base = `http://127.0.0.1:${port}`;
  const stop = async () => {
    if (child.exitCode === null) { child.kill(); await Promise.race([new Promise(resolve => child.once('exit', resolve)), delay(5000)]); }
  };
  for (let n = 0; n < 100; n++) {
    try { if ((await fetch(`${base}/api/health`)).ok) return { base, stop }; } catch {}
    if (child.exitCode !== null) break;
    await delay(100);
  }
  await stop();
  throw new Error(`Fixture server did not start: ${output}`);
}
async function load(base, path = '/plan') {
  await browser.navigate(`${base}${path}`);
  await browser.waitFor('document.querySelector("main")?.getAttribute("aria-busy") === "false"');
  assert.equal(await browser.evaluate('Boolean(document.querySelector(".error-panel"))'), false, `Unexpected API error at ${path}`);
}
async function click(selector) {
  assert.ok(await browser.evaluate(`Boolean(document.querySelector(${JSON.stringify(selector)}))`), `Missing click target ${selector}`);
  await browser.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  await browser.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
}
async function input(selector, value) {
  await browser.evaluate(`(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) throw new Error(${JSON.stringify(`Missing input target ${selector}`)});
    if (element.matches(':disabled')) throw new Error(${JSON.stringify(`Disabled input target ${selector}`)});
    if (element.type === 'checkbox') element.checked = ${JSON.stringify(value)};
    else element.value = ${JSON.stringify(String(value))};
    element.dispatchEvent(new Event(element.tagName === 'SELECT' || element.type === 'checkbox' ? 'change' : 'input', { bubbles: true }));
  })()`);
  await browser.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
}
async function noOverflow(label) {
  const dimensions = await browser.evaluate('({ width: innerWidth, scroll: document.documentElement.scrollWidth, bad: [...document.querySelectorAll("main *")].filter(e => { const r=e.getBoundingClientRect(); return r.width>0 && (r.right>innerWidth+1 || r.left < -1) && !e.closest(".week-rail"); }).map(e => e.className?.baseVal ?? e.className).slice(0,8) })');
  equal(dimensions.scroll, dimensions.width, `${label}: page overflow ${JSON.stringify(dimensions)}`);
  equal(dimensions.bad, [], `${label}: child overflow`);
}
async function screenshot(name, selector) {
  let clip;
  if (selector) clip = await browser.evaluate(`(() => { const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}; })()`);
  await browser.screenshot(join(root, 'docs/shots', `${name}.png`), clip);
  screenshots++;
}
let server;
try {
  server = await startServer();
  const { base } = server;
  const plan = await (await fetch(`${base}/api/plan`)).json();
  const analysis = await (await fetch(`${base}/api/analysis`)).json();
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(base, '/');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(base, '/');
      equal(await browser.evaluate('document.documentElement.dataset.theme'), theme, 'theme persists');
      equal(await browser.evaluate('document.querySelector(".gear").open'), false, 'gear starts collapsed');
      equal(await browser.evaluate('document.querySelectorAll(".muscle-map.compact svg").length'), 2, 'Today anatomy visible without tabs');
      equal(await browser.evaluate('document.querySelectorAll(".leaf-list button").length'), 0, 'Today does not duplicate full muscle list');
      equal(await browser.evaluate('document.querySelector(".site-footer").textContent.includes(' + JSON.stringify(releaseVersion) + ')'), true, 'footer version matches package');
      equal(await browser.evaluate('document.querySelector(".edition").textContent'), `TRAINING JOURNAL / ${releaseVersion}`, 'masthead version matches package');
      const separator = await browser.evaluate('getComputedStyle(document.querySelector(".anatomy-grid path[data-leaf]")).stroke');
      equal(separator, theme === 'light' ? 'rgb(255, 255, 255)' : 'rgb(52, 62, 77)', 'anatomy separators follow theme');
      await noOverflow(`Today ${width} ${theme}`);
      await click('.gear summary');
      equal(await browser.evaluate('document.querySelector(".gear").open'), true, 'gear expands');
      await noOverflow(`Today expanded ${width} ${theme}`);
      await click('.gear summary');
      await screenshot(`today-${width}-${theme}`);
      await click('.primary-nav a[href="/plan"]');
      await browser.waitFor('Boolean(document.querySelector(".plan-metrics"))');
      equal(await browser.evaluate('document.querySelectorAll(".muscle-map.compact svg").length'), 2, 'Plan compact anatomy default visible');
      equal(await browser.evaluate('document.querySelectorAll(".leaf-list button, .capacity-board").length'), 0, 'Plan leaves full list and cycle board to Analysis');
      await noOverflow(`Plan ${width} ${theme}`);
      const targetSizes = await browser.evaluate('[...document.querySelectorAll("button, .primary-nav a, .week-rail a, .block-nav a, .day-row")].filter(e => { const r=e.getBoundingClientRect(); return r.height < 44 || r.width < 44; }).map(e=>e.textContent.trim())');
      equal(targetSizes, [], '44px touch controls');
      await screenshot(`plan-${width}-${theme}`);
      await browser.evaluate('document.querySelector(".muscle-selector select").value = "chest"; document.querySelector(".muscle-selector select").dispatchEvent(new Event("change", { bubbles: true }))');
      await browser.waitFor('Boolean(document.querySelector(".muscle-numbers"))');
      equal(await browser.evaluate('document.querySelector(".muscle-numbers b").textContent'), analysis.perWeek[0].leaves.chest.w.toFixed(1), 'compact muscle inspection uses API values');
      await click('.muscle-map .inline-link');
      await browser.waitFor('location.pathname === "/analysis"');
      equal(await browser.evaluate('location.search'), '?week=1', 'full analysis preserves selected week');
      equal(await browser.evaluate('document.querySelectorAll(".leaf-list button").length'), 16, 'Analysis owns full sixteen-muscle list');
      equal(await browser.evaluate('document.querySelectorAll(".capacity-board").length'), 1, 'Analysis owns cycle capacity board');
      equal(await browser.evaluate('(() => { const bottom=s=>document.querySelector(s).getBoundingClientRect().bottom; const top=s=>document.querySelector(s).getBoundingClientRect().top; return [bottom(".anatomy-grid") <= top("[data-testid=analysis-summary]"), bottom("[data-testid=analysis-summary]") <= top(".leaf-list"), bottom(".leaf-list") <= top(".analysis-workspace > aside"), bottom(".analysis-workspace") <= top("[data-testid=trend-view]")]; })()'), [true, true, true, true], 'mobile reading order: anatomy, summary, sixteen leaves, capacity, trends');
      equal(await browser.evaluate('document.querySelector("[data-testid=performance-movement]").value'), 'S.Main|high-bar squat', 'performance defaults to exact main squat ID');
      equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=capacity-trend] svg")) && Boolean(document.querySelector("[data-testid=performance-empty]"))'), true, 'capacity trend visible and absent performance explicit');
      equal(await browser.evaluate('document.querySelector(".anatomy-grid path[data-leaf=chest]").classList.contains(' + JSON.stringify(`heat-${analysis.perWeek[0].leaves.chest.heat.Both.band}`) + ')'), true, 'map uses API cycle-fixed heat band');
      equal(await browser.evaluate('(() => { const expected=document.createElement("i"); expected.style.width=' + JSON.stringify(`${analysis.perWeek[0].leaves.chest.heat.Both.percent}%`) + '; return document.querySelector("[data-testid=leaf-chest] .leaf-track i").style.width === expected.style.width; })()'), true, 'leaf bar uses API cycle-fixed proportion after browser CSS serialization');
      equal(await browser.evaluate('(() => { const previous=scrollY; scrollTo(innerWidth,previous); const right=scrollX; scrollTo(-innerWidth,previous); const left=scrollX; scrollTo(0,previous); return [right,left]; })()'), [0, 0], 'analysis cannot horizontally scroll');
      equal(await browser.evaluate('[...document.querySelectorAll("main button, main select, main summary")].filter(e => { const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 && (r.width<44 || r.height<44); }).map(e=>e.className)'), [], 'analysis controls meet 44px');
      await noOverflow(`Analysis ${width} ${theme}`);
      await screenshot(`analysis-${width}-${theme}`);
      await screenshot(`map-${width}-${theme}`, '.muscle-map');
      await click('[data-testid="leaf-chest"]');
      equal(await browser.evaluate('document.querySelector(".muscle-numbers b").textContent'), analysis.perWeek[0].leaves.chest.w.toFixed(1), 'leaf weighted details match API');
      await click('[aria-label="Next muscle week"]');
      equal(await browser.evaluate('document.querySelector("[data-testid=muscle-week]").textContent'), 'W02', 'map week advances');
      equal(await browser.evaluate('Number(document.querySelector("[data-testid=weekly-total]").textContent)'), analysis.perWeek[1].total, 'week totals synchronized');
      equal(await browser.evaluate('location.pathname + location.search'), '/analysis?week=2', 'analysis map changes week deep link');
      await click('.map-filters button:nth-child(3)');
      equal(await browser.evaluate('document.querySelector(".map-filters button:nth-child(3)").getAttribute("aria-pressed")'), 'true', 'secondary filter selected');
      equal(await browser.evaluate('document.querySelector(".anatomy-grid path[data-leaf=chest]").classList.contains(' + JSON.stringify(`heat-${analysis.perWeek[1].leaves.chest.heat.Secondary.band}`) + ')'), true, 'secondary contribution uses same cycle-fixed denominator');
      equal(await browser.evaluate('document.querySelector("[data-testid=heat-scale]").textContent.includes(' + JSON.stringify(analysis.heatScale.maximum.toFixed(1)) + ')'), true, 'legend maximum stays fixed when week and filter change');
      await noOverflow(`Map selected ${width} ${theme}`);
      await click('[data-testid="leaf-adductors"]');
      assert.match(await browser.evaluate('document.querySelector(".muscle-detail").textContent'), /No separate reference/, 'unknown MEV stays unknown'); checks++;
      await click('[data-testid="leaf-lats"]');
      assert.match(await browser.evaluate('document.querySelector(".muscle-detail").textContent'), /Back-group reference/, 'back range not individual leaf'); checks++;
      const dayPath = `/plan/week/2/day/${plan.workouts.find(row => row.week === 2).day}`;
      await load(base, dayPath);
      assert.ok(await browser.evaluate('document.querySelectorAll(".exercise").length > 0'), 'day expands after direct reload'); checks++;
      const focusedDay = `day-2-${plan.workouts.find(row => row.week === 2).day}`;
      await browser.waitFor(`document.activeElement.id === ${JSON.stringify(focusedDay)}`);
      const landing = await browser.evaluate(`(() => { const r=document.getElementById(${JSON.stringify(focusedDay)}).getBoundingClientRect(); return { id: document.activeElement.id, top: r.top, scroll: scrollY }; })()`);
      equal(landing.id, focusedDay, 'day deep link transfers keyboard focus');
      assert.ok(landing.top >= 0 && landing.top < 60 && landing.scroll > 0, 'deep-linked day lands within viewport'); checks++;
      await click('[aria-label="Next plan week"]');
      await browser.evaluate('history.back()');
      await browser.waitFor(`document.activeElement.id === ${JSON.stringify(focusedDay)}`);
      equal(await browser.evaluate('Math.round(document.activeElement.getBoundingClientRect().top)'), Math.round(landing.top), 'history back restores day landing');
      await noOverflow(`Day ${width} ${theme}`);
      const dayRow = plan.workouts.find(row => row.week === 2);
      const warmups = plan.warmups?.[dayRow.date] || [];
      equal(await browser.evaluate('document.querySelectorAll("[data-testid=warmups]").length'), warmups.length ? 1 : 0, 'warm-up block matches plan data');
      if (warmups.length) {
        equal(await browser.evaluate('document.querySelector("[data-testid=warmups]").open'), false, 'warm-up starts collapsed');
        await click('[data-testid=warmups] summary');
        equal(await browser.evaluate('document.querySelector("[data-testid=warmups]").open'), true, 'warm-up expands');
        const warmText = await browser.evaluate('document.querySelector("[data-testid=warmups]").textContent');
        assert.ok(warmText.includes('SUGGESTION ONLY') && warmText.includes(`${warmups[0].steps[0].kg} kg`), 'warm-up steps render plan values'); checks++;
        await noOverflow(`Day warm-up expanded ${width} ${theme}`);
        await screenshot(`day-warmup-${width}-${theme}`);
        await click('[data-testid=warmups] summary');
      }
      console.log(`PASS CDP ${width}px ${theme}: Today, Plan, map, day reload, 44px targets, no page overflow`);
    }
  }
  await browser.viewport(390);
  for (const block of plan.blocks) {
    await load(base, `/plan/block/${block.id}`);
    equal(await browser.evaluate('Number(document.querySelector(".week-number").textContent)'), plan.weeks.find(w => w.blockId === block.id).n, `block ${block.id}`);
  }
  for (const path of ['/plan/week/0', '/plan/week/999', '/plan/week/1.5', '/plan/week/1/day/NOPE', '/plan/block/NOPE', '/missing']) {
    await load(base, path);
    equal(await browser.evaluate('document.querySelector("h1").textContent'), 'Not in this plan.', `invalid ${path}`);
  }
  await load(base, '/plan/test');
  equal(await browser.evaluate('Number(document.querySelector(".week-number").textContent)'), plan.weeks.find(w => w.kind === 'test').n, 'test week derived');
  await noOverflow('test week');
  const deloadWeek = plan.weeks.find(w => w.kind === 'deload');
  await load(base, `/plan/week/${deloadWeek.n}`);
  equal(await browser.evaluate('document.querySelector(".week-header small").textContent'), 'DELOAD WEEK', 'deload week labelled');
  assert.match(await browser.evaluate('document.querySelector(".week-header + .notice")?.textContent || ""'), /lighter loads, same movements/, 'deload notice explains reduced load'); checks++;
  await noOverflow('deload week');
  await load(base, `/plan/week/${plan.weeks.find(w => w.kind === 'training').n}`);
  equal(await browser.evaluate('document.querySelector(".week-header + .notice")'), null, 'training week carries no deload notice');
  await load(base, '/plan/week/1');
  await click('[aria-label="Next plan week"]');
  await browser.evaluate('history.back()');
  await browser.waitFor('location.pathname === "/plan/week/1"');
  equal(await browser.evaluate('document.querySelector("[data-testid=muscle-week]").textContent'), 'W01', 'browser back restores week');
  for (const path of ['/analysis', '/archive', '/settings']) { await load(base, path); await noOverflow(path); }
  assert.ok(await browser.evaluate('document.querySelector("main").textContent.includes(' + JSON.stringify(`Single-user release ${releaseVersion}`) + ')'), 'Settings version matches package'); checks++;
  const row = plan.workouts[0];
  const saved = await fetch(`${base}/api/log`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cycle_id: plan.meta.planId, week: row.week, day: row.day, seq: row.seq, load: null, sets: 0, reps: 0, rpe: null, note: 'Browser regression fixture only' }) });
  equal(saved.status, 200, 'API accepts zero-set actual log');
  await load(base, '/analysis');
  await click('.map-filters button:nth-child(2)');
  await browser.waitFor('document.querySelector("main").getAttribute("aria-busy") === "false"');
  equal(await browser.evaluate('Number(document.querySelector("[data-testid=weekly-total]").textContent)'), analysis.perWeek[0].total - row.sets, 'logged mode replaces plan sets');
  await click('.primary-nav a[href="/plan"]');
  await browser.waitFor('document.querySelector("main").getAttribute("aria-busy") === "false"');
  equal(await browser.evaluate('Number(document.querySelector("[data-testid=weekly-total]").textContent)'), analysis.perWeek[0].total, 'Plan resets to planned mode');
  equal(browser.errors, [], 'no unexpected browser errors');
  await browser.send('Network.enable');
  const loggedDayPath = `/plan/week/${row.week}/day/${row.day}`;
  await load(base, loggedDayPath);
  await click('.primary-nav a[href="/analysis"]');
  await click('.map-filters button:nth-child(2)');
  await browser.waitFor('document.querySelector("main").getAttribute("aria-busy") === "false"');
  await browser.send('Network.setBlockedURLs', { urls: [`${base}/api/analysis*`] });
  await browser.evaluate('history.back()');
  await browser.waitFor(`location.pathname === ${JSON.stringify(loggedDayPath)} && Boolean(document.querySelector(".error-panel"))`);
  equal(await browser.evaluate('document.querySelectorAll(".plan-day, .muscle-map").length'), 0, 'failed Day refresh hides retained plan and statistics');
  equal(browser.errors.filter(entry => !entry.source), [], 'failed Day refresh never focuses a missing node');
  await browser.send('Network.setBlockedURLs', { urls: [] });
  await click('.error-panel button');
  await browser.waitFor(`document.activeElement?.id === "day-${row.week}-${row.day}"`);
  equal(await browser.evaluate('document.activeElement.getBoundingClientRect().top < 60'), true, 'Day retry restores focused viewport landing');
  equal(browser.errors.filter(entry => !entry.source), [], 'Day retry has no runtime exceptions');
  browser.errors.splice(0);
  await browser.send('Network.setBlockedURLs', { urls: [`${base}/api/analysis*`] });
  await browser.navigate(`${base}/plan`);
  await browser.waitFor('Boolean(document.querySelector(".error-panel"))');
  equal(await browser.evaluate('document.querySelectorAll(".muscle-map").length'), 0, 'failed API does not show stale statistics');
  await browser.send('Network.setBlockedURLs', { urls: [] });
  await click('.error-panel button');
  await browser.waitFor('Boolean(document.querySelector(".muscle-map"))');
  browser.errors.splice(0);
  console.log('PASS routes and failure states: all blocks, reload/back, invalid paths, plan/log modes, API failure and retry');
  await server.stop(); server = null;
  for (const count of [8, 17]) {
    server = await startServer(['--weeks', String(count)]);
    const dynamic = await (await fetch(`${server.base}/api/analysis`)).json();
    await load(server.base, `/plan/week/${count}`);
    equal(await browser.evaluate('document.querySelector("[data-testid=muscle-week]").textContent'), `W${String(count).padStart(2, '0')}`, `dynamic ${count} last week`);
    equal(await browser.evaluate('Number(document.querySelector("[data-testid=weekly-total]").textContent)'), dynamic.perWeek.at(-1).total, `dynamic ${count} API-linked statistics`);
    equal(await browser.evaluate(`document.querySelector('[aria-label="Next muscle week"]').disabled`), true, `dynamic ${count} end boundary`);
    await noOverflow(`${count}-week plan`);
    console.log(`PASS dynamic browser: ${count}-week validated plan served by real FastAPI / SQLite; last week and totals match API`);
    await server.stop(); server = null;
  }
  const trainingDate = plan.workouts[0].date;
  server = await startServer(['--date', `${trainingDate}T10:00:00`]);
  const trainingCalendar = await (await fetch(`${server.base}/api/today`)).json();
  equal(trainingCalendar.date, trainingDate, 'fixture date is explicit Beijing training date');
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(server.base, '/');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(server.base, '/');
      assert.match(await browser.evaluate('document.querySelector(".badges").textContent'), /TODAY’S SESSION/); checks++;
      assert.doesNotMatch(await browser.evaluate('document.querySelector(".badges").textContent'), /PREVIEW/); checks++;
      assert.ok(await browser.evaluate('document.querySelectorAll(".main-load .load-value b").length > 0'), 'training day exposes hero loads'); checks++;
      const displayedLoads = await browser.evaluate('[...document.querySelectorAll(".main-load .load-value b")].map(e => Number(e.textContent.replaceAll(",", "")))');
      const dayRows = plan.workouts.filter(row => row.week === trainingCalendar.week && row.day === trainingCalendar.day);
      const plannedLoads = ['S', 'B', 'D'].flatMap(lift => {
        const rows = dayRows.filter(row => row.bucket === 'main' && row.lift === lift && row.loadKg !== null && !(row.sets === 1 && row.reps === 3 && row.mode === 'T1.3x3'));
        const row = rows.sort((a, b) => (b.pct || 0) - (a.pct || 0))[0];
        return row ? [row.loadKg] : [];
      });
      equal(displayedLoads, plannedLoads, 'training hero matches prescribed loads');
      await noOverflow(`training-day ${width} ${theme}`);
      await screenshot(`today-training-${width}-${theme}`);
      equal(await browser.evaluate('document.querySelector("[data-testid=warmups]").open'), false, 'training-day warm-up collapsed by default');
      await click('[data-testid=warmups] summary');
      assert.match(await browser.evaluate('document.querySelector("[data-testid=warmups]").textContent'), /empty bar/, 'training-day warm-up lists steps'); checks++;
      await noOverflow(`training-day warm-up expanded ${width} ${theme}`);
    }
  }
  console.log('PASS training-day clock fixture: explicit date, hero loads match API, four widths and two themes');

  // All writes below target serve_fixture.py's temporary SQLite database, never a live journal.
  const trainingBase = server.base;
  async function trainingApi(path) {
    const response = await fetch(`${trainingBase}${path}`);
    equal(response.status, 200, `training fixture GET ${path}`);
    return response.json();
  }
  async function fields(selector) {
    return browser.evaluate(`Object.fromEntries([...document.querySelectorAll(${JSON.stringify(`${selector} input, ${selector} select, ${selector} textarea`)})].map(element => [element.name, element.type === 'checkbox' ? element.checked : element.value]))`);
  }
  async function enterFields(selector, values) {
    for (const [name, value] of Object.entries(values)) await input(`${selector} [name="${name}"]`, value);
  }
  async function dailyLoaded() {
    await browser.waitFor('document.querySelectorAll(".daily-record .record-form").length === 2 && [...document.querySelectorAll(".daily-record .record-form")].every(form => form.getAttribute("aria-busy") === "false" && !form.querySelector(".load-failure") && !form.querySelector("button[type=submit]").disabled)');
  }
  async function blockedTrainingRequests(paths, action, label, requestBase = trainingBase, abortedPaths = []) {
    equal(browser.errors, [], `${label}: clean console before deliberate network failure`);
    const failureStart = browser.networkFailures.length;
    await browser.send('Network.setBlockedURLs', { urls: paths.map(path => `${requestBase}${path}*`) });
    try {
      await action();
      // Network.loadingFailed is authoritative even when Chrome emits no console entry.
      equal(browser.errors.filter(entry => entry.source !== 'network'), [], `${label}: no runtime or console exceptions`);
      const expected = entry => entry.source === 'network' && typeof entry.url === 'string' &&
        paths.some(path => entry.url === `${requestBase}${path}` || entry.url.startsWith(`${requestBase}${path}?`)) &&
        /net::ERR_BLOCKED_BY_CLIENT/.test(entry.text);
      equal(browser.errors.filter(entry => entry.source === 'network' && !expected(entry)), [], `${label}: no unexpected network errors`);
      const failures = browser.networkFailures.slice(failureStart);
      const expectedFailure = entry => typeof entry.url === 'string' &&
        paths.some(path => entry.url === `${requestBase}${path}` || entry.url.startsWith(`${requestBase}${path}?`)) &&
        entry.blockedReason === 'inspector' && entry.canceled === false && entry.type === 'Fetch';
      const expectedAbort = entry => entry.canceled === true && entry.errorText === 'net::ERR_ABORTED' &&
        entry.type === 'Fetch' && abortedPaths.some(path => entry.url === `${requestBase}${path}`);
      equal(failures.filter(entry => !expectedFailure(entry) && !expectedAbort(entry)), [], `${label}: no unexpected request failures`);
      for (const path of paths) {
        equal(failures.some(entry => expectedFailure(entry) && (entry.url === `${requestBase}${path}` || entry.url.startsWith(`${requestBase}${path}?`))), true, `${label}: recorded blocked ${path}`);
      }
      for (let index = browser.errors.length - 1; index >= 0; index--) {
        if (expected(browser.errors[index])) browser.errors.splice(index, 1);
      }
    } finally {
      await browser.send('Network.setBlockedURLs', { urls: [] });
    }
    equal(browser.errors, [], `${label}: expected network failures audited separately`);
  }
  const trainingPlan = await trainingApi('/api/plan');
  const cycleId = trainingPlan.meta.planId;
  const logUrl = `/api/log?${new URLSearchParams({ cycle_id: cycleId })}`;
  const sessionId = `${trainingCalendar.week}|${trainingCalendar.day}`;
  const readinessUrl = `/api/readiness?${new URLSearchParams({ cycle_id: cycleId, date: trainingDate, session_id: sessionId })}`;
  const metricsUrl = `/api/body-metrics?${new URLSearchParams({ cycle_id: cycleId, date: trainingDate })}`;
  const orderedRows = ['main', 'sbdVar', 'nonSbdVar', 'accessory'].flatMap(bucket => trainingPlan.workouts.filter(item => item.week === trainingCalendar.week && item.day === trainingCalendar.day && item.bucket === bucket));
  assert.ok(orderedRows.length >= 2, 'training fixture has two independent exercise editors'); checks++;
  const firstExercise = '.exercise-rows > article.exercise:nth-of-type(1)';
  const secondExercise = '.exercise-rows > article.exercise:nth-of-type(2)';
  const firstEditor = `${firstExercise} .log-editor`;
  const secondEditor = `${secondExercise} .log-editor`;
  const firstKey = `${orderedRows[0].week}|${orderedRows[0].day}|${orderedRows[0].seq}`;
  const secondKey = `${orderedRows[1].week}|${orderedRows[1].day}|${orderedRows[1].seq}`;
  const recoveryForm = '.daily-record .record-form:not(.body-form)';
  const bodyForm = '.daily-record .body-form';
  const visibleEditors = '[...document.querySelectorAll(".log-editor")].filter(form => form.getBoundingClientRect().width > 0).length';
  const actualValues = record => Object.fromEntries(['load', 'sets', 'reps', 'rpe', 'note'].map(key => [key, record[key]]));
  const withoutStamp = record => Object.fromEntries(Object.entries(record).filter(([key]) => key !== 'updated_at'));

  await browser.viewport(390);
  await load(trainingBase, '/');
  await dailyLoaded();
  equal((await trainingApi(logUrl)).logs, {}, 'isolated training fixture starts with no actual logs');
  equal((await trainingApi(readinessUrl)).record, null, 'training recovery starts unrecorded');
  equal((await trainingApi(metricsUrl)).records, [], 'training body metrics start unrecorded');
  equal(await browser.evaluate(visibleEditors), 0, 'all exercise editors start closed');
  equal(await browser.evaluate('document.querySelector(".daily-record").open'), false, 'daily record starts collapsed');
  equal(await browser.evaluate('document.querySelectorAll(".log-toggle").length'), orderedRows.length, 'one log toggle for each prescribed exercise');
  equal(await browser.evaluate(`Number(document.querySelector(${JSON.stringify(`${firstExercise} .exercise-index`)}).textContent)`), orderedRows[0].seq, 'first editor maps to fixture workout key');
  equal(await browser.evaluate(`Number(document.querySelector(${JSON.stringify(`${secondExercise} .exercise-index`)}).textContent)`), orderedRows[1].seq, 'second editor maps to a different fixture workout key');
  await click(`${firstExercise} .log-toggle`);
  equal(await browser.evaluate(visibleEditors), 1, 'opening a log exposes exactly one editor');
  const firstRow = orderedRows[0];
  const lastSegment = firstRow.segments?.at(-1);
  const suggestionLoad = firstRow.bucket === 'accessory' ? null : (lastSegment?.load ?? firstRow.loadKg);
  const suggestionReps = lastSegment?.reps ?? firstRow.reps;
  equal(await fields(firstEditor), { load: suggestionLoad === null || suggestionLoad === undefined ? '' : String(suggestionLoad), sets: '', reps: suggestionReps === null || suggestionReps === undefined ? '' : String(suggestionReps), rpe: '', note: '' }, 'fresh actual sets, RPE and note stay blank; only load/reps have plan suggestions');
  assert.match(await browser.evaluate(`document.querySelector(${JSON.stringify(`${firstEditor} .load-field small`)}).textContent`), /Planned suggestion.*Confirm or replace/, 'planned load is explicitly a suggestion'); checks++;
  assert.match(await browser.evaluate(`document.querySelector(${JSON.stringify(`${firstEditor} [name=reps]`)}).parentElement.querySelector("small").textContent`), /Planned suggestion.*Confirm actual reps/, 'planned reps are explicitly a suggestion'); checks++;
  const firstDraft = { load: '102.5', sets: '3', reps: '5', rpe: '8.5', note: 'Training fixture only: last working set confirmed, warm-ups excluded. Draft survives closing and switching editors.' };
  await enterFields(firstEditor, firstDraft);
  await click(`${firstExercise} .log-toggle`);
  equal(await browser.evaluate(visibleEditors), 0, 'closing a log hides the editor');
  equal(await fields(firstEditor), firstDraft, 'v-show closing retains every unsaved actual field');
  await click(`${secondExercise} .log-toggle`);
  equal(await browser.evaluate(visibleEditors), 1, 'switching exercises opens only the second editor');
  equal((await fields(secondEditor)).sets, '', 'another fresh editor never copies prescribed sets');
  const secondDraft = { load: '77.5', sets: '2', reps: '8', rpe: '7.5', note: 'Independent second-exercise draft; not a saved log.' };
  await enterFields(secondEditor, secondDraft);
  await click(`${firstExercise} .log-toggle`);
  equal(await browser.evaluate('document.querySelectorAll(".log-editor").length'), 2, 'visited editors remain mounted for drafts');
  equal(await browser.evaluate(visibleEditors), 1, 'mounted drafts never create two visible editors');
  equal(await fields(firstEditor), firstDraft, 'switching back restores the first draft');
  equal(await fields(secondEditor), secondDraft, 'switching away retains the second draft');
  equal(await browser.evaluate('[...document.querySelectorAll(".log-toggle[aria-expanded=true]")].length'), 1, 'only the visible editor toggle is expanded');
  await click(`${firstEditor} .save-log`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${firstEditor} .log-saved`)})) && document.querySelector(${JSON.stringify(firstEditor)}).getAttribute('aria-busy') === 'false'`);
  const firstActual = { load: 102.5, sets: 3, reps: 5, rpe: 8.5, note: firstDraft.note };
  const positiveLogs = await trainingApi(logUrl);
  equal(positiveLogs.cycle_id, cycleId, 'positive actual log belongs to the fixture cycle');
  equal(Object.keys(positiveLogs.logs), [firstKey], 'saving one editor does not commit another draft');
  equal(actualValues(positiveLogs.logs[firstKey]), firstActual, 'UI positive-set save persists exact load, sets, reps, RPE and note');
  equal(typeof positiveLogs.logs[firstKey].updated_at, 'string', 'real SQLite log carries a save timestamp');
  equal(await trainingApi('/api/plan'), trainingPlan, 'saving actual sets never changes the prescription');
  await load(trainingBase, '/');
  await dailyLoaded();
  await click(`${firstExercise} .log-toggle`);
  equal(await fields(firstEditor), firstDraft, 'reload hydrates saved positive actuals from the API');
  equal(await browser.evaluate(`document.querySelector(${JSON.stringify(firstEditor)}).textContent.includes('Planned suggestion')`), false, 'hydrated actuals are no longer labelled planned suggestions');

  const retryDraft = { load: '105.75', sets: '4', reps: '6', rpe: '9', note: 'Retained after a deliberately blocked save; retry must write these exact actuals.' };
  await enterFields(firstEditor, retryDraft);
  await blockedTrainingRequests(['/api/log'], async () => {
    await click(`${firstEditor} .save-log`);
    await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${firstEditor} .log-errors`)})) && document.querySelector(${JSON.stringify(firstEditor)}).getAttribute('aria-busy') === 'false'`);
    assert.match(await browser.evaluate(`document.querySelector(${JSON.stringify(`${firstEditor} .log-errors`)}).textContent`), /Unable to save.*Your entries are still here/, 'log network failure is explained without discarding input'); checks++;
    equal(await fields(firstEditor), retryDraft, 'failed log save preserves all inputs');
    equal(await browser.evaluate(`Boolean(document.querySelector(${JSON.stringify(`${firstEditor} .log-saved`)}))`), false, 'failed log save does not claim success');
    equal((await trainingApi(logUrl)).logs, positiveLogs.logs, 'blocked log PUT leaves SQLite actuals unchanged');
  }, 'log failed save');
  await click(`${firstEditor} .save-log`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${firstEditor} .log-saved`)}))`);
  const retryActual = { load: 105.75, sets: 4, reps: 6, rpe: 9, note: retryDraft.note };
  equal(actualValues((await trainingApi(logUrl)).logs[firstKey]), retryActual, 'unblocked retry saves the retained actuals');
  await click(`${secondExercise} .log-toggle`);
  const skipNote = 'Explicitly skipped working sets; fixture only.';
  await enterFields(secondEditor, { load: '88.5', reps: '12', rpe: '8.5', note: skipNote, sets: '0' });
  equal(await browser.evaluate(`[...document.querySelectorAll(${JSON.stringify(`${secondEditor} [name=load], ${secondEditor} [name=reps], ${secondEditor} [name=rpe]`)})].every(element => element.matches(':disabled'))`), true, 'explicit zero sets disables irrelevant load, reps and RPE');
  await click(`${secondEditor} .save-log`);
  await browser.waitFor(`document.querySelector(${JSON.stringify(`${secondEditor} .log-saved`)})?.textContent.includes('Skipped exercise saved.')`);
  const skippedActual = { load: null, sets: 0, reps: 0, rpe: null, note: skipNote };
  const skippedLogs = await trainingApi(logUrl);
  equal(Object.keys(skippedLogs.logs).sort(), [firstKey, secondKey].sort(), 'explicit skip creates only the selected second log');
  equal(actualValues(skippedLogs.logs[secondKey]), skippedActual, 'zero-set UI save normalizes load/RPE to null and reps to zero');
  equal(actualValues(skippedLogs.logs[firstKey]), retryActual, 'skipping another exercise preserves positive actuals');
  await load(trainingBase, '/');
  await dailyLoaded();
  await click(`${secondExercise} .log-toggle`);
  equal(await fields(secondEditor), { load: '', sets: '0', reps: '0', rpe: '', note: skipNote }, 'explicit skip hydrates as zero sets, zero reps and blank load/RPE');

  await click('.daily-record summary');
  equal(await browser.evaluate('document.querySelector(".daily-record").open'), true, 'daily recovery and body forms expand together');
  equal(await browser.evaluate('document.querySelector(".record-form h3").textContent'), 'Recovery', 'first daily form is recovery');
  equal(await browser.evaluate('document.querySelector(".body-form h3").textContent'), 'Body metrics', 'body metrics have a separate form');
  const emptyRecovery = { recovery: '', arousal: '', nutrition: '', hrv: '', rhr: '', sleep_score: '', session_time: '', joint_pain: false, note: '' };
  const emptyBody = { bodyweight: '', bodyfat: '', waist: '', chest: '', hips: '', upper_arm: '', thigh: '', calf: '' };
  equal(await fields(recoveryForm), emptyRecovery, 'fresh recovery form has no invented readings');
  equal(await fields(bodyForm), emptyBody, 'fresh body form has no invented measurements');
  equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), 'Incomplete', 'unrecorded readiness is Incomplete');
  await enterFields(recoveryForm, { recovery: '4', arousal: '5', hrv: '55', rhr: '60', note: 'Two subjective ratings and raw physiological readings; no baseline history.' });
  await click(`${recoveryForm} button[type=submit]`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${recoveryForm} .save-success`)}))`);
  const partialRecovery = await trainingApi(readinessUrl);
  const partialRecord = { date: trainingDate, session_id: sessionId, recovery: 4, arousal: 5, nutrition: null, hrv: 55, rhr: 60, sleep_score: null, session_time: null, joint_pain: false, note: 'Two subjective ratings and raw physiological readings; no baseline history.' };
  equal(withoutStamp(partialRecovery.record), partialRecord, 'partial readiness UI save retains raw readings and null missing inputs');
  equal(partialRecovery.evaluation.validInputs, 2, 'HRV and resting HR without baselines are not scored inputs');
  equal([partialRecovery.evaluation.score, partialRecovery.evaluation.rec], [null, null], 'fewer than three valid scored inputs gives no score or REC');
  equal([partialRecovery.evaluation.scores.hrv, partialRecovery.evaluation.scores.rhr], [null, null], 'raw HRV/RHR never become scores without sufficient history');
  equal(['hrv', 'rhr'].map(key => [partialRecovery.evaluation.baseline[key].count, partialRecovery.evaluation.baseline[key].status]), [[0, 'insufficient_history'], [0, 'insufficient_history']], 'same-day readings do not create a prior 28-day baseline');
  equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), 'Incomplete', 'saved two-input readiness remains Incomplete');
  equal(await browser.evaluate('document.querySelectorAll("[data-testid=recovery-coefficient]").length'), 0, 'Incomplete readiness shows no numeric recovery coefficient');
  assert.match(await browser.evaluate('document.querySelector(".evaluation").textContent'), /2 available/, 'Incomplete state explains valid scored input count'); checks++;
  assert.match(await browser.evaluate('document.querySelector(".baseline-line").textContent'), /HRV: baseline pending.*0 valid days.*Resting HR: baseline pending.*0 valid days/s, 'raw physiology shows pending baselines'); checks++;
  await click(`${recoveryForm} label.pain-control`);
  equal((await fields(recoveryForm)).joint_pain, true, 'pain label is the checkbox touch control');
  assert.match(await browser.evaluate('document.querySelector(".pain-warning").textContent'), /A readiness score does not override pain/, 'pain caution appears independently of a complete score'); checks++;
  equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), 'Incomplete', 'pain toggle does not manufacture a readiness score');
  await click(`${recoveryForm} button[type=submit]`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${recoveryForm} .save-success`)}))`);
  const painfulPartial = await trainingApi(readinessUrl);
  equal(painfulPartial.evaluation.scores, partialRecovery.evaluation.scores, 'joint pain never changes scored input values');
  equal(painfulPartial.evaluation.score, null, 'joint pain leaves an incomplete score incomplete');
  equal(painfulPartial.record.joint_pain, true, 'pain warning persists in the recovery record');
  assert.ok(painfulPartial.evaluation.advice.some(message => /Caution: joint pain reported/.test(message)), 'backend pain caution is independent advice'); checks++;
  await input(`${recoveryForm} [name=nutrition]`, '6');
  await click(`${recoveryForm} button[type=submit]`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${recoveryForm} .save-success`)})) && document.querySelector('.evaluation-line strong').textContent === '66.7'`);
  const completeRecovery = await trainingApi(readinessUrl);
  equal([completeRecovery.record.recovery, completeRecovery.record.arousal, completeRecovery.record.nutrition], [4, 5, 6], 'UI recovery ratings persist exact 4/5/6 inputs');
  equal(completeRecovery.evaluation.validInputs, 3, 'only the three subjective ratings are scored');
  equal(completeRecovery.evaluation.score.toFixed(1), '66.7', 'independent 50/66.6667/83.3333 mean displays 66.7');
  equal(completeRecovery.evaluation.rec.toFixed(2), '1.08', 'independent 0.75 + 0.5 × 2/3 recovery coefficient displays 1.08');
  equal(await browser.evaluate('document.querySelector("[data-testid=recovery-coefficient]").textContent'), 'REC 1.08 · recovery coefficient, not applied.', 'numeric backend REC is displayed as advisory only');
  equal([completeRecovery.evaluation.scores.hrv, completeRecovery.evaluation.scores.rhr], [null, null], 'complete readiness still excludes unbaselined raw HRV/RHR');
  equal(await browser.evaluate('Boolean(document.querySelector(".pain-warning"))'), true, 'complete score never hides the independent pain caution');

  await enterFields(recoveryForm, { hrv: '57.5', note: 'Recovery draft retained after a blocked save; retry must preserve date, session and pain.' });
  const retainedRecovery = await fields(recoveryForm);
  await blockedTrainingRequests(['/api/readiness'], async () => {
    await click(`${recoveryForm} button[type=submit]`);
    await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${recoveryForm} > .error`)})) && document.querySelector(${JSON.stringify(recoveryForm)}).getAttribute('aria-busy') === 'false'`);
    assert.match(await browser.evaluate(`document.querySelector(${JSON.stringify(`${recoveryForm} > .error`)}).textContent`), /Recovery was not saved.*Your inputs have been kept/, 'recovery failure explains retained inputs'); checks++;
    equal(await fields(recoveryForm), retainedRecovery, 'failed readiness save preserves all ratings, raw readings, pain and note');
    equal(await browser.evaluate(`Boolean(document.querySelector(${JSON.stringify(`${recoveryForm} .save-success`)}))`), false, 'failed recovery save never shows Saved');
    equal((await trainingApi(readinessUrl)).record, completeRecovery.record, 'blocked recovery PUT leaves the previous SQLite record intact');
  }, 'recovery failed save');
  await click(`${recoveryForm} button[type=submit]`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${recoveryForm} .save-success`)})) && !document.querySelector(${JSON.stringify(`${recoveryForm} > .error`)})`);
  const finalRecovery = await trainingApi(readinessUrl);
  equal(withoutStamp(finalRecovery.record), { ...partialRecord, nutrition: 6, hrv: 57.5, joint_pain: true, note: retainedRecovery.note }, 'recovery retry writes retained inputs to the same date/session');
  equal(await fields(recoveryForm), retainedRecovery, 'recovery retry response hydrates without losing entries');
  equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), '66.7', 'recovery retry keeps independently computed readiness');

  const bodyDraft = { ...emptyBody, bodyweight: '82.5', bodyfat: '0', waist: '80' };
  await enterFields(bodyForm, { bodyweight: '82.5', bodyfat: '0', waist: '80' });
  equal(await fields(bodyForm), bodyDraft, 'body draft records explicit zero fat while leaving optional measurements blank');
  await blockedTrainingRequests(['/api/body-metrics'], async () => {
    await click(`${bodyForm} button[type=submit]`);
    await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${bodyForm} > .error`)})) && document.querySelector(${JSON.stringify(bodyForm)}).getAttribute('aria-busy') === 'false'`);
    assert.match(await browser.evaluate(`document.querySelector(${JSON.stringify(`${bodyForm} > .error`)}).textContent`), /Body metrics were not saved.*Your inputs have been kept/, 'body failure explains retained entries'); checks++;
    equal(await fields(bodyForm), bodyDraft, 'failed body save preserves bodyweight, zero fat and waist');
    equal(await browser.evaluate(`Boolean(document.querySelector(${JSON.stringify(`${bodyForm} .save-success`)}))`), false, 'failed body save never shows Saved');
    equal((await trainingApi(metricsUrl)).records, [], 'blocked body PUT creates no partial SQLite measurements');
  }, 'body failed save');
  await click(`${bodyForm} button[type=submit]`);
  await browser.waitFor(`Boolean(document.querySelector(${JSON.stringify(`${bodyForm} .save-success`)})) && !document.querySelector(${JSON.stringify(`${bodyForm} > .error`)})`);
  const bodyRecord = { date: trainingDate, bodyweight: 82.5, bodyfat: 0, measurements: { waist: 80, chest: null, hips: null, upper_arm: null, thigh: null, calf: null } };
  const finalMetrics = await trainingApi(metricsUrl);
  equal(finalMetrics.records, [bodyRecord], 'real body retry saves 82.5 kg, 0% fat, 80 cm waist and null other measurements');
  equal(finalMetrics.bodyweight, { value: 82.5, date: trainingDate }, 'bodyweight source retains its actual recorded date');
  equal(await fields(bodyForm), bodyDraft, 'body retry hydrates explicit zero without converting it to blank');
  await load(trainingBase, '/');
  await dailyLoaded();
  equal(await browser.evaluate('document.querySelector(".daily-record").open'), false, 'saved daily records still reload collapsed');
  await click('.daily-record summary');
  equal(await fields(recoveryForm), retainedRecovery, 'reload hydrates recovery from SQLite, including pain and note');
  equal(await fields(bodyForm), bodyDraft, 'reload hydrates exact dated body metrics including zero fat');
  equal(await browser.evaluate('[...document.querySelectorAll(".daily-record .form-heading time")].map(time => [time.dateTime, time.textContent])'), [[trainingDate, trainingDate], [trainingDate, trainingDate]], 'both forms show the exact associated Beijing training date');
  assert.ok(await browser.evaluate(`document.querySelector(${JSON.stringify(`${recoveryForm} .form-heading`)}).textContent.includes(${JSON.stringify(`Session: ${sessionId}`)})`), 'recovery reload retains the prescribed session key'); checks++;
  equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), '66.7', 'reload retains backend readiness evaluation');
  equal(await browser.evaluate('document.querySelector("[data-testid=recovery-coefficient]").textContent.includes("REC 1.08")'), true, 'reload retains numeric REC');
  const trainingDayPath = `/plan/week/${trainingCalendar.week}/day/${trainingCalendar.day}`;
  await load(trainingBase, trainingDayPath);
  await dailyLoaded();
  await click('.daily-record summary');
  equal(await fields(recoveryForm), retainedRecovery, 'Today and prescribed-day views share the same recovery date/session');
  equal(await fields(bodyForm), bodyDraft, 'Today and prescribed-day views share the same dated body metrics');
  const anotherRow = trainingPlan.workouts.find(item => item.date > trainingDate);
  assert.ok(anotherRow, 'fixture has a later prescribed date to test association'); checks++;
  await load(trainingBase, `/plan/week/${anotherRow.week}/day/${anotherRow.day}`);
  await dailyLoaded();
  await click('.daily-record summary');
  equal(await fields(recoveryForm), emptyRecovery, 'a different training date does not inherit saved recovery');
  equal(await fields(bodyForm), emptyBody, 'past bodyweight is never copied into a different date’s fields');
  equal(await browser.evaluate('[...document.querySelectorAll(".daily-record .form-heading time")].map(time => time.dateTime)'), [anotherRow.date, anotherRow.date], 'navigated forms are associated only with the selected date');
  equal(await browser.evaluate('document.querySelector(".bodyweight-source time").dateTime'), trainingDate, 'later date labels the prior bodyweight source date');
  equal(await browser.evaluate('document.querySelector(".bodyweight-source strong").textContent'), '82.5 kg', 'later date shows past weight as a source, not a current measurement');
  equal((await trainingApi(`/api/readiness?${new URLSearchParams({ cycle_id: cycleId, date: anotherRow.date, session_id: `${anotherRow.week}|${anotherRow.day}` })}`)).record, null, 'navigation never creates a recovery record for another date');
  equal((await trainingApi(metricsUrl)).records, [bodyRecord], 'date navigation never creates or mutates body measurements');

  await blockedTrainingRequests(['/api/readiness', '/api/body-metrics'], async () => {
    await load(trainingBase, '/');
    await browser.waitFor('document.querySelectorAll(".daily-record .load-failure").length === 2 && [...document.querySelectorAll(".daily-record .record-form")].every(form => form.getAttribute("aria-busy") === "false")');
    await click('.daily-record summary');
    equal(await fields(recoveryForm), emptyRecovery, 'blocked recovery GET never substitutes previously saved inputs');
    equal(await fields(bodyForm), emptyBody, 'blocked body GET never substitutes a cached daily record');
    equal(await browser.evaluate('[...document.querySelectorAll(".daily-record .record-form fieldset")].map(fieldset => fieldset.disabled)'), [true, true], 'failed daily GET disables both fieldsets');
    equal(await browser.evaluate('[...document.querySelectorAll(".daily-record button[type=submit]")].map(button => button.disabled)'), [true, true], 'failed daily GET disables both save buttons');
    equal(await browser.evaluate('[...document.querySelectorAll(".daily-record fieldset input, .daily-record fieldset select, .daily-record fieldset textarea")].every(element => element.matches(":disabled"))'), true, 'failed daily GET disables every input, including pain checkbox');
    equal(await browser.evaluate('document.querySelectorAll(".daily-record .evaluation").length'), 0, 'failed recovery GET hides stale score and REC');
    await click(`${recoveryForm} button[type=submit]`);
    await click(`${bodyForm} button[type=submit]`);
    equal(await browser.evaluate('document.querySelectorAll(".daily-record .save-success").length'), 0, 'disabled save clicks cannot claim success');
    equal((await trainingApi(readinessUrl)).record, finalRecovery.record, 'disabled recovery save preserves the existing record');
    equal((await trainingApi(metricsUrl)).records, [bodyRecord], 'disabled body save preserves the existing dated metrics');
  }, 'daily reload GET failures');
  equal(await browser.evaluate('[...document.querySelectorAll(".daily-record button[type=submit]")].map(button => button.disabled)'), [true, true], 'unblocking network alone does not enable saves before a successful reload');
  await click(`${recoveryForm} .load-failure button`);
  await browser.waitFor(`!document.querySelector(${JSON.stringify(`${recoveryForm} .load-failure`)}) && !document.querySelector(${JSON.stringify(`${recoveryForm} button[type=submit]`)}).disabled`);
  equal(await fields(recoveryForm), retainedRecovery, 'recovery GET retry hydrates the retained record before enabling save');
  equal(await browser.evaluate(`document.querySelector(${JSON.stringify(`${bodyForm} button[type=submit]`)}).disabled`), true, 'recovery retry cannot enable body save without its own successful GET');
  await click(`${bodyForm} .load-failure button`);
  await dailyLoaded();
  equal(await fields(bodyForm), bodyDraft, 'body GET retry hydrates the dated measurements before enabling save');
  equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), '66.7', 'successful recovery GET retry restores backend score');
  equal(await browser.evaluate('Boolean(document.querySelector(".pain-warning"))'), true, 'successful GET retry restores independent pain caution');
  await blockedTrainingRequests(['/api/log'], async () => {
    await browser.navigate(`${trainingBase}/`);
    await browser.waitFor('Boolean(document.querySelector(".error-panel")) && document.querySelector("main").getAttribute("aria-busy") === "false"');
    equal(await browser.evaluate('document.querySelectorAll(".log-toggle, .log-editor, .daily-record").length'), 0, 'failed initial log GET exposes no write controls or stale records');
    equal((await trainingApi(logUrl)).logs, skippedLogs.logs, 'blocked browser GET leaves both saved SQLite logs unchanged and readable');
  }, 'log reload GET failure');
  await click('.error-panel button');
  await browser.waitFor('!document.querySelector(".error-panel") && document.querySelector("main").getAttribute("aria-busy") === "false" && Boolean(document.querySelector(".log-toggle"))');
  await dailyLoaded();
  await click(`${firstExercise} .log-toggle`);
  equal(await fields(firstEditor), retryDraft, 'connection retry hydrates actuals before exposing the editor');
  equal(await trainingApi('/api/plan'), trainingPlan, 'all actual, recovery and body saves leave every prescription field unchanged');
  equal(browser.errors, [], 'log and daily successful paths have no runtime, console or unexpected network errors');

  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(trainingBase, '/');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(trainingBase, '/');
      await dailyLoaded();
      await click(`${firstExercise} .log-toggle`);
      await click('.daily-record summary');
      equal(await browser.evaluate(visibleEditors), 1, `expanded log ${width} ${theme}: exactly one visible editor`);
      equal(await fields(firstEditor), retryDraft, `expanded log ${width} ${theme}: saved actuals`);
      equal(await fields(bodyForm), bodyDraft, `expanded daily ${width} ${theme}: dated zero-fat metrics`);
      equal(await browser.evaluate('document.querySelector(".evaluation-line strong").textContent'), '66.7', `expanded daily ${width} ${theme}: score remains numeric`);
      await noOverflow(`expanded log and daily ${width} ${theme}`);
      const horizontalScroll = await browser.evaluate(`(async () => {
        const before = { x: scrollX, y: scrollY };
        const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
        scrollTo({ left: innerWidth, top: before.y, behavior: 'instant' });
        await frame();
        const right = scrollX;
        scrollTo({ left: -innerWidth, top: before.y, behavior: 'instant' });
        await frame();
        const left = scrollX;
        scrollTo({ left: before.x, top: before.y, behavior: 'instant' });
        const containers = [...document.querySelectorAll('.log-editor, .log-fields, .secondary-fields, .daily-record, .record-content, .record-form, .rating-fields, .field-grid')].filter(element => element.getBoundingClientRect().width > 0);
        const scrolling = containers.flatMap(element => {
          const previous = element.scrollLeft;
          element.scrollLeft = element.clientWidth;
          const positive = element.scrollLeft;
          element.scrollLeft = -element.clientWidth;
          const negative = element.scrollLeft;
          element.scrollLeft = previous;
          return positive !== 0 || negative !== 0 ? [{ className: element.className, positive, negative }] : [];
        });
        await frame();
        return { right, left, scrolling };
      })()`);
      equal(horizontalScroll, { right: 0, left: 0, scrolling: [] }, `expanded log and daily ${width} ${theme}: real horizontal scroll attempts cannot move page or form containers`);
      const smallControls = await browser.evaluate(`[...document.querySelectorAll('.log-toggle, .log-editor button, .log-editor input, .log-editor textarea, .daily-record summary, .daily-record button, .daily-record input:not([type=checkbox]), .daily-record select, .daily-record textarea, .daily-record label.pain-control')].filter(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility !== 'hidden' && (rect.width < 44 || rect.height < 44);
      }).map(element => ({ name: element.name || element.className || element.textContent.trim(), width: element.getBoundingClientRect().width, height: element.getBoundingClientRect().height }))`);
      equal(smallControls, [], `expanded log and daily ${width} ${theme}: visible controls have 44px touch targets; pain uses its label`);
      await screenshot(`log-expanded-${width}-${theme}`, firstEditor);
      await screenshot(`daily-expanded-${width}-${theme}`, '.daily-record');
      equal(browser.errors, [], `expanded log and daily ${width} ${theme}: no unexpected browser errors`);
    }
  }
  console.log('PASS isolated training forms: single editor and drafts, real SQLite actual/skip saves, readiness 66.7 / REC 1.08, independent pain and raw baselines, dated zero-fat body metrics, failed saves and GET retries, expanded four-width/two-theme scrolling and 44px controls');

  const prescriptionUrl = `/api/prescription?${new URLSearchParams({ cycle_id: cycleId })}`;
  const originalInfo = await trainingApi(prescriptionUrl);
  const variationLifts = { 'Low-bar Squat': 'S', 'Wide-grip Bench': 'B', 'Sumo Deadlift': 'D', 'Power Clean': 'D', OHP: 'B', 'Pull-Up': 'D', Dip: 'B', 'Bent-Over Barbell Row': 'D' };
  const ohpId = originalInfo.catalogue.find(item => item.name === 'OHP').id;
  const referenceSelector = `.reference-input[name=${JSON.stringify(ohpId)}]`;
  const settingsLoaded = async () => {
    await browser.waitFor('Boolean(document.querySelector(".preview-prescription")) && !document.querySelector(".preview-prescription").disabled');
    if (!await browser.evaluate('document.querySelector("[data-testid=prescription-settings]").open')) await click('[data-testid=prescription-settings] > summary');
  };
  await load(trainingBase, '/settings');
  await settingsLoaded();
  equal(await browser.evaluate(`document.querySelector(${JSON.stringify(referenceSelector)}).value`), '60', 'approved OHP reference starts at 60 kg');
  equal(originalInfo.policy, 'legacy', 'startup never silently applies a prescription');
  await blockedTrainingRequests(['/api/prescription/preview'], async () => {
    await click('.preview-prescription');
    await browser.waitFor('Boolean(document.querySelector(".prescription-error")) && !document.querySelector(".preview-prescription").disabled');
    equal(await browser.evaluate(`document.querySelector(${JSON.stringify(referenceSelector)}).value`), '60', 'failed preview retains reference inputs');
    equal(await trainingApi('/api/plan'), trainingPlan, 'blocked preview cannot replace original plan');
  }, 'prescription preview failure');
  await click('.preview-prescription');
  await browser.waitFor('Boolean(document.querySelector(".prescription-preview")) && Boolean(document.querySelector(".apply-prescription"))');
  equal(await trainingApi('/api/plan'), trainingPlan, 'successful preview is still read-only');
  await input(referenceSelector, '70');
  equal(await browser.evaluate('Boolean(document.querySelector(".prescription-preview"))'), false, 'editing a reference invalidates the reviewed preview');
  await click('.preview-prescription');
  await browser.waitFor('Boolean(document.querySelector(".apply-prescription")) && !document.querySelector(".apply-prescription").disabled');
  await blockedTrainingRequests(['/api/prescription/apply'], async () => {
    await click('.apply-prescription');
    await browser.waitFor('Boolean(document.querySelector(".prescription-error")) && !document.querySelector(".apply-prescription").disabled');
    equal(await browser.evaluate(`document.querySelector(${JSON.stringify(referenceSelector)}).value`), '70', 'failed apply retains edited reference');
    equal(await trainingApi('/api/plan'), trainingPlan, 'failed apply leaves every original field intact');
  }, 'prescription apply failure');
  await click('.apply-prescription');
  await browser.waitFor('document.querySelector("main").getAttribute("aria-busy") === "false" && Boolean(document.querySelector(".preview-prescription")) && !document.querySelector(".preview-prescription").disabled');
  const revisedPlan = await trainingApi('/api/plan');
  equal(revisedPlan.prescription.version, 'eight-variations-v1', 'explicit UI apply saves a versioned policy');
  equal(revisedPlan.prescription.basePlan, trainingPlan, 'original prescription remains fully recoverable');
  equal(revisedPlan.prescription.references[ohpId], 70, 'manual reference persists independently of estimated performance');
  equal(revisedPlan.workouts.map(row => [row.date, row.sets, row.reps, row.targetRpe, row.movementId]), trainingPlan.workouts.map(row => [row.date, row.sets, row.reps, row.targetRpe, row.movementId]), 'dates, sets, reps, target RPE and identities survive UI recalculation');
  equal([...new Set(revisedPlan.workouts.filter(row => variationLifts[row.movement]).map(row => row.movement))].sort(), Object.keys(variationLifts).sort(), 'all eight approved variations remain in the plan');
  for (const row of revisedPlan.workouts.filter(row => variationLifts[row.movement])) {
    equal([row.role, row.bucket, row.lift], ['variation', 'sbdVar', variationLifts[row.movement]], `${row.movement}: approved classification`);
  }
  equal((await trainingApi(logUrl)).logs, skippedLogs.logs, 'prescription apply does not rewrite actual logs');
  equal((await trainingApi(metricsUrl)).records, [bodyRecord], 'prescription apply preserves dated body metrics');
  await load(trainingBase, '/settings');
  await settingsLoaded();
  equal(await browser.evaluate(`document.querySelector(${JSON.stringify(referenceSelector)}).value`), '70', 'reference hydrates after full browser reload');
  const history = await trainingApi(prescriptionUrl);
  equal(history.versions.length, 2, 'original and recalculated immutable versions exist');
  const originalIndex = history.versions.findIndex(item => item.id === originalInfo.currentId);
  await click('.prescription-history > summary');
  await click(`.revision-list > li:nth-child(${originalIndex + 1}) .revision-compare`);
  await browser.waitFor('Boolean(document.querySelector(".revision-restore")) && !document.querySelector(".revision-restore").disabled');
  await click('.revision-restore');
  await settingsLoaded();
  await browser.waitFor(`document.querySelector(${JSON.stringify(referenceSelector)})?.value === '60'`);
  equal(await trainingApi('/api/plan'), trainingPlan, 'reviewed restore returns every original prescription field');
  equal((await trainingApi(logUrl)).logs, skippedLogs.logs, 'restore never discards actual logs');
  await click('.preview-prescription');
  await browser.waitFor('Boolean(document.querySelector(".apply-prescription")) && !document.querySelector(".apply-prescription").disabled');
  await click('.apply-prescription');
  await browser.waitFor(`document.querySelector('main').getAttribute('aria-busy') === 'false' && document.querySelector(${JSON.stringify(referenceSelector)})?.value === '60' && !document.querySelector('.preview-prescription').disabled`);
  const defaultPlan = await trainingApi('/api/plan');
  equal(defaultPlan.prescription.references[ohpId], 60, 'reviewed default reference reapplies after original restore');
  const pull = defaultPlan.workouts.find(row => row.movement === 'Pull-Up' && row.date >= trainingDate);
  assert.ok(pull, 'fixture includes a scheduled system-weight pull-up on or after the bodyweight reading'); checks++;
  await load(trainingBase, `/plan/week/${pull.week}/day/${pull.day}`);
  assert.match(await browser.evaluate('document.querySelector("[data-testid=system-load]").textContent'), /Total system weight.*bodyweight 82.5 kg/s, 'dated bodyweight is shown with system load'); checks++;
  equal(await browser.evaluate('document.querySelector("[data-testid=gpp]").open'), false, 'weekly GPP starts collapsed');
  await click('[data-testid=gpp] summary');
  assert.match(await browser.evaluate('document.querySelector("[data-testid=gpp]").textContent'), /Zone 2 cardio.*Breathing and mobility/s, 'GPP retains prescribed cardio and recovery'); checks++;
  await noOverflow('expanded weekly GPP');
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(trainingBase, '/settings');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(trainingBase, '/settings');
      await settingsLoaded();
      await click('.preview-prescription');
      await browser.waitFor('Boolean(document.querySelector(".prescription-preview"))');
      await browser.evaluate('[...document.querySelectorAll(".reference-family, .prescription-history")].forEach(item => item.open = true)');
      await noOverflow(`prescription reference and preview ${width} ${theme}`);
      equal(await browser.evaluate('[...document.querySelectorAll("[data-testid=prescription-settings] input, [data-testid=prescription-settings] button, [data-testid=prescription-settings] summary")].filter(element => { const r=element.getBoundingClientRect(); return r.width>0 && r.height>0 && (r.width<44 || r.height<44); }).map(element=>element.className)'), [], `prescription ${width} ${theme}: 44px controls`);
      equal(await browser.evaluate('(() => { const previous=scrollY; scrollTo(innerWidth,previous); const right=scrollX; scrollTo(-innerWidth,previous); const left=scrollX; scrollTo(0,previous); return [right,left]; })()'), [0, 0], `prescription ${width} ${theme}: no horizontal scrolling`);
      await screenshot(`references-${width}-${theme}`, '[data-testid=prescription-settings]');
      await load(trainingBase, `/plan/week/${pull.week}/day/${pull.day}`);
      await browser.evaluate('document.querySelector("[data-testid=gpp]").open = true; document.querySelector(".plan-day .gear").open = true');
      await noOverflow(`system load and expanded GPP/GEAR ${width} ${theme}`);
      equal(await browser.evaluate('[...document.querySelectorAll(".gear summary")].filter(element => { const r=element.getBoundingClientRect(); return r.width>0 && r.height>0 && (r.width<44 || r.height<44); }).length'), 0, `GPP/GEAR ${width} ${theme}: 44px summaries`);
      await screenshot(`supporting-work-${width}-${theme}`, '[data-testid=gpp]');
      await load(trainingBase, `/analysis?week=${pull.week}`);
      const capacity = (await trainingApi('/api/analysis')).perWeek.find(week => week.n === pull.week);
      for (const code of ['S', 'B', 'D']) equal(await browser.evaluate(`document.querySelector('[data-testid=equivalent-${code}]').textContent`), capacity.equivalent[code].total.toFixed(1), `${width} ${theme}: ${code} displays backend-rounded equivalent capacity`);
      equal(await browser.evaluate('document.querySelector("[data-testid=weekly-total]").textContent'), String(capacity.total), `${width} ${theme}: raw weekly sets remain separate`);
      await noOverflow(`recalculated capacity ${width} ${theme}`);
      await screenshot(`prescription-analysis-${width}-${theme}`);
      equal(browser.errors, [], `prescription ${width} ${theme}: no unexpected browser errors`);
    }
  }
  console.log('PASS versioned prescriptions: preview/apply failures and retained inputs, eight variations, persisted manual references, original comparison/restore, unchanged actual records, dated system loads, weekly GPP, four-width/two-theme references and 44px controls');
  const beforePerformancePlan = await trainingApi('/api/plan');
  const pullRows = [1, 3].map(n => defaultPlan.workouts.find(row => row.week === n && row.movementId === pull.movementId));
  assert.ok(pullRows.every(Boolean), 'same exact pull-up ID scheduled either side of an unlogged week'); checks++;
  for (const [index, observed] of pullRows.entries()) {
    const payload = { cycle_id: cycleId, week: observed.week, day: observed.day, seq: observed.seq, sets: 2, reps: index ? 1 : 3, load: index ? 101.25 : 100, rpe: null, note: 'Isolated performance chart fixture' };
    equal((await fetch(`${trainingBase}/api/log`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).status, 200, 'save actual performance fixture');
  }
  const recorded = await trainingApi('/api/performance');
  const pullSeries = recorded.movements.find(item => item.id === pull.movementId);
  equal(pullSeries.weekly.slice(0, 3).map(item => item.value), [110, null, 101.25], 'recorded system-total estimates and raw single leave null week');
  equal(await trainingApi('/api/plan'), beforePerformancePlan, 'performance never changes references or prescriptions');
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(trainingBase, '/analysis?week=1');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(trainingBase, '/analysis?week=1');
      await input('[data-testid=performance-movement]', pull.movementId);
      equal(await browser.evaluate('document.querySelector(".performance-line").getAttribute("d").match(/M/g)?.length'), 2, 'performance path breaks at null week');
      equal(await browser.evaluate('document.querySelectorAll(".performance-point").length'), 2, 'no fake zero observations');
      equal(await browser.evaluate('document.querySelectorAll(".performance-point.estimated").length'), 1, 'estimated point labelled separately');
      equal(await browser.evaluate('document.querySelectorAll(".performance-point.actual").length'), 1, 'actual single labelled separately');
      assert.match(await browser.evaluate('document.querySelector("[data-testid=performance-records]").textContent'), /110.*Estimated.*Epley estimate.*100 kg.*101.25.*Actual single/s, 'records expose methods and raw system loads'); checks++;
      await noOverflow(`performance ${width} ${theme}`);
      await click('.weekly-reading summary');
      await noOverflow(`performance expanded source values ${width} ${theme}`);
      equal(await browser.evaluate('document.querySelectorAll(".capacity-week").length'), defaultPlan.weeks.length, 'all weekly source values remain accessible');
      await click('.weekly-reading summary');
      equal(await browser.evaluate('(() => { const previous=scrollY; scrollTo(innerWidth,previous); const right=scrollX; scrollTo(-innerWidth,previous); const left=scrollX; scrollTo(0,previous); return [right,left]; })()'), [0, 0], 'performance has no horizontal scrolling');
      await screenshot(`trends-${width}-${theme}`, '[data-testid=trend-view]');
      await input('[data-testid=performance-movement]', ohpId);
      equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=performance-empty]"))'), true, 'unlogged selected movement has explicit empty state');
    }
  }
  await blockedTrainingRequests(['/api/performance'], async () => {
    await browser.navigate(`${trainingBase}/analysis?week=1`);
    await browser.waitFor('Boolean(document.querySelector(".error-panel"))');
    equal(await browser.evaluate('document.querySelectorAll("[data-testid=trend-view], .muscle-map").length'), 0, 'failed performance request hides stale chart and anatomy');
  }, 'performance GET failure');
  await click('.error-panel button');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=trend-view]"))');
  equal(await trainingApi('/api/plan'), beforePerformancePlan, 'failure and retry do not rewrite the plan');
  console.log('PASS performance: cycle-fixed heat, anatomy-first mobile order, Epley/actual labels, null-gap curves, all widths/themes, explicit empty and failure retry');
  await server.stop(); server = null;
  const deloadDate = plan.workouts.find(row => row.week === deloadWeek.n).date;
  server = await startServer(['--date', `${deloadDate}T10:00:00`]);
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(server.base, '/');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(server.base, '/');
      assert.match(await browser.evaluate('document.querySelector("main .notice")?.textContent || ""'), /lighter loads, same movements/, 'Today deload notice uses scheduled week'); checks++;
      await noOverflow(`Today deload ${width} ${theme}`);
      await load(server.base, `/plan/week/${deloadWeek.n}`);
      await noOverflow(`Plan deload ${width} ${theme}`);
      await screenshot(`plan-deload-${width}-${theme}`);
    }
  }
  await server.stop(); server = null;
  server = await startServer(['--archive', '--date', `${plan.meta.endDate}T10:00:00`]);
  const archiveBase = server.base;
  const archiveApi = async path => (await fetch(`${archiveBase}${path}`)).json();
  const historicalReview = await archiveApi('/api/review?cycle_id=archive-fixture');
  const activeBeforeReview = await archiveApi('/api/plan');
  const activeLogsBeforeReview = await archiveApi('/api/log');
  equal(historicalReview.attainment.bodyweight, 50, 'independent historical bodyweight progress is 50 percent');
  equal(historicalReview.attainment.goal, null, 'ordinary historical singles are not actual test attainment');
  equal(historicalReview.attainment.composite, null, 'missing goal weight is not redistributed');
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(archiveBase, '/archive');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(archiveBase, '/archive');
      await browser.waitFor('document.querySelector("[data-testid=archive-view]")?.getAttribute("aria-busy") === "false"');
      equal(await browser.evaluate('document.querySelectorAll(".archive-entry").length'), 1, 'archive excludes active cycle');
      equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=archive-active-link]"))'), true, 'active review is separate from historical list');
      await noOverflow(`archive ${width} ${theme}`);
      await screenshot(`archive-${width}-${theme}`);
      await click('[data-testid=archive-cycle-archive-fixture]');
      await browser.waitFor('Boolean(document.querySelector("[data-testid=review-view]"))');
      equal(await browser.evaluate('location.pathname'), '/archive/archive-fixture', 'history has cycle-scoped deep link');
      equal(await browser.evaluate('document.querySelector("[data-testid=review-status]").textContent'), 'READ-ONLY', 'historical status explicit');
      equal(await browser.evaluate('document.querySelector("[data-testid=review-score-bodyweight] .score-value").textContent'), '50%', 'review displays server bodyweight progress');
      equal(await browser.evaluate('document.querySelector("[data-testid=review-score-goal] .score-value").textContent'), '—', 'unknown actual tests remain dash');
      equal(await browser.evaluate('document.querySelector("[data-testid=review-score-composite] .score-value").textContent'), '—', 'unknown composite remains dash');
      equal(await browser.evaluate('document.querySelectorAll(".record-form, .exercise-editor, .prescription-settings").length'), 0, 'historical review has no write forms');
      equal(await browser.evaluate('document.querySelector("[data-testid=performance-records]").textContent.includes("70 kg")'), true, 'historical performance isolated from active 100 kg log');
      await noOverflow(`review ${width} ${theme}`);
      await screenshot(`review-${width}-${theme}`);
      await click('[data-testid=archive-plan] > summary');
      equal(await browser.evaluate('document.querySelectorAll("[data-testid=archive-rows] > li").length'), plan.workouts.filter(row => row.week === 1).length, 'every historical first-week row is readable');
      assert.match(await browser.evaluate('document.querySelector("[data-testid=archive-rows]").textContent'), /70 kg.*Historical <script> data, not HTML/s, 'notes are native escaped text and actual load is historical'); checks++;
      equal(await browser.evaluate('document.querySelectorAll("[data-testid=archive-rows] script").length'), 0, 'untrusted notes never become executable markup');
      await input('[data-testid=archive-week]', plan.weeks.at(-1).n);
      equal(await browser.evaluate('document.querySelectorAll("[data-testid=archive-rows] > li").length'), plan.workouts.filter(row => row.week === plan.weeks.at(-1).n).length, 'arbitrary final week history is readable');
      await click('[data-testid=review-readiness] > summary');
      await browser.waitFor('document.querySelector("[data-testid=review-readiness] .source-reading") !== null');
      assert.match(await browser.evaluate('document.querySelector("[data-testid=review-readiness]").textContent'), /Legacy fatigue \(not recovery\).*6/s, 'legacy fatigue preserved separately'); checks++;
      equal(await browser.evaluate('[...document.querySelectorAll("main button, main select, main summary, main a")].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.width<44||r.height<44)}).map(e=>e.className)'), [], 'review controls meet 44px in expanded states');
      await noOverflow(`review expanded ${width} ${theme}`);
      equal(await browser.evaluate('(() => { const previous=scrollY; scrollTo(innerWidth,previous); const right=scrollX; scrollTo(-innerWidth,previous); const left=scrollX; scrollTo(0,previous); return [right,left]; })()'), [0, 0], 'review has no actual horizontal scrolling');
      await load(archiveBase, '/archive/archive-fixture');
      await browser.waitFor('Boolean(document.querySelector("[data-testid=review-view]"))');
      equal(await browser.evaluate('document.querySelector("[data-testid=review-status]").textContent'), 'READ-ONLY', 'deep-link reload retains historical identity');
    }
  }
  await browser.evaluate('(() => { window.reviewDownload=null; window.originalCreateURL=URL.createObjectURL; window.originalAnchorClick=HTMLAnchorElement.prototype.click; URL.createObjectURL=blob=>{window.reviewDownload=blob.text();return window.originalCreateURL(blob)}; HTMLAnchorElement.prototype.click=function(){if(!this.download)return window.originalAnchorClick.call(this)}; })()');
  await click('[data-testid=review-export]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=review-export-status]"))');
  const downloadedReview = await browser.evaluate('window.reviewDownload.then(text=>JSON.parse(text))');
  equal(downloadedReview.plan_id, 'archive-fixture', 'download uses selected historical cycle');
  equal(downloadedReview.logs[0].load, 70, 'complete blob retains raw historical actual');
  equal(downloadedReview.prescription_versions[0].plan.meta.planId, 'archive-fixture', 'download preserves historical prescription plan');
  equal(downloadedReview.readiness.legacy[0].fatigue, 6, 'download preserves original fatigue');
  await browser.evaluate('URL.createObjectURL=window.originalCreateURL; HTMLAnchorElement.prototype.click=window.originalAnchorClick');
  await blockedTrainingRequests(['/api/review/export'], async () => {
    await click('[data-testid=review-export]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=review-error]"))');
    equal(await browser.evaluate('document.querySelectorAll("[data-testid=review-view]").length'), 0, 'failed export clears stale review');
  }, 'review export failure', archiveBase);
  await click('[data-testid=review-retry]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=review-view]"))');
  await blockedTrainingRequests(['/api/review'], async () => {
    await browser.navigate(`${archiveBase}/archive/archive-fixture`);
    await browser.waitFor('Boolean(document.querySelector("[data-testid=review-error]"))');
    equal(await browser.evaluate('document.querySelectorAll("[data-testid=review-view]").length'), 0, 'failed GET clears stale review');
  }, 'review GET failure', archiveBase, ['/api/analysis?cycle_id=archive-fixture&mode=log', '/api/performance?cycle_id=archive-fixture']);
  await click('[data-testid=review-retry]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=review-view]"))');
  await load(archiveBase, `/archive/${encodeURIComponent(plan.meta.planId)}`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=review-view]"))');
  equal(await browser.evaluate('document.querySelector("[data-testid=review-status]").textContent'), 'IN PROGRESS', 'active review never implies archival');
  equal(await archiveApi('/api/plan'), activeBeforeReview, 'archive navigation and exports do not modify active plan');
  equal(await archiveApi('/api/log'), activeLogsBeforeReview, 'archive navigation and exports do not modify active logs');
  equal((await archiveApi('/api/cycle')).active_cycle_id, plan.meta.planId, 'export retains active cycle');
  console.log('PASS review/archive: cycle-isolated read-only deep links, 50-percent bodyweight progress, null test scores, complete Blob export, legacy fatigue, all widths/themes and failure retry');
  async function uploadPlan(text, filename = 'candidate.json') {
    await browser.evaluate(`(() => { const input=document.querySelector('[data-testid=import-file]'); const transfer=new DataTransfer(); transfer.items.add(new File([${JSON.stringify(text)}],${JSON.stringify(filename)},{type:'application/json'})); input.files=transfer.files; input.dispatchEvent(new Event('change',{bubbles:true})); })()`);
    await browser.waitFor('!document.querySelector("[data-testid=import-preview]")?.disabled');
  }
  async function expectedImportRejection(path, status, action) {
    equal(browser.errors, [], 'import rejection starts with clean console');
    const first = browser.networkFailures.length;
    await action();
    const expected = entry => entry.source === 'network' && entry.url === `${archiveBase}${path}` && entry.text.includes(String(status));
    equal(browser.errors.filter(entry => !expected(entry)), [], 'import rejection has no unexpected runtime or network error');
    equal(browser.networkFailures.slice(first), [], 'HTTP rejection is not an unexpected failed transport');
    for (let index = browser.errors.length - 1; index >= 0; index--) if (expected(browser.errors[index])) browser.errors.splice(index, 1);
  }
  const candidatePlan = structuredClone(activeBeforeReview);
  candidatePlan.meta.planId = 'browser-import-new-cycle-with-a-long-identity';
  candidatePlan.meta.name = 'Imported <script> text stays data';
  const candidateText = JSON.stringify(candidatePlan);
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await load(archiveBase, '/settings');
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      await load(archiveBase, '/settings');
      equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=plan-import]"))'), true, 'Settings has strict import entry');
      await noOverflow(`import empty ${width} ${theme}`);
      await uploadPlan(candidateText);
      await click('[data-testid=import-preview]');
      await browser.waitFor('Boolean(document.querySelector("[data-testid=import-comparison]"))');
      equal(await browser.evaluate('document.querySelector("[data-testid=import-current-id]").textContent'), activeBeforeReview.meta.planId, 'preview names exact old cycle');
      equal(await browser.evaluate('document.querySelector("[data-testid=import-candidate-id]").textContent'), candidatePlan.meta.planId, 'preview names exact new cycle');
      equal(await browser.evaluate('document.querySelector("[data-testid=import-confirm]").disabled'), true, 'explicit acknowledgement required');
      equal(await browser.evaluate('document.querySelectorAll("[data-testid=plan-import] script").length'), 0, 'uploaded plan text cannot execute markup');
      equal((await archiveApi('/api/cycle')).active_cycle_id, activeBeforeReview.meta.planId, 'preview does not activate');
      await noOverflow(`import preview ${width} ${theme}`);
      await screenshot(`import-${width}-${theme}`);
      await browser.evaluate('[...document.querySelectorAll("[data-testid=import-comparison] details")].forEach(e=>e.open=true)');
      await noOverflow(`import expanded ${width} ${theme}`);
      equal(await browser.evaluate('[...document.querySelectorAll("[data-testid=plan-import] button, [data-testid=plan-import] summary, [data-testid=plan-import] input[type=file], [data-testid=plan-import] label")].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.width<44||r.height<44)}).map(e=>e.className)'), [], 'import expanded controls meet 44px');
      equal(await browser.evaluate('(()=>{const y=scrollY;scrollTo(innerWidth,y);const r=scrollX;scrollTo(-innerWidth,y);const l=scrollX;scrollTo(0,y);return[r,l]})()'), [0, 0], 'import no actual horizontal scroll');
      await click('[data-testid=import-cancel]');
      equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=import-comparison]"))'), false, 'cancel discards preview without activation');
    }
  }
  await uploadPlan(candidateText);
  await blockedTrainingRequests(['/api/plan/import/preview'], async () => {
    await click('[data-testid=import-preview]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=import-error]"))');
    equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=import-comparison]"))'), false, 'failed preview has no stale confirm');
  }, 'import preview network failure', archiveBase);
  await click('[data-testid=import-preview]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=import-comparison]"))');
  await input('[data-testid=import-confirm-check]', true);
  await blockedTrainingRequests(['/api/plan/import/confirm'], async () => {
    await click('[data-testid=import-confirm]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=import-error]"))');
    equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=import-comparison]"))'), false, 'failed confirmation requires new preview, not automatic retry');
    equal((await archiveApi('/api/cycle')).active_cycle_id, activeBeforeReview.meta.planId, 'blocked confirmation never changes cycle');
  }, 'import confirm network failure', archiveBase);
  await uploadPlan('{"schemaVersion":"RPL-Raw-v1","schemaVersion":"RPL-Raw-v1"}');
  await expectedImportRejection('/api/plan/import/preview', 422, async () => {
    await click('[data-testid=import-preview]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=import-error]"))');
    assert.match(await browser.evaluate('document.querySelector("[data-testid=import-error]").textContent'), /schemaVersion.*unique|unique.*schemaVersion/s); checks++;
  });
  await uploadPlan(JSON.stringify(activeBeforeReview));
  await expectedImportRejection('/api/plan/import/preview', 409, async () => {
    await click('[data-testid=import-preview]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=import-error]"))');
    assert.match(await browser.evaluate('document.querySelector("[data-testid=import-error]").textContent'), /Cycle ID already exists/); checks++;
  });
  await uploadPlan(candidateText);
  await click('[data-testid=import-preview]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=import-comparison]"))');
  const importRow = activeBeforeReview.workouts.find(row => row.bucket === 'main');
  const staleSave = await fetch(`${archiveBase}/api/log`, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({cycle_id:activeBeforeReview.meta.planId,week:importRow.week,day:importRow.day,seq:importRow.seq,load:102.5,sets:2,reps:1,rpe:9,note:'Saved after import preview'}) });
  equal(staleSave.status, 200, 'concurrent valid log creates stale preview');
  await input('[data-testid=import-confirm-check]', true);
  await expectedImportRejection('/api/plan/import/confirm', 409, async () => {
    await click('[data-testid=import-confirm]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=import-error]"))');
    equal(await browser.evaluate('Boolean(document.querySelector("[data-testid=import-comparison]"))'), false, 'stale confirmation clears preview');
  });
  await click('[data-testid=import-preview]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=import-comparison]"))');
  await input('[data-testid=import-confirm-check]', true);
  await click('[data-testid=import-confirm]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=import-success]"))');
  equal((await archiveApi('/api/cycle')).active_cycle_id, candidatePlan.meta.planId, 'explicit confirm activates new cycle');
  equal(await archiveApi('/api/plan'), candidatePlan, 'new plan exactly matches uploaded prescriptions');
  equal((await archiveApi('/api/log')).logs, {}, 'new cycle never inherits old logs');
  const frozenReview = await archiveApi(`/api/review?cycle_id=${encodeURIComponent(activeBeforeReview.meta.planId)}`);
  equal(frozenReview.cycle.status, 'archived', 'old review frozen as archive');
  equal(frozenReview.logs[0].load, 102.5, 'archive includes last pre-confirm actual save');
  equal(frozenReview.prescription_versions[0].plan, activeBeforeReview, 'original prescription preserved');
  await click('[data-testid=import-open-plan]');
  await browser.waitFor('document.querySelector("main")?.getAttribute("aria-busy") === "false" && Boolean(document.querySelector(".plan-metrics"))');
  equal((await archiveApi('/api/plan')).meta.planId, candidatePlan.meta.planId, 'open reload reads new active plan');
  await load(archiveBase, `/archive/${encodeURIComponent(activeBeforeReview.meta.planId)}`);
  await browser.waitFor('Boolean(document.querySelector("[data-testid=review-view]"))');
  equal(await browser.evaluate('document.querySelector("[data-testid=review-status]").textContent'), 'READ-ONLY', 'old plan is readable after real import');
  equal(await browser.evaluate('document.querySelectorAll(".record-form, .exercise-editor").length'), 0, 'old cycle never mounts editors after import');
  console.log('PASS atomic import: strict errors, preview/cancel, explicit confirm, stale logs, network failure, complete readonly archive, new-cycle reload and four-width/two-theme controls');
  const questionnaireCycle = candidatePlan.meta.planId;
  const qGet = async () => (await archiveApi(`/api/questionnaire?cycle_id=${encodeURIComponent(questionnaireCycle)}`));
  const qPut = (status, payload) => fetch(`${archiveBase}/api/questionnaire`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cycle_id: questionnaireCycle, status, payload }) });
  const qField = (field, value) => input(`[data-field=${JSON.stringify(field)}]`, value);
  const qNext = () => click('[data-testid=questionnaire-next]');
  const stripQuestionnaireRejections = label => {
    const expected = entry => entry.source === 'network' && entry.url === `${archiveBase}/api/questionnaire` && entry.text.includes('422');
    equal(browser.errors.filter(entry => !expected(entry)), [], `${label}: only expected questionnaire 422 rejections`);
    for (let index = browser.errors.length - 1; index >= 0; index--) if (expected(browser.errors[index])) browser.errors.splice(index, 1);
  };
  async function fillCompetitionDraft() {
    await click('[data-field="goal.type"][value="competition"]');
    await qNext();
    await qField('schedule.startDate', '2026-11-16');
    await qField('schedule.trainingDaysPerWeek', '4');
    await qField('schedule.sessionMinutes', '90');
    await qField('schedule.competitionDate', '2027-03-20');
    equal(await browser.evaluate('document.querySelector("[data-field=\\"schedule.testDates\\"]").textContent'), '2027-03-20', 'competition test date locks to the competition date');
    await qNext();
    await qField('personal.age', '30');
    await qField('personal.sex', 'male');
    await qField('personal.heightCm', '175');
    await qField('personal.bodyweightKg', '85');
    await qField('personal.trainingYears', '5');
    await qField('personal.equipment', 'classic');
    await qField('personal.activityLevel', 'Desk job, walks daily');
    await qNext();
    await qField('level.sbd1rm.squat', '180');
    await qField('level.sbd1rm.bench', '120');
    await qField('level.sbd1rm.deadlift', '220');
    await qField('level.oneRmSource', 'measured');
    await qField('level.recentPrs', 'Squat 175x1 last month');
    await qField('level.variationPrs.S.Main|low-bar squat', '170');
    await qField('level.fiveKm.timeSeconds', '1500');
    await qField('level.fiveKm.date', '2026-10-01');
    await qNext();
    await input('[data-field="limits.squat"]', true);
    await input('[data-field="limits.weakMuscles"]', true);
    await qField('limits.technique', 'Knees cave at heavy squat');
    await qNext();
    await qField('recovery.sleepHours', '7.5');
    await qField('recovery.sleepQuality', '4');
    await qField('recovery.stressLevel', '2');
    await qField('recovery.bodyFatPercent', '15');
    await click('.tri[data-field="recovery.proteinSufficient"] .choice-row button');
    await click('.tri[data-field="recovery.caloriesSufficient"] .choice-row button');
    await qNext();
    await qField('outlook.targetBodyweightKg', '84');
    await qField('outlook.weightDirection', 'cut');
    await qField('outlook.effortLevel', 'moderate');
    await qField('outlook.riskPreference', 'steady');
    await qField('outlook.targets.squat', '190');
    await qField('outlook.targets.bench', '125');
    await qField('outlook.targets.deadlift', '230');
    await qField('outlook.targets.total', '545');
    await qField('outlook.targetTotalKg', '545');
    await qField('outlook.fiveKmTargetSeconds', '1440');
    await qField('outlook.competitionName', 'City Open');
    await qField('outlook.weightClass', '93');
    await qField('outlook.consistencyGoal', 'Four sessions every week');
    await input('[data-field="outlook.sbdFocus"]', true);
    await input('[data-field="outlook.keepMovements"]', true);
    await browser.evaluate('document.querySelectorAll("[data-field=\\"outlook.avoidMovements\\"]")[1].click()');
    await qField('notes', 'Shoulder history: keep bench volume moderate');
  }
  await load(archiveBase, '/questionnaire');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-progress]"))');
  equal(await browser.evaluate('Boolean(document.querySelector("a[href=\\"/questionnaire\\"]"))'), true, 'OUTLOOK navigation link exists');
  equal((await qGet()).status, 'empty', 'new cycle starts with an explicit empty skeleton');
  equal(await browser.evaluate('document.querySelector("[data-testid=questionnaire-progress]").textContent'), 'Step 1 of 7 · Goal', 'wizard starts at step 1');
  await fillCompetitionDraft();
  await click('[data-testid=questionnaire-save-draft]');
  await browser.waitFor('document.querySelector("[data-testid=questionnaire-view]").textContent.includes("Draft saved")');
  const draftRecord = await qGet();
  equal(draftRecord.status, 'draft', 'explicit save stores a draft');
  equal(draftRecord.payload.personal.age, 30, 'numeric fields round-trip as numbers, not strings');
  equal(draftRecord.payload.schedule.testDates, ['2027-03-20'], 'competition locks test dates to the competition date');
  equal(draftRecord.payload.outlook.testGroups, ['sbd'], 'competition locks test groups to SBD');
  equal(draftRecord.payload.recovery.proteinSufficient, true, 'tri-state yes persists as boolean true');
  equal(draftRecord.payload.level.variationPrs['S.Main|low-bar squat'], 170, 'variation PR keyed by exact movement id');
  await click('[data-testid=questionnaire-complete]');
  await browser.waitFor('Boolean(document.querySelector(".completed[data-testid=questionnaire-summary]"))');
  equal((await qGet()).status, 'complete', 'complete persists server-side');
  const completePayload = (await qGet()).payload;
  const reviewWithQuestionnaire = await archiveApi(`/api/review?cycle_id=${encodeURIComponent(questionnaireCycle)}`);
  equal(reviewWithQuestionnaire.questionnaire.status, 'complete', 'review source carries the completed questionnaire');
  await click('[data-testid=questionnaire-new-draft]');
  await browser.waitFor('Boolean(document.querySelector(".confirm-box"))');
  await click('.confirm-box [data-testid=questionnaire-new-draft]');
  await browser.waitFor('document.querySelector("[data-testid=questionnaire-progress]")?.textContent.startsWith("Step 1")');
  equal((await qGet()).status, 'draft', 'confirmed new draft replaces the completed record');
  const skeletonPayload = (await qGet()).payload;
  await click('[data-field="goal.type"][value="competition"]');
  for (let n = 0; n < 6; n++) await qNext();
  await click('[data-testid=questionnaire-complete]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-error]"))');
  const missingText = await browser.evaluate('document.querySelector("[data-testid=questionnaire-error]").textContent');
  assert.match(missingText, /personal\.age/); checks++;
  assert.match(missingText, /schedule\.startDate/); checks++;
  equal(await browser.evaluate('document.querySelectorAll("[data-testid=questionnaire-error] .error-list li").length > 0'), true, 'incomplete completion lists field-level issues');
  equal(await browser.evaluate('[...document.querySelectorAll("[data-testid=questionnaire-error] button")].some(b => b.textContent.includes("Go to step"))'), true, 'error panel offers jump-to-step');
  stripQuestionnaireRejections('incomplete completion');
  await browser.evaluate('[...document.querySelectorAll("[data-testid=questionnaire-error] button")].find(b => b.textContent.includes("step 3")).click()');
  await qField('personal.age', '9');
  await click('[data-testid=questionnaire-save-draft]');
  await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-error]"))');
  assert.match(await browser.evaluate('document.querySelector("[data-testid=questionnaire-error]").textContent'), /personal\.age/); checks++;
  equal(await browser.evaluate('document.querySelector("[data-field=\\"personal.age\\"]").value'), '9', 'rejected save keeps the entered value');
  stripQuestionnaireRejections('invalid age');
  await blockedTrainingRequests(['/api/questionnaire'], async () => {
    await click('[data-testid=questionnaire-save-draft]');
    await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-error]"))');
    equal(await browser.evaluate('document.querySelector("[data-field=\\"personal.age\\"]").value'), '9', 'network failure keeps inputs for retry');
  }, 'questionnaire save network failure', archiveBase);
  const archivedSave = await fetch(`${archiveBase}/api/questionnaire`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cycle_id: activeBeforeReview.meta.planId, status: 'draft', payload: {} }) });
  equal(archivedSave.status, 409, 'archived cycle questionnaire is read-only');
  for (const width of [320, 360, 390, 412]) {
    await browser.viewport(width);
    for (const theme of ['light', 'dark']) {
      await browser.evaluate(`localStorage.setItem('roastraw-theme', '${theme}')`);
      equal((await qPut('complete', completePayload)).status, 200, 'responsive audit restores completed record');
      await load(archiveBase, '/questionnaire');
      await browser.waitFor('Boolean(document.querySelector(".completed[data-testid=questionnaire-summary]"))');
      await noOverflow(`questionnaire complete ${width} ${theme}`);
      await screenshot(`questionnaire-complete-${width}-${theme}`);
      equal((await qPut('draft', completePayload)).status, 200, 'responsive audit restores filled draft');
      await load(archiveBase, '/questionnaire');
      await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-progress]"))');
      for (let n = 0; n < 6; n++) await qNext();
      await noOverflow(`questionnaire step7 ${width} ${theme}`);
      equal(await browser.evaluate('[...document.querySelectorAll("[data-testid=questionnaire-view] button, [data-testid=questionnaire-view] select, [data-testid=questionnaire-view] textarea, [data-testid=questionnaire-view] label, [data-testid=questionnaire-view] input:not([type=checkbox]):not([type=radio])")].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.width<44||r.height<44)}).map(e=>e.tagName)'), [], `questionnaire controls meet 44px ${width} ${theme}`);
      equal(await browser.evaluate('(()=>{const y=scrollY;scrollTo(innerWidth,y);const r=scrollX;scrollTo(-innerWidth,y);const l=scrollX;scrollTo(0,y);return[r,l]})()'), [0, 0], `questionnaire no actual horizontal scroll ${width} ${theme}`);
      await screenshot(`questionnaire-step7-${width}-${theme}`);
      equal((await qPut('draft', skeletonPayload)).status, 200, 'responsive audit restores empty draft');
      await load(archiveBase, '/questionnaire');
      await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-progress]"))');
      for (let n = 0; n < 6; n++) await qNext();
      await click('[data-testid=questionnaire-complete]');
      await browser.waitFor('Boolean(document.querySelector("[data-testid=questionnaire-error]"))');
      await noOverflow(`questionnaire error ${width} ${theme}`);
      await screenshot(`questionnaire-error-${width}-${theme}`);
    }
  }
  stripQuestionnaireRejections('responsive audit');
  equal((await qPut('complete', completePayload)).status, 200, 'final state restores the completed questionnaire');
  console.log('PASS questionnaire: seven-step golden path, competition locks, draft/complete/new-draft, field-level 422 with jump-to-step, kept inputs on failure, archived read-only, four-width/two-theme states');
  equal(browser.errors, [], 'no browser runtime or console errors');
  console.log(`PASS browser.mjs: ${checks} assertions; ${screenshots} delivery screenshots; CDP device metrics at 320/360/390/412`);
} finally {
  if (server) await server.stop();
  await browser.close();
}
