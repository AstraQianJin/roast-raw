<script setup>
import { computed } from 'vue';
const props = defineProps({ week: Object, ranges: Object });
const lifts = { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT' };
const scale = computed(() => Math.max(...Object.values(props.week.equivalent).map(lift => lift.main + lift.var), props.week.roles.accessory, 1));
const display = value => Number(value).toFixed(1);
</script>

<template>
  <section class="week-capacity" aria-label="Weekly capacity">
    <div class="section-kicker"><span>WEEKLY CAPACITY</span><span>SBD EQUIVALENT</span></div>
    <div v-for="(label, code) in lifts" :key="code" class="volume-row">
      <header><span>{{ label }}</span><small>MEV {{ ranges.sbd[code].mev }} / MRV {{ ranges.sbd[code].mrv }}</small><strong :data-testid="`equivalent-${code}`">{{ display(week.equivalent[code].total) }}</strong></header>
      <div class="capacity-track"><i :style="{ width: `${week.equivalent[code].main / scale * 100}%` }"></i><i :style="{ width: `${week.equivalent[code].var / scale * 100}%` }"></i></div>
      <p class="micro-copy">{{ week.lifts[code].main }} main + {{ week.lifts[code].var }} variation working sets<span v-if="week.equivalent[code].unknown"> · {{ week.equivalent[code].unknown }} sets excluded: transfer unknown</span></p>
    </div>
    <div class="volume-row"><header><span>ACCESSORY</span><small>NO SBD EQUIVALENT</small><strong>{{ week.roles.accessory }}</strong></header><div class="capacity-track"><i :style="{ width: `${week.roles.accessory / scale * 100}%` }"></i></div></div>
    <div v-if="week.roles.nonSbdVar" class="volume-row"><header><span>OTHER VARIATIONS</span><small>OUTSIDE SBD</small><strong>{{ week.roles.nonSbdVar }}</strong></header></div>
    <div class="total-row"><span>ALL GROUPS</span><strong data-testid="weekly-total">{{ week.total }}</strong></div>
    <p class="micro-copy">Solid · main &nbsp; Gray · equivalent variation. Approved transfer factors apply only to SBD capacity, not working sets, muscle weighting or completion. Legacy prescriptions retain their original 1:1 basis. MEV/MRV are reference ranges, not targets.</p>
  </section>
</template>
