<script setup>
import { computed } from 'vue';
const props = defineProps({
  weeks: { type: Array, required: true },
  blocks: { type: Array, required: true },
  current: { type: Number, default: 0 },
});
const segments = computed(() => props.blocks.map(block => ({
  id: block.id,
  name: block.nameEn,
  type: (block.cycleType || 'custom').toLowerCase(),
  weeks: props.weeks.filter(week => week.blockId === block.id),
})).filter(segment => segment.weeks.length));
const range = segment => `W${String(segment.weeks[0].n).padStart(2, '0')}–W${String(segment.weeks.at(-1).n).padStart(2, '0')}`;
const summary = computed(() => segments.value.map(segment => `${segment.name}: ${range(segment)}, ${segment.weeks.length} weeks`).join('. '));
</script>

<template>
  <div class="cycle-strip" data-testid="cycle-strip">
    <div class="strip-track" role="img" :aria-label="`Cycle phases. ${summary}`">
      <div v-for="segment in segments" :key="segment.id" class="strip-segment" :class="`ct-${segment.type}`" :style="{ flexGrow: segment.weeks.length }">
        <i v-for="week in segment.weeks" :key="week.n" :class="[week.kind, { on: week.n === current }]"></i>
      </div>
    </div>
    <div class="strip-labels" aria-hidden="true">
      <div v-for="segment in segments" :key="segment.id" class="strip-label" :class="`ct-${segment.type}`" :style="{ flexGrow: segment.weeks.length }">
        <b>{{ segment.id }}</b>
        <span>{{ segment.name }}</span>
        <small>{{ range(segment) }} · {{ segment.weeks.length }} WK</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cycle-strip { margin: 14px 0 6px; }
.strip-track { display: flex; gap: 3px; height: 14px; }
.strip-segment { display: flex; gap: 2px; min-width: 0; flex-basis: 0; }
.strip-segment i { flex: 1; min-width: 2px; background: var(--seg); }
.strip-segment i.deload { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 3px, var(--ct-deload-s) 3px 6px); }
.strip-segment i.test { background: var(--ct-peak); }
.strip-segment i.on { outline: 2px solid var(--ink); outline-offset: 1px; }
.ct-hyper { --seg: var(--ct-hyper); --seg-text: var(--ct-hyper); }
.ct-strength { --seg: var(--ct-strength); --seg-text: var(--ct-strength); }
.ct-transmute { --seg: var(--ct-transmute); --seg-text: var(--ct-transmute); }
.ct-peak { --seg: var(--ct-peak); --seg-text: var(--ct-peak); }
.ct-custom { --seg: var(--ct-custom); --seg-text: var(--ct-custom); }
.ct-deload { --seg: var(--ct-deload); --seg-text: var(--ct-deload); }
.strip-labels { display: flex; gap: 3px; margin-top: 7px; }
.strip-label { flex-basis: 0; min-width: 0; border-top: 2px solid var(--seg); padding-top: 5px; }
.strip-label b { font: 700 9px var(--mono); color: var(--seg-text); }
.strip-label span { display: block; font-size: 8.5px; letter-spacing: .04em; text-transform: uppercase; color: var(--ink); line-height: 1.35; overflow-wrap: anywhere; }
.strip-label small { display: block; font: 8px var(--mono); color: var(--muted); margin-top: 2px; white-space: nowrap; }
@media (max-width: 420px) {
  .strip-label span { display: none; }
}
</style>