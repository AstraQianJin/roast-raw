const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { readFileSync: rawReadFileSync, existsSync } = require('node:fs');
const { rmSync } = require('node:fs');
// Checks read the same sources repeatedly; the gate holds one copy per file for its run.
const fileCache = new Map();
function readFileSync(path, encoding) {
  if (encoding !== 'utf8') return rawReadFileSync(path, encoding);
  if (!fileCache.has(path)) fileCache.set(path, rawReadFileSync(path, 'utf8'));
  return fileCache.get(path);
}
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
// 0.33 plate arithmetic. Every expectation below is worked out by hand from the
// bar and collar numbers, not read back from the solver under test.
async function plateCheck() {
  const { solveLoad } = await import('../web/src/plate-load.js');
  const sideKg = side => side.plates.map(plate => plate.kg);
  // 110.5 − 20 bar = 90.5 → 45.25 per side = 25 + 20 + 0.25.
  const symmetric = solveLoad(110.5, 20, 0);
  same(sideKg(symmetric.sideA), [25, 20, 0.25], 'symmetric side A for 110.5 kg without collars');
  same(sideKg(symmetric.sideB), [25, 20, 0.25], 'symmetric side B matches side A');
  assert.equal(symmetric.asymmetric, false, 'equal loads are not flagged asymmetric');
  checks++;
  same(symmetric.microUsed, [0.25], 'micro plate list names the 0.25 kg plate');
  // 110.5 − 20 − 5 = 85.5 → 42.75 per side = 25 + 15 + 2.5 + 0.25.
  const collared = solveLoad(110.5, 20, 5);
  same(sideKg(collared.sideA), [25, 15, 2.5, 0.25], 'collar-on side A for 110.5 kg');
  near(collared.plateTotal, 85.5, 1e-9, 'collar pair is subtracted from the plate total');
  // 22.75 − 20 = 2.75; 1.375 per side cannot be built, so one side takes 1.5 and
  // the other 1.25. Both sides still sum to 2.75 with no shortfall.
  const split = solveLoad(22.75, 20, 0);
  assert.equal(split.asymmetric, true, 'a half that cannot be built is flagged asymmetric');
  checks++;
  near(split.sideA.loaded, 1.5, 1e-9, 'heavier side carries 1.5 kg');
  near(split.sideB.loaded, 1.25, 1e-9, 'lighter side carries 1.25 kg');
  near(split.sideA.loaded + split.sideB.loaded, 2.75, 1e-9, 'single-side plates still add up to the load');
  near(split.shortKg, 0, 1e-9, 'single-side split leaves nothing short');
  // 20.1 − 20 = 0.1, below the smallest plate: report the shortfall, never round it away.
  const short = solveLoad(20.1, 20, 0);
  near(short.shortKg, 0.1, 1e-9, 'an unbuildable remainder is reported');
  same(short.sideA.plates.map(plate => plate.kg), [], 'nothing smaller than 0.25 kg is invented');
  // A load at or under the bar has no plates on either side.
  same(sideKg(solveLoad(20, 20, 0).sideA), [], 'bar alone carries no plates');
  same(sideKg(solveLoad(20, 20, 5).sideA), [], 'bar plus collars is already over the load');
  console.log('PASS plates: symmetric, collar-on, single-side and shortfall arithmetic agree');
}

async function plateParityCheck() {
  // The UI cabinet and the share canvas each solve plates. They must agree on every
  // symmetric, fully buildable load; the UI is allowed to split an odd half, the canvas
  // is not, so asymmetric or short loads are out of scope by definition.
  const { solveLoad } = await import('../web/src/plate-load.js');
  const { solvePlates } = await import('../web/src/share.js');
  const mismatches = [];
  let compared = 0;
  for (let total = 20; total <= 320; total += 0.5) {
    for (const collar of [0, 5]) {
      const ui = solveLoad(total, 20, collar);
      if (ui.asymmetric || ui.shortKg > 0) continue;
      const side = ui.sideA.plates.map(plate => plate.kg);
      const share = solvePlates(total, 20, collar).map(plate => plate.kg);
      compared++;
      if (JSON.stringify(side) !== JSON.stringify(share)) mismatches.push({ total, collar, side, share });
    }
  }
  assert.equal(mismatches.length, 0, `plate solutions drifted between the UI and the share card: ${JSON.stringify(mismatches.slice(0, 3))}`);
  assert.ok(compared > 500, `the parity sweep must cover the working range, compared ${compared}`);
  checks += 2;
  console.log(`PASS plate parity: ${compared} symmetric loads agree between the cabinet and the share canvas`);
}

async function shareCheck() {
  const { solvePlates, dayShareData } = await import('../web/src/share.js');
  const kg = plates => plates.reduce((sum, plate) => sum + plate.kg, 0);
  // The collar switch became a venue setting in 0.33: the default is off, and the
  // same total is solved twice so both policies stay pinned to their own arithmetic.
  // 155 − 20 bar − 5 collars = 130 → 65 per side = 25+25+15.
  same(solvePlates(155, 20, 5).map(plate => plate.kg), [25, 25, 15], 'collar-on share plates for 155 kg');
  near(kg(solvePlates(155, 20, 5)) * 2 + 25, 155, 1e-9, 'collar-on plate sum reconstructs total');
  // 155 − 20 = 135 → 67.5 per side = 25+25+15+2.5.
  same(solvePlates(155, 20, 0).map(plate => plate.kg), [25, 25, 15, 2.5], 'collar-off share plates for 155 kg');
  same(solvePlates(140, 20, 5).map(plate => plate.kg), [25, 25, 5, 2.5], 'share plates reach micro plates');
  same(solvePlates(25, 20, 5), [], 'bar plus collars alone draws no plates');
  same(solvePlates(20, 20, 0), [], 'bar alone draws no plates');
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
function testPlanCheck() {
  // The test battery is its own layer: nine items on the SBD test day, groups that
  // cannot be swapped, and a load/run split the server enforces, checked here by hand.
  const plan = json('data/plan.json');
  const testPlan = plan.testPlan;
  const sbd = testPlan.dates.sbd;
  same(sbd, plan.meta.profile.motto.match(/TEST (\d{4}-\d{2}-\d{2})/)[1], 'test battery sits on the evidenced SBD date');
  assert.deepEqual(Object.keys(testPlan.dates).sort(), ['fivekm', 'sbd', 'tier1', 'tier2'], 'every group declares a date');
  ['tier1', 'tier2', 'fivekm'].forEach(group => {
    same(testPlan.dates[group], sbd, `${group} sits on the SBD date, not a second test day`);
  });
  const items = testPlan.items;
  same(items.length, 9, 'four tier-1 variations, four tier-2 variations and the 5 km');
  same(items.filter(item => item.group === 'tier1').length, 4, 'tier-1 count');
  same(items.filter(item => item.group === 'tier2').length, 4, 'tier-2 count');
  same(items.filter(item => item.group === 'fivekm').length, 1, '5 km count');
  const ids = items.map(item => item.id);
  same(ids.length, new Set(ids).size, 'item ids are unique');
  const runs = items.filter(item => item.kind === 'run');
  same(runs.map(item => item.id), ['five_km'], 'only the 5 km is a run');
  assert.ok(ids.every(id => /^[a-z0-9_]+$/.test(id)), 'item ids are lowercase snake case');
  assert.deepEqual(testPlan.tests, ['fivekm', 'sbd', 'tier1', 'tier2'], 'declared groups are the ones with dates');
  // Every lifting item names a load the server will accept on a 0.5 kg step.
  items.filter(item => item.kind !== 'run').forEach(item => {
    assert.match(item.kind, /load|loadBodyweight/, `${item.id} declares a load kind`);
  });
  const schema = json('data/schema/RPL-Raw-v1.json');
  same(schema.$defs.testItem.properties.kind.enum, ['load', 'loadBodyweight', 'run'], 'schema load kinds');
  same(schema.properties.testPlan.properties.tests.items.enum, ['sbd', 'tier1', 'tier2', 'fivekm'], 'schema group names');
  console.log(`PASS test battery: 9 items on ${sbd}, groups ${testPlan.tests.join('/')}`);
}
function completionCheck() {
  // R5 policy (0.35): the denominator is only the prescribed sets whose session has
  // arrived. The expected numbers below are summed here from plan.json, not read
  // back out of the engine under test.
  const plan = json('data/plan.json');
  const asOf = '2026-12-31';
  const classes = { main: 'main', sbdVar: 'var', nonSbdVar: 'var', accessory: 'acc' };
  const planned = { main: 0, var: 0, acc: 0 };
  const sessionDates = new Map();
  plan.workouts.forEach(row => {
    if (!sessionDates.has(`${row.week}|${row.day}`)) sessionDates.set(`${row.week}|${row.day}`, row.date);
    if (row.date <= asOf) planned[classes[row.bucket]] += row.sets;
  });
  const elapsedSessions = [...sessionDates.values()].filter(date => date <= asOf).length;
  const result = runPython(`import json
from server.app.stats import engine
p = json.load(open('data/plan.json', encoding='utf-8'))
c = engine.analyze(p, None, 'plan', today='${asOf}')['completion']
print(json.dumps({'classes': c['classes'], 'planned': c['planned'], 'actual': c['actual'],
                  'credited': c['credited'], 'extra': c['extra'], 'sessions': c['sessions'],
                  'policy': c['policy'], 'asOf': c['asOf']}))`);
  assert.match(result.policy, /^R5/, 'completion names the R5 policy it follows');
  checks++;
  same(result.asOf, asOf, 'completion honours the injected as-of date');
  ['main', 'var', 'acc'].forEach(key => {
    same(result.classes[key].planned, planned[key], `${key} denominator is the elapsed side only`);
    same(result.classes[key].credited, 0, `${key} has nothing credited without logs`);
    same(result.classes[key].extra, 0, `${key} records no extra sets without logs`);
    same(result.classes[key].pct, planned[key] ? 0 : null, `${key} completion starts at zero, not fourteen weeks early`);
  });
  same(result.sessions.elapsed, elapsedSessions,
    `elapsed sessions count only the ${elapsedSessions} sessions whose date arrived`);
  same(result.sessions.reviewed, 0, 'nothing is reviewed before a single zero is logged');
  same(result.sessions.untouched, elapsedSessions, 'every elapsed session is untouched');
  same(result.planned.main + result.planned.accessory + result.planned.sbdVar + result.planned['nonSbdVar'],
    planned.main + planned.var + planned.acc, 'raw bucket totals add up to the class totals');
  console.log(`PASS completion R5: as of ${asOf} main ${planned.main} / var ${planned.var} / acc ${planned.acc} planned sets, ${elapsedSessions} sessions elapsed`);
}
function membershipMatrixCheck() {
  // The landing matrix must read the exported table, not a second copy typed into Vue.
  const members = json('web/src/membership.json');
  const vue = readFileSync(join(root, 'web', 'src', 'components', 'MembershipMatrix.vue'), 'utf8');
  const welcome = readFileSync(join(root, 'web', 'src', 'components', 'WelcomeView.vue'), 'utf8');
  same(members.columns, ['free', 'lite', 'plus', 'pro'], 'four columns; Ultra never takes a column');
  same(members.tiers.length, 5, 'five tiers exist');
  assert.ok(vue.includes("import membership from '../membership.json'"), 'the matrix imports the exported table');
  ['¥', 'US$', '19.9', '69.9', '198', '98'].forEach(text => {
    assert.ok(!vue.includes(`'${text}`), `no typed-in price (${text}) in the component`);
  });
  members.capabilities.forEach(item => {
    assert.ok(!vue.includes(item.label), `capability label "${item.label}" is not copied into the component`);
  });
  assert.ok(vue.includes('<table') && vue.includes('<th scope="col"'), 'a real table with scoped headers');
  assert.ok(vue.includes('<th scope="row"'), 'row headers name each capability');
  assert.ok(vue.includes('aria-label'), 'included/not-included cells carry a label, not just a glyph');
  assert.ok(vue.includes("'0fr'") || vue.includes('grid-template-rows'), 'the collapsed rows animate through grid rows');
  assert.ok(vue.includes('ResizeObserver'), 'the sticky offset is measured, not hardcoded');
  assert.ok(vue.includes('prefers-reduced-motion'), 'reduced motion turns the reveal off');
  assert.ok(welcome.includes('<MembershipMatrix />'), 'the landing page renders the matrix');
  assert.ok(welcome.includes('data-testid="wl-share"') && welcome.includes('Link copied'), 'the share control and its feedback exist');
  assert.ok(!welcome.includes('no tiers'), 'the old "no tiers" copy is gone');
  assert.ok(welcome.includes('data-testid="wl-tour"') && welcome.includes("onPointerDown"), 'the screenshot deck is dragged by the pointer');
  assert.ok(welcome.includes('wl-tour-dots') && welcome.includes('frameStyle'), 'dots select a frame and every frame carries a drag offset');
  assert.ok(!welcome.includes('--tour-p') && !welcome.includes('readTour'), 'the scroll reader is gone, not running beside the deck');
  checks++;
  console.log(`PASS membership matrix: ${members.capabilities.length} capabilities from membership.json, four columns plus the Ultra strip`);
}
function membershipPanelCheck() {
  // The account panel reads the session and the membership endpoints; it must not
  // keep its own tier ladder or device limit.
  const panel = readFileSync(join(root, 'web', 'src', 'components', 'MembershipPanel.vue'), 'utf8');
  const register = readFileSync(join(root, 'web', 'src', 'components', 'RegisterView.vue'), 'utf8');
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  const members = json('web/src/membership.json');
  assert.ok(panel.includes('/api/membership/sessions') && panel.includes('/api/membership/redeem'), 'devices and redemption go through the API');
  assert.ok(panel.includes("props.session?.device_limit ?? membership.device_limit"), 'the device limit comes from the session or the export');
  assert.ok(panel.includes('timeZone: \'Asia/Shanghai\''), 'expiry and device stamps are Beijing time');
  assert.ok(panel.includes('data-testid="redeem-code"') && panel.includes('redeem-message'), 'the code field and its feedback exist');
  assert.ok(panel.includes('min-height: 44px'), 'panel controls stay at 44 px');
  assert.ok(app.includes('<MembershipPanel') && app.includes('@changed="refreshSessionOnce"'), 'the vault page mounts the panel and refreshes the session after a redemption');
  assert.ok(register.includes('URLSearchParams(location.search).get(\'code\')'), '/register?code= prefills the invite field');
  assert.ok(panel.includes('PERMANENT'), 'a permanent tier is labelled instead of an expiry date');
  assert.ok(!panel.includes('"free": 1') && members.tiers.includes('ultra'), 'tiers stay in the export');
  checks++;
  console.log('PASS membership panel: session-driven tier, devices from /api/membership/sessions, redemption through the API');
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
function auditFixesCheck() {
  // Defects from the 0.38 independent review, each pinned to the code that closes it.
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  const analysis = readFileSync(join(root, 'web', 'src', 'components', 'AnalysisView.vue'), 'utf8');
  const matrix = readFileSync(join(root, 'web', 'src', 'components', 'MembershipMatrix.vue'), 'utf8');
  const strip = readFileSync(join(root, 'web', 'src', 'components', 'BarbellStrip.vue'), 'utf8');
  const card = readFileSync(join(root, 'web', 'src', 'components', 'ShareCard.vue'), 'utf8');
  const browser = readFileSync(join(root, 'tests', 'browser.mjs'), 'utf8');
  const title = readFileSync(join(root, 'server', 'tools', 'gen_data.py'), 'utf8');
  const landing = readFileSync(join(root, 'web', 'src', 'components', 'WelcomeView.vue'), 'utf8');
  // D-01: a tier change re-reads the derived projection, not only the session.
  assert.ok(/async function refreshSessionOnce[\s\S]*await loadSession\(\)[\s\S]*await refresh\(\)/.test(app), 'D-01: redeem refreshes plan/analysis/geometry after the session');
  checks++;
  assert.ok(analysis.includes("if (!props.geometry?.leaves) return [];") && analysis.includes('muscle-geometry-pending'), 'D-01: a missing geometry degrades to a placeholder instead of throwing');
  checks++;
  // D-02: the register shares the R5 as-of denominator and min(actual, planned) credit.
  assert.ok(analysis.includes("props.analysis?.completion?.asOf") && analysis.includes('Math.min(actualHere, plannedHere)'), 'D-02: register completion uses the R5 elapsed policy');
  checks++;
  assert.ok(!analysis.includes('item.actual / item.planned * 100'), 'D-02: the whole-cycle ratio is gone from the register');
  checks++;
  // D-04: toggle buttons expose their state.
  assert.ok(matrix.includes('aria-expanded="false" aria-controls="mm-extra-rows"'), 'D-04: collapsed toggle announces aria-expanded');
  checks++;
  // D-05: an omitted prop must not silently count collars.
  assert.ok(/collarPair: { type: Number, default: 0 }/.test(strip), 'D-05: BarbellStrip defaults collars off');
  checks++;
  // D-06: the canvas redraws when collars change.
  assert.ok(card.includes('watch([data, () => props.theme, collarPair], draw'), 'D-06: share card watches the collar pair');
  checks++;
  // D-07: the screenshot folder follows the release instead of a hard-coded number.
  assert.ok(browser.includes("JSON.parse(readFileSync(join(root, 'web', 'package.json'), 'utf8')).version"), 'D-07: SHOTS_DIR derives from package.json');
  assert.ok(!browser.includes("shots', '0.38'"), 'D-07: no hard-coded release folder');
  checks += 2;
  // U-01: the test note is split so only the test week shows it.
  const plan = json('data/plan.json');
  assert.ok(plan.days.every(day => !/\(W\d+\s+TEST\)/.test(day.titleEn)), 'U-01: day titles no longer carry a test note');
  assert.ok(plan.days.some(day => /\(W\d+\s+TEST\)/.test(day.testTitleEn || '')), 'U-01: the test note survives on testTitleEn');
  assert.ok(app.includes('weekMeta.value?.kind === \'test\' && meta.testTitleEn'), 'U-01: the UI shows the note only in the test week');
  checks += 3;
  // D-03: landing links reach a 44 px hit area.
  assert.ok(landing.includes('.wl-top-nav a { display: inline-flex; align-items: center; min-height: 44px;') && landing.includes('.wl-foot-links a { display: inline-flex; align-items: center; min-height: 44px;'), 'D-03: landing nav and footer links reach 44 px');
  checks++;
  assert.ok(readFileSync(join(root, 'web', 'src', 'components', 'MembershipMatrix.vue'), 'utf8').includes('min-height: 44px; color: var(--bg)'), 'D-03: the invite link reaches 44 px');
  checks++;
  console.log('PASS audit fixes: D-01..D-07, U-01 and D-03 pinned to their code');
}
function calendarViewCheck() {
  // The calendar is a projection, not a second copy of the plan.
  const view = readFileSync(join(root, 'web', 'src', 'components', 'CalendarView.vue'), 'utf8');
  const router = readFileSync(join(root, 'web', 'src', 'main.js'), 'utf8');
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  const server = readFileSync(join(root, 'server', 'app', 'calendar.py'), 'utf8');
  const api = readFileSync(join(root, 'server', 'app', 'main.py'), 'utf8');
  assert.ok(router.includes("'/calendar'") && app.includes("<CalendarView v-if=\"page === 'calendar'\" />"), '/calendar is a registered route with a rendered page');
  checks++;
  assert.ok(['week', 'month', 'agenda'].every(id => view.includes(`id: '${id}'`) || view.includes(`'cal-view-${id}'`)), 'the three views exist');
  checks++;
  assert.ok(view.includes('/api/calendar') && view.includes('URLSearchParams(range.value)'), 'the page reads the range projection instead of copying plan rows');
  checks++;
  assert.ok(!/\bPOST|\bPUT|\bPATCH|\bDELETE\b/.test(view) && !view.includes('method:'), 'the calendar never writes: read-only by construction');
  checks++;
  assert.ok(server.includes('def calendar_days(') && server.includes('date_from <= date < date_to'), 'the projection is half-open on the server');
  checks++;
  assert.ok(api.includes("alias='from'") && api.includes("alias='to'"), 'the API takes from/to as an explicit half-open range');
  checks++;
  assert.ok(server.includes("'skipped'") && server.includes("'missed' if date < today else 'planned'"), 'statuses keep explicit-zero skips apart from missed days');
  checks++;
  assert.ok(server.includes("'cycles':") && view.includes('inSpan(date) ? \'Rest\' : \'\''), 'an empty day inside a cycle reads REST; a date no cycle spans stays blank');
  checks++;
  console.log('PASS calendar projection: /calendar with week/month/agenda, half-open range, read-only');
}
function copyAndLabelsCheck() {
  // 0.45: copy, repeated-row labels, capacity ruler and the glossary.
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  assert.ok(app.includes("weeks.length === 1 ? 'WEEK' : 'WEEKS'"), 'one week never prints "1 WEEKS"');
  assert.ok(app.includes('class="masthead-signout"'), 'the masthead carries a sign-out control');
  const rows = readFileSync(join(root, 'web', 'src', 'components', 'ExerciseRows.vue'), 'utf8');
  assert.ok(rows.includes('ex-row-tag'), 'a repeated movement row carries its own TOP / BACK-OFF tag');
  assert.ok(rows.includes('repeatedNames[row.nameEn] > 1'), 'the tag appears only when the movement repeats');
  const capacity = readFileSync(join(root, 'web', 'src', 'components', 'WeekCapacity.vue'), 'utf8');
  assert.ok(capacity.includes('cap-axis'), 'the capacity bar carries a numbered axis');
  assert.ok(capacity.includes('MEV is the least effective volume'), 'MEV is explained in words, not only as a tick');
  const glossary = readFileSync(join(root, 'web', 'src', 'components', 'Glossary.vue'), 'utf8');
  ['SBD', 'MEV', 'MRV', 'RPE', 'GPP', 't', 'ses', 'TOP / BACK-OFF'].forEach(term => {
    assert.ok(glossary.includes(`'${term}'`), `the glossary defines ${term}`);
  });
  // 0.46: a cycle that has not begun says so on the cycle page, not only on Today.
  assert.ok(app.includes('data-testid="cycle-prestart-band"'), 'the cycle page carries a not-started band');
  assert.ok(app.includes("calendar.value.status !== 'upcoming'"), 'the band exists only before the start date');
  assert.ok(app.includes("startCountdown ? 'STARTS IN' : 'START'"), 'the start metric becomes a countdown before day one');
  checks += 7;
  console.log('PASS copy and labels: plurals, sign out, row tags, capacity axis, glossary');
}

function logicAffordanceCheck() {
  // 0.43: the attempt ladder may not tie, a history row may not be a dead button,
  // and the calendar detail may not label a session by her lift letters alone.
  const attempts = readFileSync(join(root, 'server', 'app', 'stats', 'attempts.py'), 'utf8');
  assert.ok(attempts.includes('def ceil25('), 'the ladder can step up instead of only flooring');
  assert.ok(attempts.includes('values[index] = ceil25(values[index - 1] + 2.5)'),
    'a would-be tie moves the third attempt up one 2.5 kg step');
  const ai = readFileSync(join(root, 'web', 'src', 'components', 'AiOutlook.vue'), 'utf8');
  assert.ok(ai.includes('This call keeps its timing and usage only'), 'a call with no stored text says so');
  assert.ok(ai.includes('callState.error'), 'a failed history fetch shows its reason instead of nothing');
  const calendar = readFileSync(join(root, 'web', 'src', 'components', 'CalendarView.vue'), 'utf8');
  assert.ok(calendar.includes('SESSION {{ day.day }}'), 'the calendar detail names the session it belongs to');
  assert.ok(calendar.includes('day.rows'), 'the calendar detail lists the prescribed rows themselves');
  checks += 4;
  console.log('PASS logic and affordances: the ladder never ties, a history row always answers, the detail names its session');
}

function blockTestDateCheck() {
  // One cycle has one test week and one block owns it. The block page passes that
  // block's own date, never the global SBD date to every block (0.42).
  const plan = json('data/plan.json');
  const sbd = plan.testPlan?.dates?.sbd;
  const testWeeks = plan.weeks.filter(week => week.kind === 'test');
  same(testWeeks.length, 1, 'the cycle holds exactly one test week');
  const owners = plan.blocks.filter(block => testWeeks.some(week => week.blockId === block.id));
  same(owners.map(block => block.id), [testWeeks[0].blockId], 'exactly one block owns the test week');
  assert.ok(testWeeks[0].dateStart <= sbd && sbd <= testWeeks[0].dateEnd, 'the test day falls inside its own week');
  const others = plan.blocks.filter(block => block.id !== owners[0].id);
  assert.ok(others.every(block => !plan.weeks.some(week => week.blockId === block.id && week.kind === 'test')),
    'no other block carries a test week');
  checks++;
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  assert.ok(app.includes(':test-date="blockTestDate"'), 'the block page reads its own test date from blockTestDate');
  assert.ok(!app.includes(':per-week="blockPerWeek" :test-date="plan.testPlan?.dates?.sbd"'),
    'the block view no longer receives the global SBD date');
  assert.ok(app.includes('const blockTestDate = computed'), 'the block-scoped date exists as one computed value');
  checks += 2;
  console.log(`PASS block test day: ${sbd} belongs to ${testWeeks[0].blockId} / W${testWeeks[0].n}; ${others.map(block => block.id).join(', ')} show no test day`);
}

function totalsReconcileCheck() {
  // One calculation (server/app/stats/totals.py) rendered everywhere: cycle page,
  // week cards, day header, calendar, Assay and the landing chart. The expected
  // numbers below are hand sums of plan rows, never read back out of the engine.
  const plan = json('data/plan.json');
  const rows = plan.workouts;
  const round1 = value => Number(Number(value).toFixed(1));
  const handCycleSets = rows.reduce((sum, row) => sum + row.sets, 0);
  const handCycleKg = rows.reduce((sum, row) => sum + (row.tonnageKg || 0), 0);
  const handWeek = new Map();
  plan.weeks.forEach(week => handWeek.set(week.n, { sets: 0, kg: 0 }));
  const handDay = new Map();
  rows.forEach(row => {
    const week = handWeek.get(row.week);
    week.sets += row.sets;
    week.kg += row.tonnageKg || 0;
    const key = `${row.week}|${row.day}`;
    handDay.set(key, (handDay.get(key) || 0) + row.sets);
  });

  const sample = runPython(`import json
from server.app.stats import totals as T
from server.app.calendar import calendar_days
p = json.load(open('data/plan.json', encoding='utf-8'))
head = T.totals(p)
chain = T.display_chain(p)
cal = calendar_days([p], {}, p['meta']['startDate'], p['meta']['endDate'])
print(json.dumps({
  'cycle': head['cycle'], 'perWeek': head['perWeek'], 'perDay': head['perDay'],
  'perBlock': head['perBlock'], 'perLift': head['perLift'], 'basis': head['basis'],
  'chain': chain,
  'calendar': [{'week': d['week'], 'day': d['day'], 'prescribed': d['prescribedSets']} for d in cal['days']],
}))`);
  const cycle = sample.cycle;
  same(cycle.sets.total, handCycleSets, 'cycle sets are the hand sum of plan rows');
  same(cycle.sets.main + cycle.sets.variation + cycle.sets.accessory, cycle.sets.total, 'the three classes add to the total');
  same(cycle.tonnageKg, round1(handCycleKg), 'cycle tonnage is the hand sum of row tonnage');
  same(cycle.tonnageKg, plan.meta.cycleTonnageKg, 'the cycle headline equals meta.cycleTonnageKg');
  sample.perWeek.forEach(week => {
    const hand = handWeek.get(week.n);
    same(week.sets.total, hand.sets, `W${week.n} sets are the hand sum of its rows`);
    same(week.tonnageKg, round1(hand.kg), `W${week.n} tonnage is the hand sum of its rows`);
  });
  sample.perDay.forEach(entry => {
    same(entry.sets.total, handDay.get(`${entry.week}|${entry.day}`), `W${entry.week} ${entry.day} sets are the hand sum of its rows`);
  });
  assert.ok(sample.chain.blocksReconcile, 'block sub-totals at 0.01 t add to the cycle headline');  assert.ok(sample.chain.weeksReconcile, 'week sub-totals at 0.01 t add to the cycle headline');
  same(sample.chain.cycleT, round1(handCycleKg / 1000), 'headline tonnes come from the same sum');
  sample.calendar.forEach(entry => {
    same(entry.prescribed, handDay.get(`${entry.week}|${entry.day}`), `calendar ${entry.week}|${entry.day} prescribed sets match the rows`);
  });
  const first = sample.calendar[0];
  same(first.prescribed, handDay.get(`${first.week}|${first.day}`), 'calendar and the day header share one count');

  const facts = json('web/src/landing-facts.json');
  same(facts.set_count, handDay.get(`${facts.week}|${facts.day}`), 'landing day count equals the day header count');
  same(facts.weeks.map(week => week.sets), sample.perWeek.map(week => week.sets.total), 'landing chart draws the same weekly series as the cycle chart');
  same(facts.cycle_sets, handCycleSets, 'landing cycle count is the cycle headline');
  same(facts.sets_by_class, sample.perDay.find(entry => entry.week === facts.week && entry.day === facts.day).sets, 'landing carries the class split it prints');

  // No page may add sets or tonnage a second time; the map component must not type one.
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  assert.ok(!app.includes('sum + row.sets'), 'App.vue does not sum row sets itself');
  assert.ok(!app.includes('sum + row.tonnageKg'), 'App.vue does not sum row tonnage itself');
  const welcome = readFileSync(join(root, 'web', 'src', 'components', 'WelcomeView.vue'), 'utf8');
  assert.ok(!/const capSets = \[/.test(welcome), 'the landing chart has no hand-typed set series');
  assert.ok(!/const capTop = \[/.test(welcome), 'the landing chart has no hand-typed intensity series');
  checks += 3;
  console.log(`PASS totals: ${handCycleSets} sets / ${round1(handCycleKg / 1000)} t reconciled across cycle, blocks, weeks, days, calendar, Assay and landing; four blocks at 0.01 t add to the headline`);
}

function governanceCheck() {
  // The exits and the refresh policy are promised on the /about page, so they are asserted here.
  const app = readFileSync(join(root, 'web', 'src', 'App.vue'), 'utf8');
  const router = readFileSync(join(root, 'web', 'src', 'main.js'), 'utf8');
  const about = readFileSync(join(root, 'web', 'src', 'components', 'AboutView.vue'), 'utf8');
  const daily = readFileSync(join(root, 'web', 'src', 'components', 'DailyRecord.vue'), 'utf8');
  assert.ok(router.includes("'/about'"), '/about is a registered route, not a dead footer link');
  checks++;
  assert.ok(app.includes("if (route.path === '/about') return 'about';"), 'App.vue resolves the about page');
  checks++;
  assert.ok(app.includes('<RouterLink to="/about" class="footer-about">ABOUT</RouterLink>'), 'the footer ABOUT link points at /about');
  checks++;
  assert.ok(about.includes('Export and delete, both explicit'), 'the about page names the exits it promises');
  checks++;
  assert.ok(!app.includes('setInterval('), 'no polling: a 3M link and 4C4G cannot afford a heartbeat');
  checks++;
  assert.ok(app.includes("document.addEventListener('visibilitychange'"), 'returning to the tab refreshes once');
  checks++;
  assert.ok(app.includes('timed_until'), 'a timed tier schedules its own one-shot expiry');
  checks++;
  assert.ok(app.includes(":readonly=\"!can('recovery_body')\""), 'free tiers read the daily record with the write locked');
  checks++;
  assert.ok(daily.includes('readonlyNote'), 'the locked record explains itself');
  checks++;
  const orphans = spawnSync(python, ['server/tools/audit_orphans.py', '--json'], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  assert.equal(orphans.status, 0, `orphan audit failed: ${orphans.stdout}${orphans.stderr}`);
  const audit = JSON.parse(orphans.stdout);
  assert.equal(audit.total, 0, `orphan rows present: ${JSON.stringify(audit.orphans)}`);
  checks++;
  assert.ok(audit.checked.length >= 17, 'every cycle- and account-scoped link is audited');
  checks++;
  assert.equal(audit.skipped.length, 0, `links skipped on the live database: ${JSON.stringify(audit.skipped)}`);
  checks++;
  console.log(`PASS governance: /about routed, write gates explained, no polling, ${audit.checked.length} links with 0 orphans`);
}
(async () => {
try {
  fixtureCheck();
  if (!sabotage) {
    libraryCheck();
    syntheticCheck();
    await plateCheck();
    await plateParityCheck();
    await shareCheck();
    landingFactsCheck();
    totalsReconcileCheck();
    blockTestDateCheck();
    logicAffordanceCheck();
    copyAndLabelsCheck();
    planCalendarCheck();
    testPlanCheck();
    completionCheck();
    membershipMatrixCheck();
    membershipPanelCheck();
    calendarViewCheck();
    auditFixesCheck();
    governanceCheck();
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
