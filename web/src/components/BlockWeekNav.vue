# BlockWeekNav
<script setup>
import { computed } from 'vue';
const props = defineProps({
  blocks: { type: Array, required: true },
  weeks: { type: Array, required: true },
  blockId: { type: String, default: '' },
  currentWeek: { type: Number, default: 0 },
});
const activeBlock = computed(() => props.blockId || '');
const blockWeeks = computed(() => activeBlock.value ? props.weeks.filter(week => week.blockId === activeBlock.value) : props.weeks);
const tone = id => {
  const type = (props.blocks.find(block => block.id === id)?.cycleType || '').toLowerCase();
  // Literal colours, not var() references: a custom property that holds another
  // var() does not always resolve to a usable background on the chip.
  return { hyper: '#A81A12', strength: '#0D3FA8', transmute: '#6A2F9E', peak: '#7A5200' }[type] || '#55605C';
};
</script>

<template>
  <nav class="bw-nav" aria-label="Block and week selection">
    <div class="bw-blocks">
      <RouterLink to="/cycle" class="bw-all" :class="{ on: !activeBlock }">CYCLE</RouterLink>
      <RouterLink v-for="block in blocks" :key="block.id" :to="`/cycle/block/${block.id}`" class="bw-block" :class="[{ on: activeBlock === block.id }, `ct-${(block.cycleType || 'custom').toLowerCase()}`]" :style="{ '--seg': tone(block.id) }">
        <b>{{ block.id }}</b><span>{{ block.nameEn }}</span>
      </RouterLink>
    </div>
    <div class="bw-weeks" :class="{ dense: blockWeeks.length > 13 }" role="list" :aria-label="`${blockWeeks.length} weeks`" :style="{ '--count': blockWeeks.length }">
      <RouterLink v-for="week in blockWeeks" :key="week.n" :to="`/cycle/week/${week.n}`" class="bw-week" :class="[week.kind, { on: week.n === currentWeek }]" :style="{ '--seg': tone(week.blockId || activeBlock) }" role="listitem" :aria-label="`Week ${week.n}${week.kind === 'training' ? '' : `, ${week.kind}`}`" :title="`Week ${week.n}${week.kind === 'training' ? '' : ` · ${week.kind}`}`">
        <b>{{ week.n }}</b>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.bw-nav { margin: 18px 0 22px; padding: 6px; border: 1px solid var(--line-soft); border-radius: 16px; background: #FFFFFF; box-shadow: 0 10px 26px rgba(17, 17, 17, .05); }
.bw-blocks { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; }
.bw-blocks::-webkit-scrollbar { display: none; }
.bw-all, .bw-block { flex: none; display: flex; align-items: center; gap: 7px; min-height: 38px; padding: 0 11px; border-radius: 10px; font: 700 9px var(--mono); letter-spacing: .06em; color: var(--muted); white-space: nowrap; }
.bw-all { background: var(--panel2); }
.bw-block b { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; background: var(--seg, var(--ct-custom)); color: #FFFFFF; font: 700 10px var(--mono); }
.bw-block span { text-transform: uppercase; }
.bw-block.on, .bw-all.on { background: var(--ink); color: #FFFFFF; }
.bw-block.on b { background: #FFFFFF; color: var(--ink); border: 1px solid var(--seg, var(--ink)); }
/* One row of small squares, never two: each week is one unit of the block and the
   whole block must stay readable at a glance on a 360 px phone, from 9 to 17 weeks. */
.bw-weeks { display: grid; grid-template-columns: repeat(var(--count, 1), minmax(0, 1fr)); gap: 3px; margin-top: 8px; }
.bw-week { min-width: 0; aspect-ratio: 1; display: grid; place-items: center; border: 1px solid var(--seg, var(--accent)); background: #FFFFFF; color: var(--ink); font: 700 9px var(--mono); text-decoration: none; transition: background .16s var(--ease-out), color .16s var(--ease-out); }
.bw-week.dense, .bw-weeks.dense .bw-week { font-size: 8px; }
.bw-week.deload { background: repeating-linear-gradient(135deg, color-mix(in srgb, var(--seg, var(--accent)) 16%, #FFFFFF) 0 3px, #FFFFFF 3px 6px); }
.bw-week.test { border-width: 2px; }
.bw-week.on { background: var(--seg, var(--accent)); color: #FFFFFF; }
.bw-week.on.test { border-color: var(--ink); }
@media (max-width: 880px) {
  .bw-block span { display: none; }
  .bw-weeks { gap: 2px; }
}
@media (max-width: 400px) {
  .bw-week { font-size: 8px; }
  .bw-weeks.dense .bw-week { font-size: 7px; }
}
</style>
