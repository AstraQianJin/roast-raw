<script setup>
defineProps({ rows: Array });
const roleNames = { main: 'MAIN LIFTS', sbdVar: 'SBD VARIATIONS', nonSbdVar: 'OTHER VARIATIONS', accessory: 'ACCESSORIES' };
const display = value => value === null || value === undefined ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 });
</script>

<template>
  <div class="exercise-rows">
    <template v-for="(label, role) in roleNames" :key="role">
      <template v-if="rows.some(row => row.bucket === role)">
        <div class="section-heading"><span class="section-label">{{ label }}</span><span class="mono">{{ String(rows.filter(row => row.bucket === role).length).padStart(2, '0') }}</span></div>
        <article v-for="row in rows.filter(row => row.bucket === role)" :key="`${row.week}-${row.day}-${row.seq}`" :class="['exercise', row.bucket]">
          <div class="exercise-heading"><span class="exercise-index">{{ String(row.seq).padStart(2, '0') }}</span><span class="exercise-name">{{ row.nameEn }}</span><span class="rpe">RPE {{ display(row.targetRpe) }}</span></div>
          <div v-for="(segment, index) in row.segments" :key="index" class="prescription">
            <span class="segment-label">{{ segment.label }}</span>
            <span class="reps">{{ segment.sets }} × {{ segment.reps }}<small v-if="segment.unit"> {{ segment.unit }}</small></span>
            <span class="weight">{{ role === 'accessory' ? '—' : display(segment.load) }}<small v-if="role !== 'accessory' && segment.load !== null"> kg</small></span>
            <small>{{ segment.pct === null || role === 'accessory' ? '' : `${display(segment.pct)}%` }}</small>
          </div>
        </article>
      </template>
    </template>
  </div>
</template>
