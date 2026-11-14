<script setup>
import { computed } from 'vue';
const props = defineProps({ week: Object, ranges: Object });
const lifts = { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT' };
const liftColor = { S: 'var(--main)', B: 'var(--variation)', D: 'var(--accessory)' };
const scale = computed(() => Math.max(
  ...Object.values(props.week.equivalent).map(lift => lift.main + lift.var),
  props.week.roles.accessory,
  ...Object.values(props.ranges.sbd).map(range => range.mrv || 0),
  1,
));
const display = value => Number(value).toFixed(1);
const pct = value => `${value / scale.value * 100}%`;
</script>

<template>
  <section class="week-capacity" aria-label="Weekly capacity">
    <div class="section-kicker"><span>WEEKLY CAPACITY</span><span>SBD EQUIVALENT</span></div>
    <div v-for="(label, code) in lifts" :key="code" class="volume-row">
      <header><span>{{ label }}</span><small>MEV {{ ranges.sbd[code].mev }} / MRV {{ ranges.sbd[code].mrv }}</small><strong :data-testid="`equivalent-${code}`">{{ display(week.equivalent[code].total) }}</strong></header>
      <div class="cap-track" :style="{ '--lift': liftColor[code] }">
        <span v-if="ranges.sbd[code].mev !== null && ranges.sbd[code].mrv !== null" class="cap-band" :style="{ left: pct(ranges.sbd[code].mev), width: pct(ranges.sbd[code].mrv - ranges.sbd[code].mev) }" aria-hidden="true"></span>
        <i class="cap-main" :style="{ width: pct(week.equivalent[code].main) }"></i>
        <i class="cap-var" :style="{ width: pct(week.equivalent[code].var) }"></i>
        <span v-if="ranges.sbd[code].mev !== null" class="cap-tick mev" :style="{ left: pct(ranges.sbd[code].mev) }" aria-hidden="true"></span>
        <span v-if="ranges.sbd[code].mrv !== null" class="cap-tick mrv" :style="{ left: pct(ranges.sbd[code].mrv) }" aria-hidden="true"></span>
      </div>
      <p class="micro-copy">{{ week.lifts[code].main }} main + {{ week.lifts[code].var }} variation working sets<span v-if="week.equivalent[code].unknown"> · {{ week.equivalent[code].unknown }} sets excluded: transfer unknown</span></p>
    </div>
    <div class="volume-row"><header><span>ACCESSORY</span><small>NO SBD EQUIVALENT</small><strong>{{ week.roles.accessory }}</strong></header><div class="cap-track"><i class="cap-main" style="--lift: var(--ink)" :style="{ width: pct(week.roles.accessory) }"></i></div></div>
    <div v-if="week.roles.nonSbdVar" class="volume-row"><header><span>OTHER VARIATIONS</span><small>OUTSIDE SBD</small><strong>{{ week.roles.nonSbdVar }}</strong></header></div>
    <div class="total-row"><span>ALL GROUPS</span><strong data-testid="weekly-total">{{ week.total }}</strong></div>
    <div class="cap-legend" aria-hidden="true">
      <span><i class="lg-solid"></i>MAIN</span>
      <span><i class="lg-hatch"></i>EQUIV. VAR</span>
      <span><i class="lg-band"></i>MEV–MRV</span>
      <span><i class="lg-tick"></i>MRV TICK</span>
    </div>
    <p class="micro-copy">Solid · main &nbsp; Hatched · equivalent variation. Approved transfer factors apply only to SBD capacity, not working sets, muscle weighting or completion. Legacy prescriptions retain their original 1:1 basis. MEV/MRV are reference ranges, not targets.</p>
  </section>
</template>

<style scoped>
.cap-track { position: relative; display: flex; height: 16px; margin-top: 8px; background: var(--panel2); border: 1px solid var(--line-soft); overflow: hidden; }
.cap-main { height: 100%; background: var(--lift, var(--ink)); }
.cap-var { height: 100%; background: repeating-linear-gradient(135deg, var(--lift, var(--muted)) 0 3px, transparent 3px 6px); }
.cap-band { position: absolute; top: 0; bottom: 0; border-left: 1px dashed var(--muted); border-right: 1px dashed var(--muted); background: color-mix(in srgb, var(--lift, var(--ink)) 6%, transparent); pointer-events: none; }
.cap-tick { position: absolute; top: -1px; bottom: -1px; width: 1px; background: var(--muted); pointer-events: none; }
.cap-tick.mrv { width: 2px; background: var(--ink); }
.cap-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; font: 9px var(--mono); letter-spacing: .06em; color: var(--muted); }
.cap-legend span { display: inline-flex; align-items: center; gap: 5px; }
.cap-legend i { display: inline-block; width: 14px; height: 8px; }
.lg-solid { background: var(--ink); }
.lg-hatch { background: repeating-linear-gradient(135deg, var(--muted) 0 3px, transparent 3px 6px); border: 1px solid var(--line-soft); }
.lg-band { border-left: 1px dashed var(--muted); border-right: 1px dashed var(--muted); background: var(--panel2); }
.lg-tick { width: 2px; background: var(--ink); }
</style>