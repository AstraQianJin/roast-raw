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
    <div class="strip-rail" role="list" :aria-label="`Weeks in this cycle. ${summary}`">
      <div v-for="segment in segments" :key="segment.id" class="strip-segment" :class="`ct-${segment.type}`" :style="{ flexGrow: segment.weeks.length }" role="group" :aria-label="`${segment.name}, ${range(segment)}`">
        <RouterLink v-for="week in segment.weeks" :key="week.n" :to="`/plan/week/${week.n}`" class="strip-week" :class="[week.kind, { on: week.n === current }]" role="listitem" :title="`${segment.name} · Week ${week.n}`" :aria-label="`Week ${week.n}, ${segment.name}`">
          <span>{{ week.n }}</span>
        </RouterLink>
      </div>
    </div>
    <div class="strip-key" aria-hidden="true">
      <div v-for="segment in segments" :key="segment.id" class="strip-key-item" :class="`ct-${segment.type}`">
        <i></i><b>{{ segment.id }}</b><span>{{ range(segment) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cycle-strip { margin: 16px 0 8px; }
.strip-rail { display: flex; gap: 10px; }
.strip-segment { display: flex; gap: 2px; min-width: 0; flex-basis: 0; flex-grow: var(--grow, 1); }
.strip-week { display: grid; place-items: center; flex: 1; min-width: 0; aspect-ratio: 1; border: 1px solid var(--seg); color: var(--seg-text); background: var(--seg-s); font: 600 9px var(--mono); line-height: 1; text-decoration: none; }
.strip-week.deload { background: repeating-linear-gradient(135deg, var(--ct-deload-s) 0 3px, transparent 3px 6px); }
.strip-week.test { border-width: 2px; }
.strip-week.on { background: var(--seg); color: var(--bg); }
.strip-week:hover { background: var(--seg); color: var(--bg); }
.ct-hyper { --seg: var(--ct-hyper); --seg-text: var(--ct-hyper); --seg-s: var(--ct-hyper-s); }
.ct-strength { --seg: var(--ct-strength); --seg-text: var(--ct-strength); --seg-s: var(--ct-strength-s); }
.ct-transmute { --seg: var(--ct-transmute); --seg-text: var(--ct-transmute); --seg-s: var(--ct-transmute-s); }
.ct-peak { --seg: var(--ct-peak); --seg-text: var(--ct-peak); --seg-s: var(--ct-peak-s); }
.ct-custom { --seg: var(--ct-custom); --seg-text: var(--ct-custom); --seg-s: var(--ct-custom-s); }
.ct-deload { --seg: var(--ct-deload); --seg-text: var(--ct-deload); --seg-s: var(--ct-deload-s); }
.strip-key { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; }
.strip-key-item { display: flex; align-items: baseline; gap: 4px; font: 9px var(--mono); color: var(--muted); }
.strip-key-item i { width: 6px; height: 6px; background: var(--seg); align-self: center; }
.strip-key-item b { color: var(--seg-text); font-weight: 700; }
.strip-key-item span { letter-spacing: .02em; }
@media (max-width: 560px) {
  .strip-segment { --grow: 1; }
  .strip-key-item span { display: none; }
}
</style>
