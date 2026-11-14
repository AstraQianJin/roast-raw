<script setup>
import { onMounted, ref } from 'vue';
import BarbellStrip from './BarbellStrip.vue';

const props = defineProps({
  cycleId: { type: String, required: true },
  barKg: { type: Number, default: 20 },
  collarPair: { type: Number, default: 0 },
});
const state = ref(null);
const error = ref('');
const busy = ref(false);
const drafts = ref({});
const editing = ref({});
const LIFTS = [['squat', 'SQUAT'], ['bench', 'BENCH'], ['deadlift', 'DEADLIFT']];

async function load() {
  error.value = '';
  try {
    const response = await fetch(`/api/attempts?${new URLSearchParams({ cycle_id: props.cycleId })}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Attempt state could not be loaded (${response.status}).`);
    state.value = await response.json();
    drafts.value = {};
    editing.value = {};
    for (const [lift] of LIFTS) {
      state.value.lifts[lift].attempts.forEach((attempt, index) => {
        const key = `${lift}|${index + 1}`;
        drafts.value[key] = attempt ? attempt.load : state.value.lifts[lift].next[index];
      });
    }
  } catch (failure) { error.value = failure.message || 'The server is unavailable. Retry the connection.'; }
}
onMounted(load);

const attemptAt = (lift, number) => state.value.lifts[lift].attempts[number - 1];
const confirmed = (lift, number) => { const attempt = attemptAt(lift, number); return !!attempt && attempt.result !== null; };
const unlocked = (lift, number) => number === 1 || confirmed(lift, number - 1);
const draftKey = (lift, number) => `${lift}|${number}`;
const isEditing = (lift, number) => !confirmed(lift, number) || editing.value[draftKey(lift, number)];
const rowLoad = (lift, number) => {
  const attempt = attemptAt(lift, number);
  if (attempt && !isEditing(lift, number)) return attempt.load;
  const draft = Number(drafts.value[draftKey(lift, number)]);
  return Number.isFinite(draft) && draft > 0 ? draft : null;
};

async function confirm(lift, number, result) {
  const attemptLoad = Number(drafts.value[draftKey(lift, number)]);
  if (!Number.isFinite(attemptLoad) || attemptLoad <= 0 || Math.abs(attemptLoad / 2.5 - Math.round(attemptLoad / 2.5)) > 1e-6) {
    error.value = 'Attempt load must be a positive multiple of 2.5 kg.';
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    const response = await fetch('/api/attempts', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: props.cycleId, lift, number, load: attemptLoad, result }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `The attempt was not saved (${response.status}).`);
    }
    await load();
  } catch (failure) { error.value = failure.message || 'The attempt was not saved. Retry the connection.'; }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="attempt-board" data-testid="attempt-board" aria-label="Test day attempts">
    <div class="section-kicker"><span>TEST DAY ATTEMPTS</span><span v-if="state?.competition?.competition">COMPETITION</span><span v-else>SBD TEST</span></div>
    <h2>Three attempts.<br><em>One confirmed at a time.</em></h2>
    <p class="reading-note" v-if="state?.competition?.competition">
      {{ state.competition.name || 'Competition' }}<template v-if="state.competition.date"> · {{ state.competition.date }}</template>.
      Openers at 92.5%, second at 100%, third at 102.5% of the reference 1RM, floored to 2.5 kg.
    </p>
    <p class="reading-note" v-else>Suggested openers at 92.5%, second at 100%, third at 102.5% of the reference 1RM, floored to 2.5 kg. A miss repeats the same weight; after a good lift the next attempt never decreases.</p>
    <p v-if="error" class="attempt-error" role="alert" data-testid="attempt-error">{{ error }}</p>
    <p v-if="!state && !error" class="reading-note" role="status">Loading attempt suggestions…</p>
    <template v-if="state">
      <article v-for="[lift, label] in LIFTS" :key="lift" class="attempt-lift" :data-testid="`attempt-lift-${lift}`">
        <header>
          <h3>{{ label }}</h3>
          <p class="reading-note" v-if="state.lifts[lift].reference.reference !== null">
            Reference {{ state.lifts[lift].reference.reference }} kg · {{ state.lifts[lift].reference.source === 'questionnaire' ? 'questionnaire' : 'plan profile' }}
          </p>
          <p class="reading-note" v-else>No reference 1RM available. Enter the attempt load manually.</p>
        </header>
        <ol class="attempt-rows">
          <li v-for="number in [1, 2, 3]" :key="number" :data-testid="`attempt-${lift}-${number}`" :class="{ locked: !unlocked(lift, number) }">
            <span class="attempt-number">{{ number }}</span>
            <template v-if="isEditing(lift, number)">
              <label class="attempt-load"><span class="visually-hidden">{{ label }} attempt {{ number }} load, kg</span>
                <input type="number" inputmode="decimal" step="2.5" min="2.5" max="500" v-model.number="drafts[draftKey(lift, number)]" :disabled="busy || !unlocked(lift, number)" :data-testid="`attempt-load-${lift}-${number}`">
                <small>kg</small>
              </label>
              <span class="attempt-suggestion" v-if="state.lifts[lift].next[number - 1] !== null">Suggested {{ state.lifts[lift].next[number - 1] }}</span>
              <span class="attempt-actions">
                <button type="button" class="good" :disabled="busy || !unlocked(lift, number)" :data-testid="`attempt-good-${lift}-${number}`" @click="confirm(lift, number, 'good')">Good lift</button>
                <button type="button" class="miss" :disabled="busy || !unlocked(lift, number)" :data-testid="`attempt-miss-${lift}-${number}`" @click="confirm(lift, number, 'miss')">Missed</button>
              </span>
            </template>
            <template v-else>
              <span class="attempt-result" :data-testid="`attempt-result-${lift}-${number}`">
                <strong>{{ attemptAt(lift, number).load }} kg</strong>
                <span :class="attemptAt(lift, number).result">{{ attemptAt(lift, number).result === 'good' ? 'GOOD LIFT' : 'MISSED' }}</span>
              </span>
              <button type="button" class="attempt-edit" :disabled="busy" :data-testid="`attempt-edit-${lift}-${number}`" @click="editing[draftKey(lift, number)] = true">Change</button>
            </template>
            <span v-if="!unlocked(lift, number)" class="attempt-lock-note">Confirm attempt {{ number - 1 }} first</span>
            <span class="attempt-bar"><BarbellStrip :load="rowLoad(lift, number)" :bar-kg="barKg" :collar-pair="collarPair" /></span>
          </li>
        </ol>
      </article>
      <p class="reading-note">Attempts are recorded one by one and kept in the cycle journal. They do not change the prescribed plan or the calendar.</p>
    </template>
  </section>
</template>

<style scoped>
.attempt-board { min-width: 0; margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--accent); }
.attempt-board h2 { font-size: clamp(26px, 5vw, 34px); }
.attempt-board h2 em { color: var(--muted); font-weight: 400; }
.reading-note { margin-top: 10px; color: var(--muted); font: 12px/1.7 var(--sans); }
.attempt-error { margin-top: 12px; padding: 10px 12px; border: 1px solid var(--accent); background: var(--accent-soft); font-size: 13px; }
.attempt-lift { margin-top: 20px; border: 1px solid var(--line); background: var(--panel); }
.attempt-lift header { padding: 14px 12px 10px; border-bottom: 1px solid var(--line); }
.attempt-lift h3 { font-size: 20px; letter-spacing: .04em; }
.attempt-rows { list-style: none; margin: 0; padding: 0; }
.attempt-rows li { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 12px; border-top: 1px solid var(--line-soft); }
.attempt-rows li:first-child { border-top: 0; }
.attempt-rows li.locked { opacity: .62; }
.attempt-number { flex: 0 0 auto; width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--line); font: 600 13px var(--mono); }
.attempt-load { display: inline-flex; align-items: center; gap: 6px; }
.attempt-load input { width: 92px; min-height: 44px; padding: 8px; border: 1px solid var(--line); border-radius: 2px; background: var(--panel2); color: var(--ink); font: 600 15px var(--mono); }
.attempt-load small { color: var(--muted); font: 11px var(--sans); }
.attempt-suggestion { color: var(--muted); font: 11px/1.6 var(--mono); }
.attempt-actions { display: inline-flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.attempt-actions button, .attempt-edit { min-height: 44px; min-width: 44px; padding: 10px 12px; border: 1px solid var(--line); background: var(--panel2); color: var(--ink); font: 12px var(--sans); cursor: pointer; }
.attempt-actions button.good { border-color: var(--accent); background: var(--accent-soft); }
.attempt-actions button:disabled, .attempt-edit:disabled { cursor: default; opacity: .6; }
.attempt-result { display: inline-flex; align-items: baseline; gap: 10px; }
.attempt-result strong { font: 600 18px var(--mono); }
.attempt-result .good { color: var(--accent); font: 600 11px var(--mono); letter-spacing: .06em; }
.attempt-result .miss { color: var(--muted); font: 600 11px var(--mono); letter-spacing: .06em; }
.attempt-edit { margin-left: auto; }
.attempt-lock-note { flex-basis: 100%; color: var(--muted); font: 11px/1.6 var(--sans); }
.attempt-bar { flex-basis: 100%; display: flex; min-width: 0; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
@media (max-width: 390px) {
  .attempt-actions { margin-left: 0; }
  .attempt-rows li { padding: 12px 10px; }
}
</style>