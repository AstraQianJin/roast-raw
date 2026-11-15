<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  analysis: { type: Object, default: () => ({}) },
  performance: { type: Object, default: () => ({}) },
});

const lifts = [
  { code: 'S', name: 'Squat', style: 'squat' },
  { code: 'B', name: 'Bench', style: 'bench' },
  { code: 'D', name: 'Deadlift', style: 'deadlift' },
];
const finite = value => typeof value === 'number' && Number.isFinite(value);
const validWeek = value => Number.isInteger(value) && value > 0;
const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const display = value => finite(value) ? numberFormat.format(value) : '—';
const supplied = value => value !== null && value !== undefined && value !== '' ? value : 'Not supplied';
const weekLabel = n => `W${String(n).padStart(2, '0')}`;
const estimateLabel = record => record.estimated === true
  ? 'Estimated'
  : record.estimated === false ? 'Actual single' : 'Estimate status not supplied';

// Internal ids look like `S.Main|low-bar squat`. The namespace before the bar is plumbing,
// never interface copy: show the movement name and keep the full id in the detail line.
const movementLabel = id => String(id).split('|').pop().replace(/\b\w/g, letter => letter.toUpperCase());
const capacityWeeks = computed(() => Array.isArray(props.analysis?.perWeek)
  ? props.analysis.perWeek.filter(week => week && validWeek(week.n)) : []);
const movements = computed(() => Array.isArray(props.performance?.movements)
  ? props.performance.movements.filter(movement => movement && typeof movement.id === 'string') : []);
const selectedId = ref('');

watch(movements, entries => {
  if (!entries.some(movement => movement.id === selectedId.value)) {
    selectedId.value = entries.find(movement => movement.id === 'S.Main|high-bar squat')?.id
      ?? entries[0]?.id ?? '';
  }
}, { immediate: true });

const selectedMovement = computed(() => movements.value.find(movement => movement.id === selectedId.value));
const systemTotal = computed(() => selectedMovement.value?.system === true);
const performanceWeeks = computed(() => Array.isArray(selectedMovement.value?.weekly)
  ? selectedMovement.value.weekly.filter(record => record && validWeek(record.n)) : []);

// Missing weeks are axis slots, not observations. No values are synthesized here.
const weekNumbers = computed(() => {
  let last = validWeek(props.analysis?.weeks) ? props.analysis.weeks : 0;
  for (const week of capacityWeeks.value) last = Math.max(last, week.n);
  for (const record of performanceWeeks.value) last = Math.max(last, record.n);
  return Array.from({ length: last }, (_, index) => index + 1);
});
const capacityByWeek = computed(() => new Map(capacityWeeks.value.map(week => [week.n, week])));
const performanceByWeek = computed(() => new Map(performanceWeeks.value.map(record => [record.n, record])));
const capacityRows = computed(() => weekNumbers.value.map(n => ({ n, data: capacityByWeek.value.get(n) })));
const performanceSlots = computed(() => weekNumbers.value.map(n => ({
  n, record: performanceByWeek.value.get(n),
})));
const performanceRecords = computed(() => performanceSlots.value
  .filter(slot => finite(slot.record?.value)).map(slot => slot.record));
const missingPerformanceWeeks = computed(() => performanceSlots.value
  .filter(slot => !finite(slot.record?.value)).map(slot => weekLabel(slot.n)));
const hasCapacity = computed(() => capacityWeeks.value.some(week =>
  lifts.some(lift => finite(week.equivalent?.[lift.code]?.total))));

const plot = { left: 58, right: 542, top: 18, bottom: 202 };
const x = n => weekNumbers.value.length > 1
  ? plot.left + (n - 1) / (weekNumbers.value.length - 1) * (plot.right - plot.left)
  : (plot.left + plot.right) / 2;
const y = (value, scale) => plot.bottom
  - (value - scale.min) / (scale.max - scale.min) * (plot.bottom - plot.top);

// These bounds only place API values on the SVG; they do not calculate training metrics.
const capacityScale = computed(() => {
  let min = 0;
  let max = 0;
  for (const week of capacityWeeks.value) {
    for (const lift of lifts) {
      const value = week.equivalent?.[lift.code]?.total;
      if (finite(value)) {
        min = Math.min(min, value);
        max = Math.max(max, value);
      }
    }
  }
  return { min, max: max === min ? min + 1 : max };
});
const performanceScale = computed(() => {
  if (!performanceRecords.value.length) return null;
  let min = Infinity;
  let max = -Infinity;
  for (const record of performanceRecords.value) {
    min = Math.min(min, record.value);
    max = Math.max(max, record.value);
  }
  const padding = max === min ? Math.max(Math.abs(min) * 0.08, 1) : (max - min) * 0.12;
  return { min: min - padding, max: max + padding };
});
const ticks = scale => [scale.min, (scale.min + scale.max) / 2, scale.max];
const weekTicks = computed(() => {
  const count = weekNumbers.value.length;
  if (!count) return [];
  if (count < 4) return weekNumbers.value;
  return [1, Math.ceil(count / 2), count];
});

function pathFor(slots, valueFor, scale) {
  let path = '';
  let connected = false;
  for (const slot of slots) {
    const value = valueFor(slot);
    if (!finite(value)) {
      connected = false;
      continue;
    }
    path += `${connected ? ' L' : ' M'}${x(slot.n).toFixed(2)},${y(value, scale).toFixed(2)}`;
    connected = true;
  }
  return path.trim();
}

const capacityCurves = computed(() => lifts.map(lift => ({
  ...lift,
  path: pathFor(capacityRows.value, slot => slot.data?.equivalent?.[lift.code]?.total, capacityScale.value),
  points: capacityRows.value.filter(slot => finite(slot.data?.equivalent?.[lift.code]?.total))
    .map(slot => ({ n: slot.n, value: slot.data.equivalent[lift.code].total })),
})));
const performancePath = computed(() => performanceScale.value
  ? pathFor(performanceSlots.value, slot => slot.record?.value, performanceScale.value) : '');
const capacityDescription = computed(() =>
  `Weekly squat, bench and deadlift equivalent capacity across ${weekNumbers.value.length} weeks. `
  + 'Main sets plus discounted variation sets; not muscle-weighted volume. Gaps mean unavailable values. '
  + 'Every weekly value, raw working-set count and tonnage is listed below.');
const performanceDescription = computed(() =>
  `Recorded performance for movement ID ${selectedId.value}, in ${systemTotal.value ? 'total system kilograms' : 'kilograms'}. `
  + 'Only API-reported observations are plotted. Lines break at unobserved weeks. '
  + 'Hollow markers are estimated; filled markers are actual singles. This is not goal attainment. '
  + 'Exact methods and source records are listed below.');
</script>

<template>
  <section class="trend-view" data-testid="trend-view" aria-label="Cycle capacity and recorded performance trends">
    <header class="trend-heading">
      <div class="section-kicker">
        <span>CYCLE TRENDS</span>
        <span>{{ weekNumbers.length ? `ALL ${weekNumbers.length} WEEKS` : 'WAITING FOR DATA' }}</span>
      </div>
      <h2>The work.<br><em>The recorded result.</em></h2>
      <p class="reading-note">Capacity describes the work. Recorded performance describes a result. Neither is a completion score.</p>
    </header>

    <section class="trend-section" data-testid="capacity-trend" aria-label="Weekly SBD equivalent capacity">
      <header class="chart-heading">
        <h3>SBD equivalent capacity</h3>
        <span class="unit-label">EQUIVALENT SETS / WEEK</span>
      </header>
      <p class="reading-note">Main + discounted variation sets, using the API’s transfer basis. Raw working sets, SBD equivalents and muscle-weighted volume are separate measures.</p>
      <ul class="chart-legend" aria-label="Capacity curve key">
        <li v-for="lift in lifts" :key="lift.code"><i class="line-key" :class="lift.style" aria-hidden="true"></i>{{ lift.code }} · {{ lift.name }}</li>
      </ul>
      <figure v-if="hasCapacity" class="chart-figure">
        <svg viewBox="0 0 560 238" role="img" :aria-label="capacityDescription">
          <title>Weekly SBD equivalent capacity</title>
          <desc>{{ capacityDescription }}</desc>
          <g aria-hidden="true">
            <g v-for="tick in ticks(capacityScale)" :key="tick">
              <line class="grid-line" :x1="plot.left" :x2="plot.right" :y1="y(tick, capacityScale)" :y2="y(tick, capacityScale)" />
              <text class="axis-text" :x="plot.left - 9" :y="y(tick, capacityScale) + 4" text-anchor="end">{{ display(tick) }}</text>
            </g>
            <text v-for="n in weekTicks" :key="n" class="axis-text" :x="x(n)" y="224" text-anchor="middle">{{ weekLabel(n) }}</text>
            <g v-for="curve in capacityCurves" :key="curve.code" :class="curve.style">
              <path class="trend-line" :d="curve.path" />
              <circle v-for="point in curve.points" :key="point.n" class="capacity-point" :cx="x(point.n)" :cy="y(point.value, capacityScale)" r="3.5">
                <title>{{ weekLabel(point.n) }} · {{ curve.name }} · {{ display(point.value) }} equivalent sets</title>
              </circle>
            </g>
          </g>
        </svg>
        <figcaption>Weeks on the horizontal axis; equivalent sets on the vertical axis. Missing values leave a gap, not a zero.</figcaption>
      </figure>
      <p v-else class="empty-note">No weekly equivalent-capacity data available.</p>

      <details v-if="capacityRows.length" class="weekly-reading">
        <summary>Weekly source values · {{ weekNumbers.length }} weeks</summary>
        <p class="reading-note">Each total below is the plotted API value. Main and discounted variation contributions are shown separately; unknown-transfer sets are excluded.</p>
        <ol class="capacity-list" aria-label="Weekly capacity values and working-set context">
          <li v-for="slot in capacityRows" :key="slot.n" class="capacity-week">
            <header class="week-reading-heading">
              <strong>{{ weekLabel(slot.n) }}</strong>
              <p>Raw working sets <b>{{ display(slot.data?.total) }}</b><span class="context-divider"> · </span>Tonnage <b>{{ display(slot.data?.tonnageKg) }} kg</b></p>
            </header>
            <dl class="lift-readings">
              <div v-for="lift in lifts" :key="lift.code">
                <dt>{{ lift.code }} · {{ lift.name }}</dt>
                <dd class="equivalent-value">{{ display(slot.data?.equivalent?.[lift.code]?.total) }} <small>eq sets</small></dd>
                <dd class="contribution">{{ display(slot.data?.equivalent?.[lift.code]?.main) }} main<br>{{ display(slot.data?.equivalent?.[lift.code]?.var) }} discounted var</dd>
                <dd v-if="finite(slot.data?.equivalent?.[lift.code]?.unknown) && slot.data.equivalent[lift.code].unknown > 0" class="contribution">{{ display(slot.data.equivalent[lift.code].unknown) }} raw sets excluded · transfer unknown</dd>
                <dd v-if="finite(slot.data?.topPctByLift?.[lift.code])" class="contribution">Top prescribed {{ display(slot.data.topPctByLift[lift.code]) }}% 1RM</dd>
              </div>
            </dl>
          </li>
        </ol>
      </details>
      <p class="reading-note basis-note">{{ props.analysis?.tonnageBasis || 'Tonnage is API-reported in kilograms; it is not equivalent capacity or muscle-weighted volume.' }} A dash means unavailable, never zero.</p>
    </section>

    <section class="trend-section performance-section" data-testid="performance-trend" aria-label="Recorded movement performance">
      <header class="chart-heading">
        <h3>Recorded performance</h3>
        <span class="unit-label">{{ systemTotal ? 'SYSTEM TOTAL · KG' : 'RECORDED VALUE · KG' }}</span>
      </header>
      <p class="reading-note">API-reported actual singles and estimated 1RM values only. Estimates are not goal attainment and never automatically update a plan or reference 1RM.</p>
      <label class="movement-control">
        <span>Recorded movement</span>
        <select v-model="selectedId" data-testid="performance-movement" :disabled="!movements.length">
          <option v-if="!movements.length" value="">No recorded movements</option>
          <option v-for="movement in movements" :key="movement.id" :value="movement.id">{{ movement.name || movementLabel(movement.id) }}</option>
        </select>
      </label>
      <div v-if="selectedMovement" class="movement-context">
        <p>{{ selectedMovement.name || selectedMovement.id }}</p>
        <p>Exact movement ID <code>{{ selectedMovement.id }}</code></p>
        <p>Lift {{ supplied(selectedMovement.lift) }} · {{ systemTotal ? 'System total: bodyweight + external adjustment, in kg.' : 'Recorded load basis, in kg.' }} Distinct movement IDs stay separate.</p>
      </div>

      <template v-if="performanceRecords.length">
        <ul class="chart-legend performance-key" aria-label="Performance observation key">
          <li><i class="dot-key actual" aria-hidden="true"></i>Actual single</li>
          <li><i class="dot-key estimated" aria-hidden="true"></i>Estimated</li>
        </ul>
        <figure class="chart-figure">
          <svg viewBox="0 0 560 238" role="img" :aria-label="performanceDescription">
            <title>Recorded performance · {{ selectedMovement.id }}</title>
            <desc>{{ performanceDescription }}</desc>
            <g aria-hidden="true">
              <g v-for="tick in ticks(performanceScale)" :key="tick">
                <line class="grid-line" :x1="plot.left" :x2="plot.right" :y1="y(tick, performanceScale)" :y2="y(tick, performanceScale)" />
                <text class="axis-text" :x="plot.left - 9" :y="y(tick, performanceScale) + 4" text-anchor="end">{{ display(tick) }}</text>
              </g>
              <text v-for="n in weekTicks" :key="n" class="axis-text" :x="x(n)" y="224" text-anchor="middle">{{ weekLabel(n) }}</text>
              <path class="trend-line performance-line" :d="performancePath" />
              <circle v-for="record in performanceRecords" :key="record.n" class="performance-point" :class="{ estimated: record.estimated === true, actual: record.estimated === false }" :cx="x(record.n)" :cy="y(record.value, performanceScale)" r="4.5">
                <title>{{ weekLabel(record.n) }} · {{ display(record.value) }} kg · {{ estimateLabel(record) }} · {{ supplied(record.method) }}</title>
              </circle>
            </g>
          </svg>
          <figcaption>Observed value in {{ systemTotal ? 'system-total kg' : 'kg' }} by week. The line connects adjacent observed weeks only; it is not a target or achievement curve.</figcaption>
        </figure>
        <p v-if="missingPerformanceWeeks.length" class="reading-note missing-weeks">No recorded value: {{ missingPerformanceWeeks.join(', ') }}. These weeks are not plotted as zero.</p>
        <div class="recorded-reading">
          <h4>Source records</h4>
          <ol class="performance-records" data-testid="performance-records" aria-label="Recorded performance values and methods">
            <li v-for="record in performanceRecords" :key="record.n" class="performance-record">
              <header>
                <strong>{{ weekLabel(record.n) }}</strong>
                <b>{{ display(record.value) }} <small>{{ systemTotal ? 'kg system total' : 'kg' }}</small></b>
                <span class="record-badge" :class="{ estimated: record.estimated === true }">{{ estimateLabel(record) }}</span>
              </header>
              <dl class="record-fields">
                <div><dt>Recorded method</dt><dd><code>{{ supplied(record.method) }}</code></dd></div>
                <div><dt>Record date</dt><dd>{{ supplied(record.date) }}</dd></div>
                <div><dt>{{ systemTotal ? 'Logged system total' : 'Logged load' }}</dt><dd>{{ display(record.load) }} kg</dd></div>
                <div><dt>Logged reps / RPE</dt><dd>{{ display(record.reps) }} reps / {{ display(record.rpe) }} RPE</dd></div>
                <div class="record-key"><dt>Source key</dt><dd><code>{{ supplied(record.key) }}</code></dd></div>
              </dl>
            </li>
          </ol>
        </div>
      </template>
      <p v-else class="empty-note" data-testid="performance-empty">No recorded performance{{ selectedMovement ? ' for this movement' : '' }}. Unobserved weeks remain unknown; no zero or estimate is substituted.</p>
    </section>
  </section>
</template>

<style scoped>
.trend-view { min-width: 0; max-width: 100%; margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--accent); overflow-wrap: anywhere; }
.trend-heading .section-kicker { color: var(--accent); flex-wrap: wrap; }
.trend-heading h2 { font-family: var(--display); font-weight: 800; text-transform: uppercase; font-size: clamp(30px, 5vw, 42px); }
.trend-heading h2 em { color: var(--muted); }
.reading-note, .chart-figure figcaption, .movement-context { font-size: 12px; line-height: 1.65; color: var(--muted); }
.reading-note { margin-top: 10px; }
.trend-section { min-width: 0; margin-top: 26px; padding: 20px 16px; background: var(--panel); border: 1px solid var(--line); }
.chart-heading { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 10px; }
.chart-heading h3 { font-family: var(--display); font-weight: 800; text-transform: uppercase; font-size: clamp(25px, 4vw, 32px); }
.unit-label { color: var(--muted); font: 10px/1.6 var(--mono); letter-spacing: .04em; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 12px 20px; list-style: none; padding: 0; margin: 18px 0 12px; font-size: 12px; }
.chart-legend li { display: flex; align-items: center; gap: 7px; min-width: 0; }
.line-key { display: inline-block; width: 24px; border-top: 2px solid var(--main); }
.line-key.bench { border-color: var(--variation); border-top-style: dashed; }
.line-key.deadlift { border-color: var(--ink); border-top-style: dotted; }
.chart-figure { min-width: 0; margin: 0; }
.chart-figure svg { display: block; width: 100%; max-width: 100%; height: auto; overflow: hidden; }
.chart-figure figcaption { padding: 8px 0 14px; border-bottom: 1px solid var(--line); }
.grid-line { stroke: var(--line-soft); stroke-width: 1; vector-effect: non-scaling-stroke; }
.axis-text { fill: var(--muted); font: 12px var(--mono); }
.trend-line { fill: none; stroke: var(--main); stroke-width: 2; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.bench .trend-line { stroke: var(--variation); stroke-dasharray: 6 4; }
.deadlift .trend-line { stroke: var(--ink); stroke-dasharray: 2 4; }
.capacity-point { fill: var(--main); stroke: var(--panel); stroke-width: 1; vector-effect: non-scaling-stroke; }
.bench .capacity-point { fill: var(--variation); }
.deadlift .capacity-point { fill: var(--ink); }
.weekly-reading, .recorded-reading { margin-top: 20px; }
.weekly-reading summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; color: var(--ink); font-size: 12px; }
h4 { margin: 0; font: 600 11px/1.5 var(--sans); letter-spacing: .07em; text-transform: uppercase; }
.capacity-list, .performance-records { list-style: none; padding: 0; margin: 12px 0 0; }
.capacity-week { padding: 16px 0; border-top: 1px solid var(--line); }
.week-reading-heading { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 14px; }
.week-reading-heading > strong { font: 600 15px var(--mono); }
.week-reading-heading p { color: var(--muted); font-size: 12px; }
.week-reading-heading b { color: var(--ink); font-size: 12px; }
.lift-readings { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 12px 0 0; }
.lift-readings > div { min-width: 0; }
.lift-readings dt { font: 10px/1.5 var(--sans); color: var(--muted); }
.lift-readings dd { margin: 0; }
.equivalent-value { padding: 3px 0; font: 600 20px/1.4 var(--mono); }
.equivalent-value small { font: 10px var(--sans); color: var(--muted); white-space: nowrap; }
.contribution { font: 11px/1.65 var(--mono); color: var(--muted); }
.basis-note { padding-top: 10px; border-top: 1px solid var(--line); }
.movement-control { display: block; min-width: 0; margin-top: 18px; font-size: 12px; color: var(--muted); }
.movement-control select { display: block; width: 100%; min-width: 0; max-width: 100%; min-height: 44px; margin-top: 6px; padding: 10px 8px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--panel); font: 12px var(--sans); }
.movement-control select:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.movement-control select:disabled { opacity: 1; color: var(--muted); background: var(--panel2); }
.movement-context { margin-top: 12px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.movement-context p + p { margin-top: 4px; }
.movement-context p:first-child { color: var(--ink); font-size: 14px; }
code { color: var(--ink); font-family: var(--mono); white-space: normal; overflow-wrap: anywhere; }
.dot-key { width: 10px; height: 10px; display: inline-block; border: 2px solid var(--accent); border-radius: 50%; flex-shrink: 0; }
.dot-key.actual { background: var(--ink); border-color: var(--ink); }
.dot-key.estimated { background: var(--panel); }
.performance-line { stroke: var(--muted); stroke-dasharray: 4 4; }
.performance-point { fill: var(--panel); stroke: var(--muted); stroke-width: 2; vector-effect: non-scaling-stroke; }
.performance-point.estimated { fill: var(--panel); stroke: var(--accent); }
.performance-point.actual { fill: var(--ink); stroke: var(--ink); }
.missing-weeks { margin-top: 12px; }
.performance-record { padding: 16px 0; border-top: 1px solid var(--line); }
.performance-record > header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 12px; }
.performance-record > header > strong { font-size: 13px; }
.performance-record > header > b { font-size: 21px; }
.performance-record small { color: var(--muted); font: 11px var(--sans); }
.record-badge { border: 1px solid var(--line); padding: 3px 6px; font: 10px/1.5 var(--sans); }
.record-badge.estimated { color: var(--accent); border-color: var(--accent); }
.record-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 18px; margin: 14px 0 0; }
.record-fields > div { min-width: 0; }
.record-fields dt { font-size: 10px; color: var(--muted); }
.record-fields dd { margin: 3px 0 0; font: 12px/1.65 var(--mono); }
.record-fields .record-key { grid-column: 1 / -1; }
.empty-note { padding: 18px 0; margin-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; line-height: 1.65; }
@media (max-width: 390px) {
  .trend-section { padding: 16px 10px; }
  .chart-heading { gap: 6px; }
  .unit-label { flex-basis: 100%; }
  .chart-legend { gap: 10px 12px; font-size: 11px; }
  .week-reading-heading p { flex-basis: 100%; }
  .context-divider { display: block; height: 4px; font-size: 0; }
  .lift-readings { gap: 7px; }
  .equivalent-value { font-size: 18px; }
  .equivalent-value small { display: block; margin-top: 2px; }
  .contribution { font-size: 10px; }
  .record-fields { grid-template-columns: minmax(0, 1fr); }
}
</style>
