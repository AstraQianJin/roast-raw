<script setup>
import { computed, ref } from 'vue';

const props = defineProps({ geometry: Object, leaves: Array, heatScale: Object, weekNumber: Number, weekCount: Number, compact: Boolean });
const emit = defineEmits(['week']);
const filter = ref('Both');
const selected = ref(null);
const hovered = ref(null);
const active = computed(() => props.leaves.find(leaf => leaf.id === (hovered.value || selected.value)));
const indexed = computed(() => Object.fromEntries(props.leaves.map(leaf => [leaf.id, leaf])));
const heat = id => indexed.value[id].heat[filter.value];
const shade = id => heat(id).band;
function visiblePaths(view) {
  return props.geometry.paths[view].filter(path => !path.leaf || props.geometry.leaves[path.leaf].view.includes(view));
}
const number = value => Number(value).toFixed(1);
</script>

<template>
  <section class="muscle-map" :class="{ compact }" aria-labelledby="muscle-title" data-testid="muscle-map">
    <div class="section-kicker"><span>MUSCLE MAP</span><span>16 LEAVES</span></div>
    <div class="map-heading">
      <h2 id="muscle-title">The work,<br><em>beneath the surface.</em></h2>
      <div class="week-stepper" aria-label="Muscle map week">
        <button aria-label="Previous muscle week" :disabled="weekNumber <= 1" @click="emit('week', weekNumber - 1)">‹</button>
        <strong data-testid="muscle-week">W{{ String(weekNumber).padStart(2, '0') }}</strong>
        <button aria-label="Next muscle week" :disabled="weekNumber >= weekCount" @click="emit('week', weekNumber + 1)">›</button>
      </div>
    </div>
    <p class="annotation">Weekly weighted sets · select a muscle to inspect.</p>
    <div class="map-legend" aria-label="Five volume bands">
      <span v-for="(label, i) in ['0', '1–25%', '26–50%', '51–75%', '76–100%']" :key="label"><i :class="`heat-${i}`"></i>{{ label }}</span>
    </div>
    <p class="micro-copy" data-testid="heat-scale">Fixed cycle scale: {{ number(heatScale.maximum) }} planned weighted sets. Shared across weeks and filters; not a recovery score. The darkest band also includes values above this scale.</p>
    <div class="map-filters" aria-label="Muscle contribution">
      <button v-for="kind in ['Both', 'Primary', 'Secondary']" :key="kind" :aria-pressed="filter === kind" @click="filter = kind">{{ kind }}</button>
    </div>
    <div class="anatomy-grid">
      <figure v-for="view in ['front', 'back']" :key="view">
        <svg :viewBox="geometry.viewBox[view]" role="img" :aria-label="`${view === 'front' ? 'Anterior' : 'Posterior'} muscle distribution. Use the muscle list for details.`" @mouseleave="hovered = null">
          <path v-for="path in visiblePaths(view)" :key="path.id" :d="path.d" :data-leaf="path.leaf"
            :class="[path.leaf ? `heat-${shade(path.leaf)}` : 'anatomy-base', { 'selected-muscle': path.leaf && active?.id === path.leaf }]"
            vector-effect="non-scaling-stroke" @mouseenter="hovered = path.leaf" @click="selected = path.leaf" />
        </svg>
        <figcaption>{{ view === 'front' ? 'ANTERIOR' : 'POSTERIOR' }}</figcaption>
      </figure>
    </div>
    <div v-if="!compact || active" class="muscle-detail" aria-live="polite" data-testid="muscle-detail">
      <template v-if="active">
        <div class="detail-title"><h3>{{ active.name }}</h3><button aria-label="Close muscle details" @click="selected = null; hovered = null">×</button></div>
        <div class="muscle-numbers"><span><b>{{ number(active.weighted) }}</b>WEIGHTED</span><span><b>{{ active.direct }}</b>DIRECT</span><span><b>{{ active.mev ?? '—' }}</b>MEV</span><span><b>{{ active.mrv ?? '—' }}</b>MRV</span></div>
        <p>{{ active.verdict }}<template v-if="active.scope === 'group_back'"> · Back-group reference, not an individual-muscle target.</template></p>
      </template>
      <template v-else-if="!compact"><h3>Explore the distribution.</h3><p>Tap the anatomy or a muscle below for weighted / direct sets, MEV / MRV and context.</p></template>
    </div>
    <label v-if="compact" class="muscle-selector">Inspect a muscle
      <select v-model="selected" @change="hovered = null"><option :value="null">Choose a muscle</option><option v-for="leaf in leaves" :key="leaf.id" :value="leaf.id">{{ leaf.name }}</option></select>
    </label>
    <RouterLink v-if="compact" :to="`/analysis?week=${weekNumber}`" class="inline-link">Full muscle analysis →</RouterLink>
    <slot name="summary" />
    <div v-if="!compact" class="leaf-list" aria-label="All sixteen muscles">
      <button v-for="leaf in leaves" :key="leaf.id" :data-testid="`leaf-${leaf.id}`" :aria-pressed="selected === leaf.id" @click="selected = selected === leaf.id ? null : leaf.id">
        <span>{{ leaf.name }} <i class="tier-marker">{{ leaf.primaryWeighted > 0 ? 'P' : leaf.secondaryWeighted > 0 ? 'S' : '—' }}</i></span>
        <span class="leaf-track" aria-hidden="true"><i :class="`heat-${shade(leaf.id)}`" :style="{ width: `${heat(leaf.id).percent}%` }"></i></span>
        <span aria-hidden="true">↗</span>
      </button>
    </div>
    <p v-if="!compact" class="micro-copy">P · primary work present &nbsp; S · secondary work only. Primary ≥ 80% of a movement’s maximum coefficient; secondary ≥ 30%. Filters change color contributions, not totals.</p>
    <p v-if="!compact" class="micro-copy">MEV / MRV: direct-set reference at two sessions per week. MRV is a recovery ceiling, not a target. Adductors have no separate source.</p>
    <p class="attribution">Anatomy: body-muscles 1.0.0 · Apache-2.0</p>
  </section>
</template>
