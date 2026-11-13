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
  equal(browser.errors, [], 'no browser runtime or console errors');
  console.log(`PASS browser.mjs: ${checks} assertions; ${screenshots} delivery screenshots; CDP device metrics at 320/360/390/412`);
} finally {
  if (server) await server.stop();
  await browser.close();
}
