<script setup>
import { computed, onMounted, ref } from 'vue';
const props = defineProps({ weeks: Array, blocks: Array, perWeek: Array, testDate: String });
const go = ref(false);
onMounted(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) go.value = true;
  else requestAnimationFrame(() => { go.value = true; });
});
const MAX_SETS = 75;
const rows = computed(() => props.perWeek.map(week => ({
  n: week.n,
  sets: week.total,
  top: week.topPct || 0,
  kind: week.kind === 'deload' ? 'deload' : week.kind === 'test' ? 'test' : (props.blocks.find(block => block.id === week.blockId)?.cycleType || 'custom').toLowerCase(),
})));
const maxSets = computed(() => Math.max(MAX_SETS, ...rows.value.map(row => row.sets)));
const hasTop = computed(() => rows.value.some(row => row.top > 0));
const bars = computed(() => rows.value.map((row, i) => ({
  ...row,
  h: Math.max(4, row.sets / maxSets.value * 100).toFixed(2),
  p: Math.max(0, Math.min(100, (row.top - 50) / 60 * 100)),
  x: ((i + .5) / rows.value.length * 100).toFixed(2),
  i,
  label: `Week ${row.n}, ${row.sets} sets, top set ${Math.round(row.top * 10) / 10}% of 1RM`,
})));
const points = computed(() => bars.value.map(bar => `${bar.x},${(100 - bar.p).toFixed(2)}`).join(' '));
const lastTop = computed(() => hasTop.value && rows.value.at(-1).top > 0 ? `${Math.round(rows.value.at(-1).top)}%` : '');
const gridCols = computed(() => `repeat(${rows.value.length}, minmax(0, 1fr))`);
const peak = computed(() => Math.max(...rows.value.map(row => row.sets)));
const peakWeeks = computed(() => rows.value.filter(row => row.sets === peak.value).map(row => row.n));
const deloadWeeks = computed(() => rows.value.filter(row => row.kind === 'deload').map(row => row.n));
const peakNote = computed(() => `Peak weeks ${peakWeeks.value.join(', ')} — ${peak.value} sets`);
const deloadNote = computed(() => deloadWeeks.value.length ? `Deloads ${deloadWeeks.value.join(', ')}` : 'No deloads in this cycle');
const longDate = iso => new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', timeZone: 'Asia/Shanghai' }).format(new Date(`${iso}T00:00:00+08:00`));
const testLine = computed(() => props.testDate ? `Test day ${longDate(props.testDate)}` : 'Test day: not scheduled');
const summary = computed(() => {
  const first = rows.value[0]?.top || 0;
  const last = rows.value.at(-1)?.top || 0;
  const deloads = deloadWeeks.value.length ? ` Deloads in weeks ${deloadWeeks.value.join(', ')}.` : ' No deloads in this cycle.';
  return `Peak weeks are ${peakWeeks.value.join(', and ')}.${deloads} The top set climbs from ${Math.round(first)}% of 1RM in Week 1 to ${Math.round(last)}% on the test day. ${testLine.value}`;
});
</script>

<template>
  <section class="card load" data-testid="load-profile" aria-label="Load profile">
    <div class="load-head"><div><div class="eyebrow">FIG. 1 · LOAD PROFILE</div><h2 class="load-title">Weekly work and top-set intensity across the {{ weeks.length }} weeks</h2></div></div>
    <p class="load-sub">Bars, weekly working sets. Line, the top set as a share of 1RM (scale at left). Week numbers run along the bottom.</p>
    <div class="legend">
      <div class="legend-row"><span class="lg hyper"><i></i>Hypertrophy</span><span class="lg strength"><i></i>Strength</span><span class="lg transmute"><i></i>Transmute</span><span class="lg deload"><i></i>Deload</span></div>
      <div class="legend-row"><span class="lg test"><i></i>Test</span><span class="lg line"><i></i>Top set %1RM</span></div>
    </div>
    <div class="chart">
      <div class="yax" aria-hidden="true"><span style="bottom: 0">50%</span><span style="bottom: 41.67%">75%</span><span style="bottom: 83.33%">100%</span></div>
      <div class="cbody">
        <div class="cplot">
          <div class="grid" aria-hidden="true"><span style="bottom: 0"></span><span style="bottom: 41.67%"></span><span style="bottom: 83.33%"></span></div>
          <div class="bars" :class="{ go }" :style="{ gridTemplateColumns: gridCols }">
            <div v-for="bar in bars" :key="bar.n" :class="['bar', bar.kind]" role="img" :style="{ '--h': bar.h, '--i': bar.i }" :title="bar.label" :aria-label="bar.label"><i></i></div>
          </div>
          <div v-if="hasTop" class="inten" :class="{ go }" aria-hidden="true">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none"><polyline class="iline" :points="points" fill="none" stroke="var(--gold)" stroke-width="1.5" vector-effect="non-scaling-stroke" /></svg>
            <i v-for="bar in bars" :key="bar.n" class="idot" :style="{ left: `${bar.x}%`, bottom: `${bar.p.toFixed(2)}%`, '--i': bar.i }"></i>
            <span v-if="lastTop" class="ptag">{{ lastTop }}</span>
          </div>
        </div>
        <div class="wlabels" :style="{ gridTemplateColumns: gridCols }" aria-hidden="true"><span v-for="bar in bars" :key="bar.n" :class="bar.kind === 'deload' ? 'dl' : bar.kind === 'test' ? 'ts' : ''">{{ bar.n }}</span></div>
      </div>
    </div>
    <p class="sr">{{ summary }}</p>
    <div class="notes">
      <div class="note hyper"><i></i><span>{{ peakNote }}</span></div>
      <div class="note deload"><i></i><span>{{ deloadNote }}</span></div>
      <div class="note test"><i></i><span>{{ testLine }}</span></div>
    </div>
  </section>
</template>

<style scoped>
.load { --dur-slow: .5s; --dur-live: .6s; --dur-stagger: .03s; position: relative; background: transparent; border: 0; border-top: 1px solid var(--ink); border-radius: 0; box-shadow: none; padding: 14px 0 6px; min-width: 0; margin: 22px 0; }
.eyebrow { font-family: var(--mono); font-size: 8.5px; font-weight: 500; letter-spacing: .18em; text-transform: uppercase; color: var(--muted); }
.sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
.load-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.load-fig { font: 9px var(--mono); letter-spacing: .08em; color: var(--muted); border: 1px solid var(--line); padding: 3px 6px; white-space: nowrap; }
.load-title { margin-top: 4px; font-family: var(--serif); font-size: 17px; line-height: 1.3; font-weight: 400; max-width: 34ch; }
.load-sub { margin-top: 5px; font-size: 10.5px; line-height: 1.5; color: var(--muted); max-width: 46ch; }
.legend { display: grid; gap: 4px; margin-top: 10px; }
.legend-row { display: flex; flex-wrap: wrap; gap: 4px 10px; }
.lg { display: flex; align-items: center; gap: 5px; font-size: 9px; color: var(--muted); letter-spacing: .02em; white-space: nowrap; }
.lg i { display: block; width: 7px; height: 7px; border-radius: 2px; background: var(--muted); }
.lg.hyper i { background: var(--ct-hyper); }
.lg.strength i { background: var(--ct-strength); }
.lg.transmute i { background: var(--ct-transmute); }
.lg.deload i { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 2px, var(--ct-deload-s) 2px 4px); }
.lg.test i { background: var(--ct-peak); }
.lg.line i { width: 12px; height: 2px; border-radius: 2px; background: var(--gold); }
.chart { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px; margin-top: 16px; }
.yax { position: relative; width: 26px; height: 124px; font-family: var(--mono); font-size: 8.5px; color: var(--muted); }
.yax span { position: absolute; right: 0; line-height: 1; transform: translateY(50%); }
.cbody { min-width: 0; }
.cplot { position: relative; height: 124px; }
.grid { position: absolute; inset: 0; pointer-events: none; }
.grid span { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--line2); }
.inten { position: absolute; inset: 0 3px; pointer-events: none; z-index: 2; }
.inten svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.iline { opacity: 0; transition: opacity var(--dur-slow) var(--ease-out); }
.idot { position: absolute; width: 4px; height: 4px; margin-left: -2px; margin-bottom: -2px; border-radius: 50%; background: var(--gold); opacity: 0; transition: opacity var(--dur-slow) var(--ease-out); }
.ptag { position: absolute; right: 0; top: -13px; padding: 0 3px; border-radius: 3px; background: var(--panel); font-family: var(--mono); font-size: 8.5px; line-height: 1.4; color: var(--gold); opacity: 0; transition: opacity var(--dur-slow) var(--ease-out); white-space: nowrap; }
.inten.go .iline { opacity: .9; transition-delay: var(--dur-slow); }
.inten.go .idot { opacity: 1; transition-delay: calc(var(--dur-slow) + var(--i) * var(--dur-stagger)); }
.inten.go .ptag { opacity: 1; transition-delay: var(--dur-live); }
.bars { position: relative; z-index: 1; display: grid; gap: 2px; align-items: end; height: 100%; padding: 0 3px; }
.bar { position: relative; display: flex; align-items: flex-end; height: 100%; min-width: 0; }
.bar i { display: block; width: 100%; height: calc(var(--h) * 1%); border-radius: 4px 4px 2px 2px; transform: scaleY(0); transform-origin: bottom; transition: transform var(--dur-slow) var(--ease-out); transition-delay: calc(var(--i) * var(--dur-stagger)); }
.bars.go .bar i { transform: scaleY(1); }
.bar.hyper i { background: var(--ct-hyper); }
.bar.strength i { background: var(--ct-strength); }
.bar.transmute i { background: var(--ct-transmute); }
.bar.peak i { background: var(--ct-peak); }
.bar.custom i { background: var(--ct-custom); }
.bar.deload i { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 3px, var(--ct-deload-s) 3px 6px); opacity: .9; }
.bar.test i { background: var(--ct-peak); box-shadow: 0 0 0 1px var(--ct-peak-s); }
.wlabels { display: grid; gap: 2px; margin-top: 4px; padding: 0 3px; }
.wlabels span { text-align: center; font-family: var(--mono); font-size: 9px; color: var(--muted); line-height: 1; }
.wlabels span.dl { color: var(--ct-deload); }
.wlabels span.ts { color: var(--ct-peak); font-weight: 700; }
.notes { display: grid; gap: 4px; margin-top: 10px; }
.note { display: flex; gap: 8px; font-size: 10px; line-height: 1.45; color: var(--muted); }
.note i { flex: 0 0 3px; border-radius: 2px; background: var(--muted); margin-top: 2px; margin-bottom: 2px; }
.note.hyper i { background: var(--ct-hyper); }
.note.deload i { background: var(--ct-deload); }
.note.test i { background: var(--ct-peak); }
@media (min-width: 600px) {
  .yax, .cplot { height: 148px; }
}
@media (min-width: 900px) {
  .chart { max-width: 700px; }
  .bars { gap: 4px; }
}
@media (prefers-reduced-motion: reduce) {
  .bar i, .iline, .idot, .ptag { transition: none; }
}
</style>