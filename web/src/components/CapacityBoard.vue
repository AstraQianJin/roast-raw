<script setup>
import { computed } from 'vue';
const props = defineProps({ analysis: Object, week: Object });
const lifts = { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT' };
const peak = computed(() => Math.max(...Object.values(props.analysis.cycle.lifts).map(lift => lift.main + lift.var), 1));
const display = value => Number(value).toFixed(1);
</script>

<template>
  <section class="capacity-board" aria-label="Capacity board">
    <div class="section-kicker"><span>CAPACITY</span><span>ALL {{ analysis.weeks }} WEEKS</span></div>
    <h2>Working sets.<br><em>The cycle in focus.</em></h2>
    <div class="board-total"><strong>{{ analysis.cycle.total }}</strong><span>SETS<br>{{ display(analysis.cycle.tonnageKg / 1000) }} t · {{ analysis.cycle.auxSets }} AUX SETS</span></div>
    <div class="cycle-lifts">
      <div v-for="(label, code) in lifts" :key="code" class="cycle-lift">
        <span>{{ label }}</span><strong>{{ analysis.cycle.lifts[code].main + analysis.cycle.lifts[code].var }}</strong>
        <div class="cycle-bar" aria-hidden="true"><i :style="{ height: `${analysis.cycle.lifts[code].main / peak * 100}%` }"></i><i :style="{ height: `${analysis.cycle.lifts[code].var / peak * 100}%` }"></i></div>
        <small>{{ analysis.cycle.lifts[code].main }} MAIN / {{ analysis.cycle.lifts[code].var }} VAR</small>
      </div>
    </div>
    <p class="annotation">Six groups · W{{ String(week.n).padStart(2, '0') }}</p>
    <table class="group-table"><thead><tr><th>GROUP</th><th>WEIGHTED</th><th>DIRECT</th><th>RANGE</th></tr></thead><tbody><tr v-for="group in analysis.groups" :key="group"><td>{{ group.toUpperCase() }}</td><td>{{ display(week.groups[group].w) }}</td><td>{{ week.groups[group].d }}</td><td>{{ analysis.ranges.groups[group].weekly_range.join('–') }}</td></tr></tbody></table>
    <p class="micro-copy">Group weighting uses the maximum coefficient within each group, never the sum. Group direct sets follow each exercise’s assigned group.</p>
  </section>
</template>
