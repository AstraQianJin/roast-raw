<script setup>
import { computed, onMounted, ref } from 'vue';
import MuscleMap from './MuscleMap.vue';
import WeekCapacity from './WeekCapacity.vue';
import CapacityBoard from './CapacityBoard.vue';
import TrendView from './TrendView.vue';
import LockedFeature from './LockedFeature.vue';

const props = defineProps({
  plan: { type: Object, required: true },
  analysis: { type: Object, required: true },
  geometry: { type: Object, default: null },
  capabilities: { type: Array, default: () => [] },
  performance: { type: Object, default: null },
  currentWeek: { type: Number, default: 1 },
  mode: { type: String, default: 'plan' },
  logs: { type: Object, default: () => ({}) },
});
const emit = defineEmits(['week', 'mode']);
const can = capability => props.capabilities.includes(capability);
const tab = ref('overview');
const tabs = [
  { k: 'overview', l: 'Overview' },
  { k: 'lifts', l: 'By lift' },
  { k: 'muscle', l: 'Muscle' },
  { k: 'trend', l: 'Trend' },
];
// Test-day battery. Read-only here: the test week owns the inputs, this panel only
// puts a recorded result beside the SBD anchor it belongs to.
const tests = ref(null);
const TEST_ANCHOR = {
  low_bar_squat: ['squat', 'sq_1rm'], wide_grip_bench: ['bench', 'bp_1rm'],
  sumo_deadlift: ['deadlift', 'dl_1rm'], power_clean: ['deadlift', 'dl_1rm'],
  ohp: ['bench', 'bp_1rm'], barbell_row: ['deadlift', 'dl_1rm'],
};
const clock = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
onMounted(async () => {
  try {
    const response = await fetch(`/api/test-results?${new URLSearchParams({ cycle_id: props.plan.meta.planId })}`, { cache: 'no-store' });
    if (response.ok) tests.value = await response.json();
  } catch { /* the panel stays out of the way when the server is unreachable */ }
});
const testRows = computed(() => (tests.value?.items || []).map(item => {
  const result = item.result;
  const mapping = TEST_ANCHOR[item.id];
  const anchorKey = mapping ? mapping[1] : null;
  const anchorKg = anchorKey ? (props.plan.meta.profile[anchorKey] ?? null) : null;
  let value = null;
  if (result) {
    value = item.kind === 'run'
      ? (result.duration_s ? `${clock(result.duration_s)}${result.hr ? ` · ${result.hr} bpm` : ''}` : null)
      : `${result.load} kg${result.reps ? ` × ${result.reps}` : ''}`;
  }
  const vs = result && item.kind !== 'run' && anchorKg ? result.load / anchorKg * 100 : null;
  return { id: item.id, label: item.labelEn, value, vs, anchor: mapping ? `${mapping[0]} anchor` : null };
}));
const liftLabels = { S: 'Squat', B: 'Bench', D: 'Deadlift' };
const liftKeys = { S: 'sq', B: 'bp', D: 'dl' };
const display = value => value === null || value === undefined ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 });
const lifts = computed(() => ['S', 'B', 'D'].map(code => {
  const key = liftKeys[code];
  const profile = props.plan.meta.profile;
  const start = profile[`init_${key}`] ?? profile[`${key}_1rm`] ?? 0;
  const now = profile[`${key}_1rm`] ?? start;
  const target = profile[`target_${key}`] ?? null;
  const rows = props.analysis.perWeek.map(week => ({
    n: week.n,
    kind: week.kind,
    sets: (week.lifts?.[code]?.main || 0) + (week.lifts?.[code]?.var || 0),
    top: week.topPctByLift?.[code] ?? null,
  }));
  const maxSets = Math.max(1, ...rows.map(row => row.sets));
  const total = rows.reduce((sum, row) => sum + row.sets, 0);
  const top = Math.max(0, ...rows.map(row => row.top || 0));
  const gain = target === null ? null : target - now;
  const progress = target && target > start ? Math.min(100, Math.max(0, (now - start) / (target - start) * 100)) : now >= (target || now) ? 100 : 0;
  return { code, name: liftLabels[code], start, now, target, gain, progress, rows, maxSets, total, top };
}));
const cycle = computed(() => props.analysis.cycle);
const completion = computed(() => props.analysis.completion);
const topIntensity = computed(() => Math.max(0, ...props.analysis.perWeek.map(week => week.topPct || 0)));
const mix = computed(() => [
  { k: 'MAIN', v: cycle.value.roles.main, c: 'var(--t1)' },
  { k: 'SBD VAR', v: cycle.value.roles.sbdVar, c: 'var(--t2)' },
  { k: 'OTHER VAR', v: cycle.value.roles.nonSbdVar, c: 'var(--ct-peak)' },
  { k: 'ACCESSORY', v: cycle.value.roles.accessory, c: 'var(--t3)' },
]);
const mixTotal = computed(() => mix.value.reduce((sum, item) => sum + item.v, 0) || 1);
const weekNow = computed(() => props.analysis.perWeek.find(week => week.n === props.currentWeek) || props.analysis.perWeek[0]);
const muscleLeaves = computed(() => {
  // Geometry can lag one refresh behind a tier change; never let a blank object reach a tab.
  if (!props.geometry?.leaves) return [];
  return props.analysis.leafOrder.map(id => {
  const values = weekNow.value?.leaves?.[id] || {};
  const range = props.analysis.ranges.leaf[id];
  return {
    id,
    name: props.geometry.leaves[id]?.en || id,
    weighted: values.w || 0,
    raw: values.raw || 0,
    heat: values.heat || { Both: { band: 0 } },
    direct: values.d || 0,
    primaryWeighted: values.primaryWeighted || 0,
    secondaryWeighted: values.secondaryWeighted || 0,
    mev: range?.mev ?? null,
    mrv: range?.mrv ?? null,
    scope: range?.scope || 'leaf',
    verdict: '',
  };
  });
});
function blockTone(id) {
  const type = (props.plan.blocks.find(block => block.id === id)?.cycleType || '').toLowerCase();
  return { hyper: 'var(--ct-hyper)', strength: 'var(--ct-strength)', transmute: 'var(--ct-transmute)', peak: 'var(--ct-peak)' }[type] || 'var(--ct-custom)';
}
// The completion policy owns the as-of date; the register never invents its own denominator.
const asOf = computed(() => props.analysis?.completion?.asOf || '9999-12-31');
const exerciseGroups = computed(() => {
  const map = new Map();
  for (const row of props.plan.workouts || []) {
    const key = row.movementId || row.nameEn;
    if (!key) continue;
    let item = map.get(key);
    if (!item) {
      item = {
        key, name: row.nameEn || row.movement || key, lift: row.lift || '',
        bucket: row.bucket || (row.role === 'variation' ? 'sbdVar' : row.role),
        sets: 0, planned: 0, actual: 0, elapsedPlanned: 0, elapsedCredited: 0,
        tonnage: 0, sessions: new Set(), weeks: new Set(), topLoad: 0, topPct: 0, e1rm: 0,
      };
      map.set(key, item);
    }
    const log = props.logs[`${row.week}|${row.day}|${row.seq}`];
    item.sets += Number(row.sets) || 0;
    item.planned += Number(row.sets) || 0;
    if (log && Number(log.sets) > 0) {
      item.actual += Number(log.sets);
      const load = Number(log.load) || 0;
      const reps = Number(log.reps) || 0;
      if (load > 0 && reps > 0) item.e1rm = Math.max(item.e1rm, load * (1 + reps / 30));
    }
    // R5: only elapsed planned sets enter the denominator, and credit is min(actual, planned).
    if (String(row.date || '9999-12-31') <= asOf.value) {
      const plannedHere = Number(row.sets) || 0;
      const actualHere = Number(log?.sets) > 0 ? Number(log.sets) : 0;
      item.elapsedPlanned += plannedHere;
      item.elapsedCredited += Math.min(actualHere, plannedHere);
    }
    item.tonnage += Number(row.tonnageKg) || 0;
    item.sessions.add(`${row.week}|${row.day}`);
    item.weeks.add(row.week);
    item.topLoad = Math.max(item.topLoad, Number(row.loadKg) || 0);
    item.topPct = Math.max(item.topPct, Number(row.pct) || 0);
  }
  const all = [...map.values()].map(item => ({
    ...item,
    weekCount: item.weeks.size,
    sessionCount: item.sessions.size,
    completion: item.elapsedPlanned ? Math.min(100, item.elapsedCredited / item.elapsedPlanned * 100) : 0,
    topPct: item.topPct * 100,
    e1rm: item.e1rm || 0,
  }));
  const liftOrder = { S: 0, B: 1, D: 2 };
  const byLift = (a, b) => (liftOrder[a.lift] ?? 9) - (liftOrder[b.lift] ?? 9) || b.sets - a.sets;
  return [
    { key: 'main', label: 'Main lifts', note: 'The three competition lifts and their anchor variations.', rows: all.filter(item => item.bucket === 'main').sort((a, b) => b.sets - a.sets || byLift(a, b)) },
    { key: 'var', label: 'Variations', note: 'SBD-adjacent work; it supports the lift without replacing it.', rows: all.filter(item => item.bucket !== 'main' && item.bucket !== 'accessory').sort(byLift) },
    { key: 'accessory', label: 'Accessory', note: 'Muscle and joint work. Never converted into SBD capacity.', rows: all.filter(item => item.bucket === 'accessory').sort((a, b) => b.sets - a.sets).slice(0, 14) },
  ];
});
const blocks = computed(() => props.plan.blocks.map(block => {
  const weeks = props.analysis.perWeek.filter(week => week.blockId === block.id);
  return {
    id: block.id, name: block.nameEn, tone: blockTone(block.id),
    weeks: weeks.length,
    sets: weeks.reduce((sum, week) => sum + week.total, 0),
    tonnage: weeks.reduce((sum, week) => sum + week.tonnageKg, 0),
    sessions: weeks.reduce((sum, week) => sum + week.sessions, 0),
  };
}));
</script>

<template>
  <section class="analysis-view" data-testid="analysis-view">
    <header class="analysis-hero">
      <div>
        <div class="eyebrow">RR / 02 · ASSAY — LOCAL DATA / {{ plan.meta.weeks }} WEEKS · {{ plan.meta.sessions }} SESSIONS</div>
        <h1>What the cycle built.</h1>
        <p class="analysis-deck">From the cycle goal down to each lift: prescribed volume, top intensity and the muscle it landed on. Planned and logged are kept apart.</p>
      </div>
      <aside class="analysis-stamp">
        <span>TOP %1RM</span>
        <strong>{{ display(topIntensity) }}<small>%</small></strong>
        <span>{{ analysis.mode === 'plan' ? 'PRESCRIBED' : 'LOGGED + PLANNED' }}</span>
      </aside>
    </header>

    <nav class="analysis-tabs" aria-label="Analysis sections">
      <button v-for="item in tabs" :key="item.k" type="button" :aria-pressed="tab === item.k" @click="tab = item.k">{{ item.l }}</button>
    </nav>

    <template v-if="tab === 'overview'">
      <section class="kpi-grid" aria-label="Cycle totals">
        <div class="kpi"><span>CYCLE TONNAGE</span><strong>{{ display(cycle.tonnageKg / 1000) }}<small> t</small></strong><em>prescribed segment loads</em></div>
        <div class="kpi"><span>WORKING SETS</span><strong>{{ display(cycle.total) }}</strong><em>{{ cycle.sessions }} sessions across {{ plan.meta.weeks }} weeks</em></div>
        <div class="kpi"><span>COMPLETION</span><strong>{{ display(completion.main) }}<small>%</small></strong><em>main · var {{ display(completion.var) }}% · acc {{ display(completion.acc) }}% · {{ completion.sessions?.elapsed ?? 0 }} sessions elapsed, {{ completion.sessions?.reviewed ?? 0 }} reviewed</em></div>
        <div class="kpi"><span>TOP INTENSITY</span><strong>{{ display(topIntensity) }}<small>%</small></strong><em>highest planned top set</em></div>
      </section>

      <section class="goal-panel" aria-label="Cycle goals">
        <div class="panel-head"><div><div class="eyebrow">CYCLE GOAL</div><h2>Start, now, target.</h2></div><p class="panel-note">Anchors are tested 1RM. Targets are the numbers this cycle is built around; they are not forecasts.</p></div>
        <div class="goal-rows">
          <div v-for="lift in lifts" :key="lift.code" class="goal-row">
            <div class="goal-id"><b>{{ lift.code }}</b><span>{{ lift.name }}</span></div>
            <div class="goal-track">
              <i class="goal-fill" :style="{ width: `${lift.progress}%` }"></i>
              <i class="goal-start" :style="{ left: '0%' }"></i>
              <i class="goal-now" :style="{ left: `${lift.progress}%` }"></i>
            </div>
            <div class="goal-numbers"><small>{{ display(lift.now) }}</small><strong>{{ display(lift.target) }}<small> kg</small></strong><em>{{ lift.gain === null ? '—' : `${lift.gain > 0 ? '+' : ''}${display(lift.gain)} kg` }}</em></div>
          </div>
        </div>
        <div class="goal-scale"><span>{{ display(lifts[0].start) }} kg anchor</span><span>target</span></div>
      </section>

      <section v-if="testRows.length" class="test-panel" aria-label="Test results" data-testid="analysis-tests">
        <div class="panel-head">
          <div><div class="eyebrow">TEST DAY</div><h2>What the battery actually moved.</h2></div>
          <p class="panel-note">{{ testRows.filter(row => row.value !== null).length }} of {{ testRows.length }} items recorded. Each result is the load tested that day; the percentage is against the matching SBD anchor, not a forecast.</p>
        </div>
        <ul class="test-compare">
          <li v-for="row in testRows" :key="row.id" :data-testid="`analysis-test-${row.id}`">
            <span class="tc-name">{{ row.label }}</span>
            <span class="tc-value">{{ row.value === null ? 'Not recorded' : row.value }}</span>
            <span class="tc-vs">{{ row.vs === null ? '—' : `${display(row.vs)}% of ${row.anchor}` }}</span>
          </li>
        </ul>
      </section>

      <section class="block-strip" aria-label="Block contribution">
        <div class="panel-head"><div><div class="eyebrow">BLOCKS</div><h2>Where the work sits.</h2></div><p class="panel-note">Same weeks as the Cycle page. Colour is the phase, not a verdict.</p></div>
        <div class="block-strip-rows">
          <div v-for="block in blocks" :key="block.id" class="block-strip-row">
            <span class="strip-id">{{ block.id }}</span>
            <span class="strip-name">{{ block.name }}</span>
            <div class="strip-bar"><i :style="{ width: `${block.sets / cycle.total * 100}%`, background: block.tone }"></i></div>
            <span class="strip-meta">{{ display(block.tonnage / 1000) }} t · {{ block.sessions }} ses</span>
          </div>
        </div>
      </section>

      <section class="mix-panel" aria-label="Set mix">
        <div class="eyebrow">SET MIX</div>
        <div class="mix-bar"><i v-for="item in mix" :key="item.k" :style="{ width: `${item.v / mixTotal * 100}%`, background: item.c }"></i></div>
        <div class="mix-key"><span v-for="item in mix" :key="item.k"><i :style="{ background: item.c }"></i>{{ item.k }} {{ display(item.v) }}</span></div>
        <p class="panel-note">SBD variations count separately from main work. Accessory work is not converted into SBD capacity.</p>
      </section>
    </template>

    <LockedFeature v-else-if="tab === 'lifts' && !can('lift_register')" label="Lift register & trends" tier="plus" />
    <LockedFeature v-else-if="tab === 'muscle' && !can('muscle_map')" label="Muscle-group map" tier="plus" />
    <LockedFeature v-else-if="tab === 'trend' && !can('lift_register')" label="Lift register & trends" tier="plus" />
    <template v-else-if="tab === 'lifts'">
      <section class="lift-grid" aria-label="Per-lift analysis">
        <article v-for="lift in lifts" :key="lift.code" class="lift-card" :class="`lift-${lift.code}`">
          <header><span class="lift-code">{{ lift.code }}</span><div><h2>{{ lift.name }}</h2><p>{{ display(lift.total) }} sets · top {{ display(lift.top) }}% 1RM</p></div><div class="lift-now"><strong>{{ display(lift.now) }}</strong><small>kg</small></div></header>
          <div class="lift-week-bars">
            <div v-for="row in lift.rows" :key="row.n" class="lift-week" :class="row.kind" :title="`W${row.n}: ${row.sets} sets · top ${display(row.top)}%`">
              <i :style="{ height: `${Math.max(3, row.sets / lift.maxSets * 100)}%` }"></i>
              <span>{{ String(row.n).padStart(2, '0') }}</span>
            </div>
          </div>
          <div class="lift-foot"><span>ANCHOR {{ display(lift.start) }} kg</span><span>TARGET {{ display(lift.target) }} kg<template v-if="lift.gain !== null"> · {{ lift.gain > 0 ? '+' : '' }}{{ display(lift.gain) }} kg</template></span></div>
        </article>
      </section>
      <section class="ex-register" aria-label="Exercise register">
        <header class="ex-register-head"><div><div class="eyebrow">EXERCISE REGISTER</div><h2>Main, variation, accessory.</h2></div><p class="panel-note">Prescribed rows only, grouped by how each movement serves the lift. Collapsed to one line per movement.</p></header>
        <div v-for="group in exerciseGroups" :key="group.key" class="ex-group" :class="`ex-group-${group.key}`">
          <div class="ex-group-head"><h3>{{ group.label }}</h3><small>{{ group.rows.length }} movements · {{ group.rows.reduce((sum, item) => sum + item.sets, 0) }} sets</small></div>
          <p class="ex-group-note">{{ group.note }}</p>
          <div class="ex-list">
            <div v-for="item in group.rows" :key="item.key" class="ex-row" :class="item.lift ? `ex-lift-${item.lift}` : ''">
              <span class="ex-code">{{ item.lift || '·' }}</span>
              <div class="ex-name"><strong>{{ item.name }}</strong><small>{{ item.weekCount }}w · {{ item.sessionCount }}s · {{ display(item.completion) }}% done · elapsed<template v-if="item.e1rm"> · e1RM {{ display(item.e1rm) }}</template></small></div>
              <div class="ex-cell"><b>{{ display(item.sets) }}</b><small>SETS</small></div>
              <div class="ex-cell"><b>{{ display(item.topLoad) }}</b><small>KG TOP</small></div>
              <div class="ex-cell ex-pct"><b>{{ item.topPct ? display(item.topPct) : "—" }}</b><small>%1RM</small></div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <template v-else-if="tab === 'muscle'">
      <div class="analysis-filter"><span class="eyebrow">MUSCLE VOLUME</span><div class="map-filters"><button :aria-pressed="mode === 'plan'" @click="emit('mode', 'plan')">Planned</button><button :aria-pressed="mode === 'log'" @click="emit('mode', 'log')">Logged + planned</button></div></div>
      <div class="workspace analysis-workspace">
        <MuscleMap v-if="geometry" :geometry="geometry" :leaves="muscleLeaves" :heat-scale="analysis.heatScale" :week-number="currentWeek" :week-count="plan.weeks.length" @week="emit('week', $event)" />
        <div v-else class="empty-state" data-testid="muscle-geometry-pending"><h2>Muscle map unavailable.</h2><p>The anatomy geometry has not loaded for this session yet. Reload once; your plan and logs are untouched.</p></div>
        <aside><WeekCapacity :week="weekNow" :ranges="analysis.ranges" /><CapacityBoard :analysis="analysis" :week="weekNow" /></aside>
      </div>
    </template>

    <template v-else>
      <TrendView :analysis="analysis" :performance="performance" />
    </template>
  </section>
</template>

<style scoped>
.analysis-hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; }
.analysis-hero h1 { font-family: var(--serif); font-weight: 400; text-transform: none; letter-spacing: -.035em; font-size: clamp(32px, 6vw, 48px); line-height: 1.04; }
.analysis-deck { max-width: 52ch; margin-top: 12px; font-size: 13px; line-height: 1.7; color: var(--muted); }
.analysis-stamp { flex: none; min-width: 96px; padding: 12px 14px; border: 1px solid var(--line-soft); border-radius: 16px; background: linear-gradient(160deg, #FFFFFF, #F7F5EF); box-shadow: 0 10px 24px rgba(17,17,17,.06); text-align: right; }
.analysis-stamp span { display: block; font: 600 8px var(--mono); letter-spacing: .12em; color: var(--muted); }
.analysis-stamp strong { display: block; font: 700 30px var(--mono); letter-spacing: -.04em; }
.analysis-stamp strong small { font-size: 13px; }
.analysis-tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 5px; margin: 22px 0 6px; padding: 5px; border: 1px solid var(--line-soft); border-radius: 14px; background: linear-gradient(180deg, #FFFFFF, #F6F5EF); }
.analysis-tabs button { min-height: 40px; border: 0; border-radius: 9px; background: none; font: 800 10px var(--display); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.analysis-tabs button[aria-pressed='true'] { background: var(--ink); color: #FFFFFF; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 20px; }
.kpi { min-width: 0; padding: 14px 12px; border: 1px solid var(--line-soft); border-radius: 14px; background: #FFFFFF; box-shadow: 0 8px 20px rgba(17,17,17,.05); }
.kpi span { font: 600 8px var(--mono); letter-spacing: .1em; color: var(--muted); }
.kpi strong { display: block; margin-top: 6px; font: 700 clamp(21px, 4vw, 28px) var(--mono); letter-spacing: -.04em; }
.kpi strong small { font-size: 10px; color: var(--muted); }
.kpi em { display: block; margin-top: 4px; font-style: normal; font-size: 9px; line-height: 1.5; color: var(--muted); }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.panel-head h2 { font-family: var(--serif); font-weight: 400; text-transform: none; letter-spacing: -.02em; font-size: 24px; }
.panel-note { max-width: 46ch; font-size: 10px; line-height: 1.6; color: var(--muted); text-align: right; }
.goal-panel, .block-strip, .mix-panel { margin-top: 22px; padding: 18px; border: 1px solid var(--line-soft); border-radius: 16px; background: linear-gradient(180deg, #FFFFFF, #F9F8F3); box-shadow: 0 10px 26px rgba(17,17,17,.06); }
.goal-rows { margin-top: 14px; display: grid; gap: 12px; }
.goal-row { display: grid; grid-template-columns: 78px minmax(0, 1fr) auto; align-items: center; gap: 10px; }
.goal-id b { font: 700 13px var(--mono); }
.goal-id span { display: block; font-size: 9px; color: var(--muted); }
.goal-track { position: relative; height: 7px; border-radius: 4px; background: var(--line-soft); }
.goal-fill { position: absolute; inset: 0 auto 0 0; border-radius: 4px; background: linear-gradient(90deg, var(--accent), #E0503F); }
.goal-now { position: absolute; top: -3px; width: 13px; height: 13px; border-radius: 50%; background: #FFFFFF; border: 3px solid var(--accent); transform: translateX(-50%); }
.goal-numbers { display: flex; align-items: baseline; gap: 8px; white-space: nowrap; }
.goal-numbers small { font: 700 12px var(--mono); color: var(--muted); }
.goal-numbers strong { font: 700 18px var(--mono); }
.goal-numbers em { font-style: normal; font-size: 9px; color: var(--muted); }
.goal-scale { display: flex; justify-content: space-between; margin-top: 6px; padding-left: 88px; font: 8px var(--mono); color: var(--muted); }
.block-strip-rows { display: grid; gap: 9px; margin-top: 14px; }
.block-strip-row { display: grid; grid-template-columns: 22px minmax(0, 1.2fr) minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.strip-id { font: 700 10px var(--mono); }
.strip-name { font-size: 10px; color: var(--muted); }
.strip-bar { height: 7px; border-radius: 4px; background: var(--line-soft); overflow: hidden; }
.strip-bar i { display: block; height: 100%; border-radius: 4px; }
.strip-meta { font: 9px var(--mono); color: var(--muted); white-space: nowrap; }
.mix-bar { display: flex; gap: 2px; height: 12px; margin-top: 8px; border-radius: 6px; overflow: hidden; }
.mix-bar i { height: 100%; }
.mix-key { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: 9px; color: var(--muted); }
.mix-key span { display: inline-flex; align-items: center; gap: 5px; }
.mix-key i { width: 7px; height: 7px; border-radius: 2px; }
.lift-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 20px; }
.lift-card { min-width: 0; padding: 15px 13px; border: 1px solid var(--line-soft); border-radius: 16px; background: #FFFFFF; box-shadow: 0 10px 24px rgba(17,17,17,.06); }
.lift-S { --lift: var(--t1); }
.lift-B { --lift: var(--t2); }
.lift-D { --lift: var(--t3); }
.lift-card header { display: flex; align-items: flex-start; gap: 8px; }
.lift-card .lift-code { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 8px; background: var(--lift, var(--accent)); color: #FFFFFF; font: 700 12px var(--mono); }
.lift-card h2 { font-family: var(--serif); font-weight: 400; text-transform: none; font-size: 19px; }
.lift-card header p { font: 9px var(--mono); color: var(--muted); }
.lift-now { margin-left: auto; text-align: right; }
.lift-now strong { font: 700 20px var(--mono); letter-spacing: -.03em; }
.lift-now small { font: 8px var(--mono); color: var(--muted); }
.lift-week-bars { display: flex; align-items: flex-end; gap: 2px; height: 74px; margin-top: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--line-soft); }
.lift-week { position: relative; flex: 1; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
.lift-week i { display: block; width: 100%; min-height: 3px; border-radius: 2px 2px 0 0; background: var(--lift, var(--ct-hyper)); opacity: .78; }
.lift-week.deload i { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 3px, transparent 3px 5px); }
.lift-week.test i { background: var(--ink); }
.lift-week span { position: absolute; bottom: -12px; left: 50%; transform: translateX(-50%); font: 6px var(--mono); color: var(--muted); }
.lift-foot { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px; margin-top: 10px; font: 8px var(--mono); letter-spacing: .04em; color: var(--muted); }
.lift-table-wrap { margin-top: 18px; overflow-x: auto; border: 1px solid var(--line-soft); border-radius: 14px; background: #FFFFFF; }
.lift-table { width: 100%; min-width: 520px; border-collapse: collapse; font: 10px var(--mono); }
.lift-table th, .lift-table td { padding: 8px 6px; border-bottom: 1px solid var(--line-soft); text-align: right; }
.lift-table thead th { font: 600 8px var(--mono); letter-spacing: .08em; color: var(--muted); }
.lift-table th:first-child, .lift-table td:first-child { text-align: left; }
.analysis-filter { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin-top: 22px; }
@media (max-width: 880px) {
  .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .lift-grid { grid-template-columns: 1fr; }
  .goal-row { grid-template-columns: 64px minmax(0, 1fr) auto; }
  .analysis-stamp { display: none; }
}
.ex-register { margin-top: 26px; }
.ex-register-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.ex-register-head h2 { font-size: clamp(22px, 5vw, 26px); font-family: var(--serif); font-weight: 400; text-transform: none; letter-spacing: -.02em; font-size: 26px; }
.ex-group { margin-top: 14px; padding: 16px; border: 1px solid var(--line-soft); border-radius: 18px; background: #FFFFFF; box-shadow: 0 10px 26px rgba(17,17,17,.05); }
.ex-group-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.ex-group-head h3 { font: 800 11px var(--display); letter-spacing: .1em; text-transform: uppercase; }
.ex-group-head small { font: 9px var(--mono); color: var(--muted); }
.ex-group-note { margin: 3px 0 10px; font-size: 10px; line-height: 1.5; color: var(--muted); }
.ex-list { display: grid; }
.ex-row { display: grid; grid-template-columns: 24px minmax(0, 1fr) 52px 66px 58px; align-items: center; gap: 8px; padding: 9px 0; border-top: 1px solid var(--line-soft); }
.ex-code { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 6px; background: var(--panel2); font: 700 9px var(--mono); color: var(--muted); }
.ex-lift-S .ex-code { background: color-mix(in srgb, var(--t1) 12%, #FFF); color: var(--t1); }
.ex-lift-B .ex-code { background: color-mix(in srgb, var(--t2) 12%, #FFF); color: var(--t2); }
.ex-lift-D .ex-code { background: color-mix(in srgb, var(--t3) 12%, #FFF); color: var(--t3); }
.ex-name { min-width: 0; }
.ex-name strong { display: block; font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }
.ex-name small { display: block; margin-top: 1px; font: 8.5px var(--mono); color: var(--muted); }
.ex-cell { text-align: right; }
.ex-cell b { display: block; font: 700 13px var(--mono); letter-spacing: -.02em; }
.ex-cell small { font: 7px var(--mono); letter-spacing: .08em; color: var(--muted); }
.ex-pct b { color: var(--accent); }
@media (max-width: 880px) {
  .ex-row { grid-template-columns: 20px minmax(0, 1fr) 34px 46px 40px; gap: 5px; }
  .ex-cell b { font-size: 11px; }
  .ex-cell small { font-size: 6.5px; }
}
.test-panel { margin-top: 22px; padding: 18px; border: 1px solid var(--line-soft); background: var(--panel); }
.test-compare { list-style: none; margin: 12px 0 0; padding: 0; }
.test-compare li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: baseline; padding: 9px 0; border-top: 1px solid var(--line-soft); }
.test-compare li:first-child { border-top: 0; }
.tc-name { font: 600 13px var(--sans); color: var(--ink); overflow-wrap: anywhere; }
.tc-value { font: 600 13px var(--mono); color: var(--ink); font-variant-numeric: tabular-nums; white-space: nowrap; }
.tc-vs { font: 11px var(--mono); color: var(--muted); white-space: nowrap; }
@media (max-width: 430px) {
  .test-compare li { grid-template-columns: minmax(0, 1fr) auto; }
  .tc-vs { grid-column: 1 / -1; }
}
</style>
