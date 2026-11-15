<script setup>
// One glossary, first use in the product: every abbreviation the journal prints is
// defined in the same words here (0.45, P2-10).
const TERMS = [
  ['SBD', 'Squat, bench and deadlift: the three competition lifts.'],
  ['MEV', 'Minimum effective volume: the least weekly work that still moves progress.'],
  ['MRV', 'Maximum recoverable volume: the most weekly work you can absorb and still recover.'],
  ['RPE', 'Rate of perceived exertion. 6 leaves about four reps in reserve; 10 is nothing left.'],
  ['GPP', 'General physical preparedness: cardio, recovery and weak-point work. It never counts as SBD volume.'],
  ['t', 'Metric tonne, 1,000 kg. Cycle tonnage is the sum of prescribed segment loads, not bodyweight moved.'],
  ['ses', 'A recorded session with its rows and logs.'],
  ['TOP / BACK-OFF', 'The heaviest set of a lift and the lighter repeat sets that follow it.'],
];
</script>

<template>
  <details class="glossary" data-testid="glossary">
    <summary>HOW TO READ THIS · GLOSSARY</summary>
    <dl>
      <div v-for="[term, meaning] in TERMS" :key="term"><dt>{{ term }}</dt><dd>{{ meaning }}</dd></div>
    </dl>
  </details>
</template>

<style scoped>
.glossary { margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--line-soft); }
.glossary summary { min-height: 44px; display: flex; align-items: center; font: 700 11px var(--mono); letter-spacing: .08em; cursor: pointer; }
.glossary dl { display: grid; gap: 10px; margin-top: 10px; }
.glossary dl > div { display: grid; grid-template-columns: 88px minmax(0, 1fr); gap: 10px; padding-bottom: 8px; border-bottom: 1px dotted var(--hair); }
.glossary dt { font: 700 10px var(--mono); letter-spacing: .06em; }
.glossary dd { margin: 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); }
@media (max-width: 420px) { .glossary dl > div { grid-template-columns: 1fr; gap: 2px; } }
</style>
