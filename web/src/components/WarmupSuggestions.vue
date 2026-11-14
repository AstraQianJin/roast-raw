<script setup>
defineProps({ entries: { type: Array, default: () => [] } });
</script>

<template>
  <details v-if="entries.length" class="gear warmups" data-testid="warmups">
    <summary>WARM-UP <span class="chip">SUGGESTION ONLY</span></summary>
    <div class="warmup-body">
      <div v-for="entry in entries" :key="entry.lift" class="warmup-lift">
        <span class="section-label">{{ entry.movement }}</span>
        <p class="warmup-steps"><span v-for="(step, index) in entry.steps" :key="index" class="warmup-step"><b>{{ step.kg }}</b> kg<small>× {{ step.reps }}</small><em>{{ step.label }}</em></span></p>
      </div>
      <p class="micro-copy">Generated from the session’s top loads. Suggestions only — never written to your log.</p>
    </div>
  </details>
</template>

<style scoped>
.warmup-body { padding-bottom: 16px; }
.warmup-lift { padding: 10px 0; border-top: 1px solid var(--line-soft); }
.warmup-lift:first-child { border-top: 0; padding-top: 2px; }
.warmup-steps { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.warmup-step { display: inline-flex; align-items: baseline; gap: 4px; border: 1px solid var(--line2); background: var(--panel); padding: 5px 8px; font: 11px var(--mono); color: var(--ink); }
.warmup-step b { font-size: 13px; letter-spacing: -.02em; }
.warmup-step small { color: var(--muted); font-size: 10px; }
.warmup-step em { font-style: normal; font-size: 8.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-left: 3px; }
.micro-copy { margin-top: 12px; }
</style>