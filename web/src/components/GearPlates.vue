<script setup>
import { computed } from 'vue';
import { solveLoad, sideText, plateLabel, MICRO_SIZES } from '../plate-load.js';

const props = defineProps({
  rows: { type: Array, default: () => [] },
  barKg: { type: Number, default: 20 },
  collarPair: { type: Number, default: 0 },
});

// One line per prescribed load on the bar; a session that repeats the same load
// on two rows should not read as two different setups.
const groups = computed(() => {
  const seen = new Map();
  for (const row of props.rows) {
    if (!row || row.bucket !== 'main' || row.loadKg === null || row.loadKg === undefined) continue;
    const loads = (row.segments || []).map(segment => segment.load).filter(value => value !== null && value !== undefined);
    const values = loads.length ? [...new Set([...loads, row.loadKg])] : [row.loadKg];
    for (const load of values) {
      const key = `${row.nameEn}|${load}`;
      if (seen.has(key)) { seen.get(key).rows.push(row); continue; }
      const solved = solveLoad(load, props.barKg, props.collarPair);
      seen.set(key, { key, movement: row.nameEn, lift: row.lift, load, solved, rows: [row] });
    }
  }
  return [...seen.values()];
});
const anyMicro = computed(() => groups.value.some(group => group.solved.microUsed.length));
const anyAsymmetric = computed(() => groups.value.some(group => group.solved.asymmetric));
</script>

<template>
  <div v-if="groups.length" class="gear-plates" data-testid="gear-plates">
    <p class="gp-lead">
      <template v-if="anyMicro">Micro plates needed for at least one prescribed load.</template>
      <template v-else>Standard plates cover every prescribed load.</template>
      <template v-if="anyAsymmetric"> One load is built with single-side loading; the two sides differ.</template>
      <template v-if="collarPair > 0"> The 5 kg competition collar pair is counted in this breakdown.</template>
      <template v-else> No collars are counted; only the bar is fixed weight.</template>
    </p>
    <article v-for="group in groups" :key="group.key" class="gp-row" :data-load="group.load">
      <header class="gp-head">
        <span class="gp-name">{{ group.movement }}</span>
        <span class="gp-load">{{ plateLabel(group.load) }}<small> kg</small></span>
      </header>
      <p class="gp-side">
        <template v-if="group.solved.asymmetric">
          Side A {{ plateLabel(group.solved.sideA.loaded) }} kg ({{ sideText(group.solved.sideA) }}) ·
          Side B {{ plateLabel(group.solved.sideB.loaded) }} kg ({{ sideText(group.solved.sideB) }})
        </template>
        <template v-else>Per side {{ sideText(group.solved.sideA) }}</template>
        <template v-if="group.solved.shortKg > 0"> · {{ plateLabel(group.solved.shortKg) }} kg of this load cannot be built with the reference stock.</template>
      </p>
      <div class="gp-cabinet" role="list" aria-label="Micro plate cabinet">
        <span
          v-for="size in MICRO_SIZES" :key="size" role="listitem"
          :class="['gp-plate', { on: group.solved.microUsed.includes(size) }]"
          :aria-label="`${plateLabel(size)} kg plate, ${group.solved.microUsed.includes(size) ? 'needed' : 'not needed'}`"
          :style="{ background: `var(--plate-${String(size).replace('.', 'p')})` }"
        >
          <b>{{ plateLabel(size) }}</b><small>kg</small>
        </span>
      </div>
    </article>
  </div>
</template>

<style scoped>
.gear-plates { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--line-soft); }
.gp-lead { margin: 0 0 10px; font-size: 12px; line-height: 1.5; color: var(--muted); }
.gp-row { padding: 8px 0; border-top: 1px solid var(--line-soft); }
.gp-row:first-of-type { border-top: 0; padding-top: 0; }
.gp-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.gp-name { font: 600 13px var(--sans); letter-spacing: -.01em; color: var(--ink); }
.gp-load { font: 700 15px var(--mono); color: var(--ink); font-variant-numeric: tabular-nums; }
.gp-load small { font-size: 9px; color: var(--muted); margin-left: 2px; }
.gp-side { margin: 4px 0 8px; font: 11px/1.6 var(--mono); color: var(--muted); overflow-wrap: anywhere; }
.gp-cabinet { display: flex; flex-wrap: wrap; gap: 4px; }
.gp-plate { display: inline-flex; align-items: baseline; gap: 2px; min-width: 44px; min-height: 24px; padding: 3px 6px; border-radius: 2px; border: 1px solid var(--line2); opacity: .38; filter: grayscale(1); }
.gp-plate.on { opacity: 1; filter: none; border-color: var(--ink); box-shadow: 0 0 0 1px var(--ink) inset; }
.gp-plate b { font: 700 10px var(--mono); color: var(--ink); letter-spacing: -.02em; }
.gp-plate small { font: 8px var(--mono); color: var(--ink); }
</style>
