const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { readFileSync, existsSync } = require('node:fs');
const { rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { resolve, join } = require('node:path');

const root = resolve(__dirname, '..');
const localPython = join(root, 'server', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.RR_PYTHON || (existsSync(localPython) ? localPython : 'python');
const sabotage = process.argv.includes('--sabotage-child');
let checks = 0;
const json = path => JSON.parse(readFileSync(join(root, path), 'utf8').replace(/^\uFEFF/, ''));
function runPython(code) {
  const result = spawnSync(python, ['-c', code], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' }, maxBuffer: 20 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr || result.error?.message || 'Python execution failed');
  return JSON.parse(result.stdout);
}
function same(actual, expected, label) {
  assert.deepEqual(actual, expected, label);
  checks++;
}
function near(actual, expected, epsilon, label) {
  assert.ok(Number.isFinite(actual) && Math.abs(actual - expected) <= epsilon, `${label}: ${actual} != ${expected} (tolerance ${epsilon})`);
  checks++;
}
function fixtureCheck() {
  const cap = json('Ref/02_Stats/capData.json');
  const mm = json('Ref/02_Stats/mmData.json');
  const analysis = runPython(`import json\nfrom server.app.stats import engine\np=json.load(open('data/plan.json',encoding='utf-8'))\n${sabotage ? "next(m for m in engine.library()['movements'] if m['name_en']=='Mid-grip Bench')['coef6']['chest'] += 0.1\n" : ''}print(json.dumps(engine.analyze(p)))`);
  same(analysis.weeks, cap.weeks, 'fixture week count');
  same(analysis.deload, cap.deload, 'fixture deload weeks');
  same(analysis.test, [cap.test], 'fixture test week');
  same(analysis.perWeek.map(w => w.total), cap.total, 'fixture weekly totals');
  same(analysis.cycle.total, cap.totalAll, 'fixture cycle sets');
  same(analysis.cycle.sessions, 49, 'fixture sessions');
  same(analysis.cycle.tonnageKg, 139568, 'fixture tonnage kg');
  same(Number((analysis.cycle.tonnageKg / 1000).toFixed(1)), 139.6, 'fixture tonnage display t');
  same(analysis.unresolved, [], 'no unresolved movements');
  const roleKeys = { R_MAIN: 'main', R_VAR: 'sbdVar', R_ACC: 'accessory' };
  for (const role of cap.roles) same(analysis.perWeek.map(w => w.roles[roleKeys[role.k]]), role.m, `fixture role ${role.k}`);
  same(analysis.perWeek.map(w => w.roles.nonSbdVar), Array(cap.weeks).fill(0), 'fixture non-SBD variations');
  let groupDiff = 0;
  let leafDiff = 0;
  for (const item of cap.items) {
    if (item.kind === 'lift') {
      same(analysis.perWeek.map(w => w.lifts[item.k].main), item.m, `fixture ${item.k} main`);
      same(analysis.perWeek.map(w => w.lifts[item.k].var), item.v, `fixture ${item.k} variation`);
    } else {
      same(analysis.perWeek.map(w => w.groups[item.k].d), item.d, `fixture ${item.k} direct`);
      analysis.perWeek.forEach((w, index) => {
        groupDiff = Math.max(groupDiff, Math.abs(w.groups[item.k].w - item.w[index]));
        near(w.groups[item.k].w, item.w[index], 1e-9, `fixture weekly ${item.k} W${w.n}`);
      });
    }
  }
  same(analysis.groups.map(g => analysis.cycle.groups[g].w), [148.8, 138.9, 345.4, 289.4, 144.8, 170.2], 'fixture cycle group weighted half-up');
  same(analysis.groups.map(g => analysis.cycle.groups[g].d), [162, 97, 218, 201, 0, 54], 'fixture cycle group direct');
  same(analysis.leafOrder, mm.order, 'fixture leaf order');
  analysis.perWeek.forEach(w => mm.order.forEach((leaf, index) => {
    same(w.leaves[leaf].d, mm.weeks[w.n].d[index], `fixture leaf direct W${w.n} ${leaf}`);
    leafDiff = Math.max(leafDiff, Math.abs(w.leaves[leaf].w - mm.weeks[w.n].w[index]));
    near(w.leaves[leaf].w, mm.weeks[w.n].w[index], 0.1 + 1e-12, `fixture leaf weighted W${w.n} ${leaf}`);
  }));
  same(Object.values(analysis.completion.actual), [0, 0, 0, 0], 'unlogged plan is not completed');
  console.log(`PASS fixture: ${checks} checks; 13 weeks / 49 sessions / 732 sets / 139568.0 kg`);
  console.log(`PASS precision: six-group weekly max diff=${groupDiff.toExponential(3)} (<=1e-9); leaf max diff=${leafDiff.toFixed(10)} (<=0.1)`);
}
function libraryCheck() {
  const lib = json('data/movements.json');
  same(lib.movements.length, 261, 'movement count');
  same(new Set(lib.movements.map(m => m.id)).size, 261, 'category-distinct movement ids');
  same(lib.movements.filter(m => !m.plan_allowed).map(m => m.id).sort(), ['B.Rotator|sleeper stretch', 'Unmapped|unmapped'], 'source entries without coefficients stay excluded');
  const fields = ['id', 'name_en', 'category', 'lift', 'role', 'level', 'pattern', 'equipment', 'group', 'coef16', 'tier', 'tags', 'plan_allowed', 'contraindications', 'source'];
  for (const movement of lib.movements) {
    fields.forEach(field => same(Object.hasOwn(movement, field), true, `movement field ${movement.id}.${field}`));
    if (movement.plan_allowed) {
      same(Object.keys(movement.coef16).sort(), [...lib.leaf_order].sort(), `16 leaves ${movement.id}`);
      for (const [group, leaves] of Object.entries(lib.group_leaves)) near(movement.coef6[group], Math.max(...leaves.map(leaf => movement.coef16[leaf])), 1e-12, `max-fold ${movement.id}.${group}`);
    } else same(movement.coef16, null, `unknown coefficients remain null ${movement.id}`);
  }
  console.log(`PASS movement library: 261 unique ids; ${lib.movements.filter(m => !m.plan_allowed).length} excluded; explicit 16-leaf vectors and max-fold groups`);
}
function syntheticCheck() {
  for (const count of [8, 17, 21]) {
    const result = runPython(`import json\nfrom server.tools.synth_plan import build\nfrom server.app.validation import validate_plan\nfrom server.app.stats.engine import analyze\np=build(${count})\nvalidate_plan(p)\na=analyze(p)\nprint(json.dumps({'plan':p,'analysis':a}))`);
    const { plan, analysis } = result;
    same(plan.meta.weeks, count, `synthesis ${count} meta`);
    same(plan.weeks.length, count, `synthesis ${count} calendar`);
    same(analysis.perWeek.length, count, `synthesis ${count} statistics`);
    same(plan.weeks.map(w => w.n), Array.from({ length: count }, (_, i) => i + 1), `synthesis ${count} sequential weeks`);
    same(plan.blocks.reduce((n, b) => n + b.workWeeks + b.deloadWeeks, 0), count, `synthesis ${count} blocks`);
    same(analysis.cycle.total, plan.workouts.reduce((n, row) => n + row.sets, 0), `synthesis ${count} sets`);
    same(analysis.cycle.sessions, new Set(plan.workouts.map(row => `${row.week}|${row.day}`)).size, `synthesis ${count} sessions`);
    same(analysis.unresolved, [], `synthesis ${count} coefficient resolution`);
    console.log(`PASS synthesis: ${count} weeks / ${analysis.cycle.sessions} sessions / ${analysis.cycle.total} sets; schema, calendar, blocks and stats agree`);
  }
}
async function shareCheck() {
  const { solvePlates, dayShareData } = await import('../web/src/share.js');
  const kg = plates => plates.reduce((sum, plate) => sum + plate.kg, 0);
  same(solvePlates(155).map(plate => plate.kg), [25, 25, 15], 'share plates for 155 kg include competition collars');
  near(kg(solvePlates(155)) * 2 + 25, 155, 1e-9, 'share plate sum reconstructs total with bar and collars');
  same(solvePlates(140).map(plate => plate.kg), [25, 25, 5, 2.5], 'share plates reach micro plates');
  same(solvePlates(25), [], 'bar plus collars alone draws no plates');
  same(solvePlates(20), [], 'bar alone draws no plates');
  const plan = { workouts: [
    { date: '2026-11-16', week: 1, day: 'A', seq: 1, bucket: 'main', lift: 'S', nameEn: 'High-bar Squat', sets: 3 },
    { date: '2026-11-16', week: 1, day: 'A', seq: 2, bucket: 'main', lift: 'B', nameEn: 'Mid-grip Bench', sets: 3 },
    { date: '2026-11-16', week: 1, day: 'A', seq: 3, bucket: 'accessory', lift: null, nameEn: 'Side Plank', sets: 2 },
    { date: '2026-11-17', week: 1, day: 'B', seq: 1, bucket: 'main', lift: 'D', nameEn: 'Deadlift', sets: 2 },
  ] };
  const logs = {
    '1|A|1': { load: 140, sets: 3, reps: 3, rpe: 8 },
    '1|A|2': { load: 100, sets: 3, reps: 3, rpe: 8 },
    '1|A|3': { load: null, sets: 2, reps: 30, rpe: null },
  };
  const data = dayShareData(plan, logs, '2026-11-16');
  same(data.topSet, { name: 'Mid-grip Bench', load: 100, reps: 3, rpe: 8 }, 'share top set is the final logged main lift');
  near(data.volume, 140 * 9 + 100 * 9, 1e-9, 'null accessory load contributes zero volume, not NaN');
  same(data.byLift, [['S', 1260], ['B', 900], ['OTHER', 0]], 'volume by lift sorts desc and keeps null-load group');
  same([data.doneSets, data.plannedSets], [8, 8], 'share counts logged and planned sets');
  const empty = dayShareData(plan, logs, '2026-11-17');
  same([empty.volume, empty.topSet, empty.loggedCount], [null, null, 0], 'unlogged date is an explicit empty state');
  console.log('PASS share math: collar-inclusive plate solve, final-main top set, null-load volume safety, empty state');
}
function landingFactsCheck() {
  const facts = json('web/src/landing-facts.json');
  const plan = json('data/plan.json');
  const tmp = join(tmpdir(), `landing-facts-${process.pid}.json`);
  const generated = spawnSync(python, ['server/tools/landing_facts.py', '--out', tmp], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  assert.equal(generated.status, 0, generated.stderr || 'landing facts generator failed');
  same(readFileSync(tmp, 'utf8'), readFileSync(join(root, 'web/src/landing-facts.json'), 'utf8'), 'landing facts regenerate byte-for-byte');
  rmSync(tmp, { force: true });
  const rows = plan.workouts.filter(row => row.week === facts.week && row.day === facts.day);
  assert.ok(rows.length > 0, 'landing facts name a real sample day');
  checks++;
  same(rows[0].date, facts.date, 'landing facts date comes from the sample day');
  same(rows.reduce((sum, row) => sum + (row.tonnageKg || 0), 0), facts.day_total_kg, 'day_total_kg recomputed from plan rows (no warm-ups)');
  same(rows.reduce((sum, row) => sum + row.sets, 0), facts.set_count, 'set_count recomputed from plan rows');
  same(facts.cycle_total_kg, plan.meta.cycleTonnageKg, 'cycle_total_kg equals meta.cycleTonnageKg');
  assert.notEqual(facts.day_total_kg, facts.cycle_total_kg, 'day tonnage and cycle tonnage are distinct fields');
  checks++;
  const anchors = Object.values(plan.meta.anchors || {}).filter(entry => entry.unit === 'kg').map(entry => entry.movement);
  facts.lifts.forEach(lift => {
    const candidates = rows.filter(row => row.bucket === 'main' && row.lift === lift.lift && row.loadKg !== null);
    assert.ok(candidates.some(row => row.loadKg === lift.top_kg && row.movement === lift.movement), `landing lift ${lift.lift} top load exists on the day`);
    checks++;
    same(Object.hasOwn(lift, 'pct'), anchors.includes(lift.movement), `landing lift ${lift.lift} pct only with a same-source anchor`);
  });
  assert.ok(facts.lifts.length > 0, 'landing facts carry main lifts');
  checks++;
  console.log(`PASS landing facts: byte-identical regeneration, day ${facts.day_total_kg} kg / ${facts.set_count} sets recomputed, cycle ${facts.cycle_total_kg} kg from meta`);
}
function planCalendarCheck() {
  const plan = json('data/plan.json');
  const meta = plan.meta;
  const start = meta.startDate;
  // Policy anchor: the owner moved the cycle to 2026-11-23 on 2026-11-15.
  same(start, '2026-11-23', 'plan start date is the approved calendar');
  same(meta.planId, `rpl-raw-${start}`, 'planId is derived from the start date');
  const addDays = (iso, days) => new Date(Date.parse(`${iso}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10);
  same(meta.endDate, addDays(start, meta.weeks * 7 - 1), 'end date is derived from start + weeks');
  same(plan.days.map(day => day.weekdayOffset), [0, 2, 4, 5], 'day offsets are the fixed Monday-first template');
  const offsets = Object.fromEntries(plan.days.map(day => [day.id, day.weekdayOffset]));
  plan.workouts.forEach(row => {
    same(row.date, addDays(start, (row.week - 1) * 7 + offsets[row.day]), `W${row.week} ${row.day} date follows the calendar`);
  });
  const testWeek = plan.weeks.find(week => week.kind === 'test');
  assert.ok(testWeek, 'plan has a test week');
  checks++;
  const testDate = plan.testPlan.dates.sbd;
  const inTestWeek = Date.parse(`${testDate}T00:00:00Z`) >= Date.parse(`${testWeek.dateStart}T00:00:00Z`) && Date.parse(`${testDate}T00:00:00Z`) <= Date.parse(`${testWeek.dateEnd}T00:00:00Z`);
  assert.ok(inTestWeek, `test date ${testDate} falls inside test week W${testWeek.n}`);
  checks++;
  const motto = meta.profile.motto;
  assert.equal(motto.match(/TEST (\d{4}-\d{2}-\d{2})/)[1], testDate, 'motto test date is filled from the calendar');
  checks++;
  const daysToTest = Math.round((Date.parse(`${testDate}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000);
  assert.equal(motto.match(/(\d+\.\d+W) \((\d+) days to test\)/)[2], String(daysToTest), 'motto counts days to test from the calendar');
  checks++;
  console.log(`PASS plan calendar: start ${start}, end ${meta.endDate}, ${plan.workouts.length} dated rows, test ${testDate} in W${testWeek.n}`);
}
(async () => {
try {
  fixtureCheck();
  if (!sabotage) {
    libraryCheck();
    syntheticCheck();
    await shareCheck();
    landingFactsCheck();
    planCalendarCheck();
    const drift = spawnSync(python, ['server/tools/export_membership.py', '--check'], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
    assert.equal(drift.status, 0, `web/src/membership.json drifted from server/app/membership.py: ${drift.stdout}${drift.stderr}`);
    console.log('PASS membership table: web/src/membership.json matches the server capability matrix');
    const unit = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8', RR_ACCESS_PASSWORD: '', RR_ALLOW_OPEN_FIXTURE: '1', DEEPSEEK_API_KEY: '' }, timeout: 600000, maxBuffer: 5 * 1024 * 1024 });
    process.stdout.write(unit.stdout || '');
    process.stdout.write(unit.stderr || '');
    assert.equal(unit.status, 0, 'Python import/API/calendar/statistics regression failed');
    const negative = spawnSync(process.execPath, [__filename, '--sabotage-child'], { cwd: root, encoding: 'utf8', timeout: 30000 });
    assert.equal(negative.status, 1, 'Sabotaged engine must fail with exit code 1');
    assert.match(negative.stderr, /FAIL: fixture weekly chest W1/, 'Sabotage must hit a real fixture assertion, not crash elsewhere');
    console.log(`PASS sabotage: bench chest coefficient +0.1 => child exit ${negative.status}`);
    console.log(negative.stderr.trim());
    console.log(`PASS verify.js: ${checks} fixture/library/synthesis checks plus Python regression; no tolerances weakened`);
  }
} catch (error) {
  console.error(`FAIL: ${error.message}`);
  process.exitCode = 1;
}
})();
