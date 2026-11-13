<script setup>
defineProps({ entries: { type: Array, default: () => [] } });
</script>

<template>
  <details v-if="entries.length" class="gear warmups" data-testid="warmups">
    <summary>WARM-UP <span class="chip">SUGGESTION ONLY</span></summary>
    <div v-for="entry in entries" :key="entry.lift" class="warmup-lift">
      <span class="section-label">{{ entry.movement }}</span>
      <p class="warmup-steps"><span v-for="(step, index) in entry.steps" :key="index">{{ step.label }} {{ step.kg }} kg × {{ step.reps }}</span></p>
    </div>
    <p class="micro-copy">Generated from the session’s top loads. Suggestions only — never written to your log.</p>
  </details>
</template>