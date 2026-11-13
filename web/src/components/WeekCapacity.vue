<script setup>
import { computed } from 'vue';
const props = defineProps({ week: Object, ranges: Object });
const lifts = { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT' };
const scale = computed(() => Math.max(...Object.values(props.week.lifts).map(lift => lift.main + lift.var), props.week.roles.accessory, 1));
</script>

<template>
  <section class="week-capacity" aria-label="Weekly capacity">
    <div class="section-kicker"><span>WEEKLY CAPACITY</span><span>WORKING SETS</span></div>
    <div v-for="(label, code) in lifts" :key="code" class="volume-row">
      <header><span>{{ label }}</span><small>MEV {{ ranges.sbd[code].mev }} / MRV {{ ranges.sbd[code].mrv }}</small><strong>{{ week.lifts[code].main + week.lifts[code].var }}</strong></header>
      <div class="capacity-track"><i :style="{ width: `${week.lifts[code].main / scale * 100}%` }"></i><i :style="{ width: `${week.lifts[code].var / scale * 100}%` }"></i></div>
    </div>
    <div class="volume-row"><header><span>ACCESSORY</span><small>NO SBD EQUIVALENT</small><strong>{{ week.roles.accessory }}</strong></header><div class="capacity-track"><i :style="{ width: `${week.roles.accessory / scale * 100}%` }"></i></div></div>
    <div v-if="week.roles.nonSbdVar" class="volume-row"><header><span>OTHER VARIATIONS</span><small>OUTSIDE SBD</small><strong>{{ week.roles.nonSbdVar }}</strong></header></div>
    <div class="total-row"><span>ALL GROUPS</span><strong data-testid="weekly-total">{{ week.total }}</strong></div>
    <p class="micro-copy">Solid · main &nbsp; Gray · variation. SBD equivalent sets = main + SBD variations. MRV is not a target.</p>
  </section>
</template>
