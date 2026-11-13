const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { readFileSync, existsSync } = require('node:fs');
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
try {
  fixtureCheck();
  if (!sabotage) {
    libraryCheck();
    syntheticCheck();
    const unit = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' }, timeout: 600000, maxBuffer: 5 * 1024 * 1024 });
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
