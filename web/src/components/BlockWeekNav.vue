<script setup>
import { computed } from 'vue';

const props = defineProps({
  blocks: { type: Array, required: true },
  weeks: { type: Array, required: true },
  blockId: { type: String, default: '' },
  currentWeek: { type: Number, default: 0 },
});

const count = computed(() => props.weeks.length || 13);
</script>

<template>
  <nav class="bw-nav" aria-label="13-week ribbon">
    <div class="bw-weeks" role="list" :aria-label="`${count} weeks`" :style="{ '--count': count }">
      <RouterLink
        v-for="week in weeks"
        :key="week.n"
        :to="`/cycle/week/${week.n}`"
        class="bw-week"
        :class="[week.kind, { on: week.n === currentWeek }]"
        role="listitem"
        :aria-label="`Week ${week.n}`"
        :title="`Week ${week.n}${week.kind === 'training' ? '' : ` · ${week.kind}`}`"
      >
        <b>{{ week.n }}</b>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.bw-nav {
  margin: 12px 0 20px;
  padding: 6px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: var(--paper, #FFFFFF);
  box-shadow: 0 4px 14px rgba(17, 17, 17, .04);
}
.bw-weeks {
  display: grid;
  grid-template-columns: repeat(var(--count, 13), minmax(0, 1fr));
  gap: 3px;
}
.bw-week {
  min-width: 0;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  background: var(--panel2, #FAF8F5);
  color: var(--ink);
  font: 700 10px var(--mono);
  text-decoration: none;
  border-radius: 4px;
  transition: all .16s var(--ease-out);
}
.bw-week:hover {
  border-color: var(--ink);
  background: #FFFFFF;
}
.bw-week.deload {
  background: repeating-linear-gradient(135deg, rgba(46, 107, 101, .14) 0 3px, #FFFFFF 3px 6px);
  border-color: #2E6B65;
}
.bw-week.test {
  border: 2px solid var(--ink);
}
.bw-week.on {
  background: var(--ink);
  color: #FFFFFF;
  border-color: var(--ink);
}
.bw-week.on.test {
  outline: 2px solid var(--ink);
  outline-offset: 1px;
}
@media (max-width: 880px) {
  .bw-weeks { gap: 2px; }
  .bw-week { font-size: 9px; }
}
@media (max-width: 400px) {
  .bw-week { font-size: 7.5px; border-radius: 2px; }
}
</style>
