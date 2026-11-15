<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { dayShareData, renderShareCard } from '../share.js';
import { collarPairOf, useCollars } from '../gear-settings.js';

const props = defineProps({
  plan: { type: Object, required: true },
  logs: { type: Object, default: () => ({}) },
  theme: { type: String, default: 'light' },
  defaultDate: { type: String, required: true },
});

const canvas = ref(null);
const date = ref(props.defaultDate);
const error = ref('');
const busy = ref(false);

const dates = computed(() => [...new Set(props.plan.workouts.map(row => row.date))].sort());
const data = computed(() => dayShareData(props.plan, props.logs, date.value));
const collarPair = computed(() => collarPairOf(useCollars.value));

function draw() {
  if (!canvas.value) return;
  try {
    renderShareCard(canvas.value, data.value, props.plan, props.theme, collarPair.value);
    error.value = '';
  } catch (cause) {
    error.value = `Share card could not be drawn: ${cause.message}`;
  }
}

async function download() {
  if (!canvas.value || busy.value) return;
  busy.value = true;
  try {
    draw();
    const blob = await new Promise(resolve => canvas.value.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('the browser returned no image');
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `RoastRaw-share-${date.value}.png`;
    anchor.click();
    URL.revokeObjectURL(url);
    error.value = '';
  } catch (cause) {
    error.value = `PNG export failed: ${cause.message}`;
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  draw();
  if (document.fonts?.ready) document.fonts.ready.then(draw);
});
watch([data, () => props.theme], draw, { deep: true });
</script>

<template>
  <section class="share-card" data-testid="share-card" aria-label="Daily share card">
    <div class="section-kicker"><span>DAILY SHARE · TOPSET STYLE</span><span>1080 × 1440 PNG</span></div>
    <label class="share-date">Training date
      <select v-model="date" data-testid="share-date">
        <option v-for="item in dates" :key="item" :value="item">{{ item }}</option>
      </select>
    </label>
    <p class="micro-copy">Plates are solved from the day’s final logged main lift: the 20 kg bar, plus the 5 kg competition collar pair only when it is switched on in settings.</p>
    <p v-if="error" class="notice" role="alert" data-testid="share-error">{{ error }}</p>
    <figure class="share-preview">
      <canvas ref="canvas" data-testid="share-canvas" aria-label="Share card preview"></canvas>
    </figure>
    <p class="micro-copy" data-testid="share-summary">
      <template v-if="data.loggedCount">{{ data.doneSets }} / {{ data.plannedSets }} sets logged · volume {{ Math.round(data.volume).toLocaleString('en-US') }} kg</template>
      <template v-else>No session log for this date — the card shows the empty state.</template>
    </p>
    <button data-testid="share-download" :disabled="busy" @click="download">{{ busy ? 'Exporting…' : 'Download PNG' }}</button>
  </section>
</template>

<style scoped>
.share-card { margin-top: 26px; padding: 16px 14px; border: 1px solid var(--line2); border-radius: var(--radius); background: var(--card-grad); box-shadow: var(--card-shadow); }
.share-date { display: block; margin: 12px 0 6px; font-size: 11px; color: var(--muted); }
.share-date select { display: block; width: 100%; min-height: 44px; margin-top: 6px; border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 8px; background: var(--panel); color: var(--ink); font-family: var(--mono); }
.share-preview { margin: 14px 0 10px; }
.share-preview canvas { display: block; width: 100%; height: auto; border: 1px solid var(--line2); border-radius: var(--radius-sm); }
.share-card button { width: 100%; margin-top: 10px; }
</style>