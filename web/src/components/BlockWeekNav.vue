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
  return { hyper: 'var(--ct-hyper)', strength: 'var(--ct-strength)', transmute: 'var(--ct-transmute)', peak: 'var(--ct-peak)' }[type] || 'var(--ct-custom)';
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
    <div class="bw-weeks" role="list">
      <RouterLink v-for="week in blockWeeks" :key="week.n" :to="`/cycle/week/${week.n}`" class="bw-week" :class="[week.kind, { on: week.n === currentWeek }]" role="listitem">
        <b>W{{ String(week.n).padStart(2, '0') }}</b>
        <i></i>
        <small v-if="week.kind !== 'training'">{{ week.kind }}</small>
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
.bw-block b { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; background: var(--seg); color: #FFFFFF; font: 700 10px var(--mono); }
.bw-block span { text-transform: uppercase; }
.bw-block.on, .bw-all.on { background: var(--ink); color: #FFFFFF; }
.bw-block.on b { background: #FFFFFF; color: var(--seg); }
.bw-weeks { display: grid; grid-template-columns: repeat(auto-fit, minmax(0, 1fr)); gap: 3px; margin-top: 4px; }
.bw-week { display: grid; place-items: center; gap: 2px; min-height: 40px; border-radius: 9px; font: 700 10px var(--mono); color: var(--muted); }
.bw-week i { width: 5px; height: 5px; border-radius: 50%; background: var(--line); }
.bw-week small { font: 600 7px var(--mono); letter-spacing: .05em; text-transform: uppercase; opacity: .8; }
.bw-week.on { background: var(--accent); color: #FFFFFF; }
.bw-week.on i { background: #FFFFFF; }
.bw-week.deload i { background: var(--ct-deload); }
.bw-week.test i { background: var(--ink); }
.bw-week.test.on i { background: #FFFFFF; }
@media (max-width: 880px) {
  .bw-week { min-height: 38px; }
  .bw-block span { display: none; }
}
</style>
