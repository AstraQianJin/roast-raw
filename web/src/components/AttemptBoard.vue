<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import BarbellStrip from './BarbellStrip.vue';
import ExerciseRows from './ExerciseRows.vue';

const props = defineProps({
  cycleId: { type: String, required: true },
  barKg: { type: Number, default: 20 },
  collarPair: { type: Number, default: 0 },
  rows: { type: Array, default: () => [] },
  logs: { type: Object, default: () => ({}) },
  systemLoads: { type: Object, default: () => ({}) },
});
const emit = defineEmits(['saved']);
const state = ref(null);
const error = ref('');
const busy = ref(false);
const drafts = ref({});
const editing = ref({});
const LIFTS = [['squat', 'SQUAT', 'S'], ['bench', 'BENCH', 'B'], ['deadlift', 'DEADLIFT', 'D']];

// Three judge lights per attempt, white by default. Two or more white lights is a
// good lift, two or more red is a miss; the vote is only recorded on confirmation.
const votes = reactive({});
const voteKey = (lift, number) => `${lift}|${number}`;
const panel = (lift, number) => {
  if (!votes[voteKey(lift, number)]) votes[voteKey(lift, number)] = [false, false, false];
  return votes[voteKey(lift, number)];
};
const redCount = (lift, number) => panel(lift, number).filter(Boolean).length;
const verdict = (lift, number) => (redCount(lift, number) >= 2 ? 'miss' : 'good');
const tally = (lift, number) => {
  const reds = redCount(lift, number);
  return reds >= 2 ? `${3 - reds}-${reds} MISS` : reds === 0 ? '3-0 GOOD' : `${3 - reds}-${reds} GOOD`;
};
const toggleVote = (lift, number, index) => {
  const row = panel(lift, number);
  row[index] = !row[index];
};

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
        const draftKey = voteKey(lift, index + 1);
        drafts.value[draftKey] = attempt ? attempt.load : state.value.lifts[lift].next[index];
        votes[draftKey] = [false, false, false];
      });
    }
  } catch (failure) { error.value = failure.message || 'The server is unavailable. Retry the connection.'; }
}
onMounted(load);

const attemptAt = (lift, number) => state.value.lifts[lift].attempts[number - 1];
const confirmed = (lift, number) => { const attempt = attemptAt(lift, number); return !!attempt && attempt.result !== null; };
const unlocked = (lift, number) => number === 1 || confirmed(lift, number - 1);
const isEditing = (lift, number) => !confirmed(lift, number) || editing.value[voteKey(lift, number)];
const rowLoad = (lift, number) => {
  const attempt = attemptAt(lift, number);
  if (attempt && !isEditing(lift, number)) return attempt.load;
  const draft = Number(drafts.value[voteKey(lift, number)]);
  return Number.isFinite(draft) && draft > 0 ? draft : null;
};

// A saved attempt keeps its judges on screen: a good lift reads as two white
// lights, a miss as two red. The third light did not vote.
const savedVotes = (lift, number) => {
  const attempt = attemptAt(lift, number);
  if (!attempt) return [];
  return attempt.result === 'good' ? [false, false, null] : [true, true, null];
};

async function confirm(lift, number) {
  const attemptLoad = Number(drafts.value[voteKey(lift, number)]);
  if (!Number.isFinite(attemptLoad) || attemptLoad <= 0 || Math.abs(attemptLoad / 2.5 - Math.round(attemptLoad / 2.5)) > 1e-6) {
    error.value = 'Attempt load must be a positive multiple of 2.5 kg.';
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    const response = await fetch('/api/attempts', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: props.cycleId, lift, number, load: attemptLoad, result: verdict(lift, number) }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `The attempt was not saved (${response.status}).`);
    }
    await load();
  } catch (failure) { error.value = failure.message || 'The attempt was not saved. Retry the connection.'; }
  finally { busy.value = false; }
}

// ---- fourth group: rows that really exist in this test week -----------------
const rowKey = row => `${row.week}|${row.day}|${row.seq}`;
const testDay = computed(() => {
  const counts = new Map();
  for (const row of props.rows) {
    const key = `${row.week}|${row.day}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  let pick = null;
  for (const [key, count] of counts) if (!pick || count > pick.count) pick = { key, count };
  return pick ? pick.key : null;
});
const attemptKeys = computed(() => {
  const keys = new Set();
  if (!testDay.value) return keys;
  for (const code of ['S', 'B', 'D']) {
    const rows = props.rows
      .filter(row => row.bucket === 'main' && row.lift === code && `${row.week}|${row.day}` === testDay.value)
      .sort((a, b) => a.seq - b.seq);
    rows.slice(0, 3).forEach(row => keys.add(rowKey(row)));
  }
  return keys;
});
const extraRows = computed(() => props.rows.filter(row => !attemptKeys.value.has(rowKey(row))));
const extraDays = computed(() => {
  const byDay = new Map();
  for (const row of extraRows.value) {
    const key = `${row.week}|${row.day}`;
    if (!byDay.has(key)) byDay.set(key, { key, day: row.day, week: row.week, rows: [] });
    byDay.get(key).rows.push(row);
  }
  return [...byDay.values()].sort((a, b) => String(a.day).localeCompare(String(b.day)));
});
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
    <p class="reading-note">Each attempt carries three judge lights. White means passed, red means failed; two white lights is a good lift, two red is a miss.</p>
    <p v-if="error" class="attempt-error" role="alert" data-testid="attempt-error">{{ error }}</p>
    <p v-if="!state && !error" class="reading-note" role="status">Loading attempt suggestions…</p>
    <template v-if="state">
      <article v-for="[lift, label, code] in LIFTS" :key="lift" class="attempt-lift" :data-testid="`attempt-lift-${lift}`" :data-group="code">
        <header>
          <h3>{{ label }}</h3>
          <p class="reading-note" v-if="state.lifts[lift].reference.reference !== null">
            Reference {{ state.lifts[lift].reference.reference }} kg · {{ state.lifts[lift].reference.source === 'questionnaire' ? 'questionnaire' : 'plan profile' }}
          </p>
          <p class="reading-note" v-else>No reference 1RM available. Enter the attempt load manually.</p>
        </header>
        <ol class="attempt-rows">
          <li v-for="number in [1, 2, 3]" :key="number" :data-testid="`attempt-${lift}-${number}`" :class="[{ locked: !unlocked(lift, number) }, confirmed(lift, number) ? attemptAt(lift, number).result : 'unjudged']">
            <span class="attempt-number">{{ number }}</span>
            <template v-if="isEditing(lift, number)">
              <label class="attempt-load"><span class="visually-hidden">{{ label }} attempt {{ number }} load, kg</span>
                <input type="number" inputmode="decimal" step="2.5" min="2.5" max="500" v-model.number="drafts[voteKey(lift, number)]" :disabled="busy || !unlocked(lift, number)" :data-testid="`attempt-load-${lift}-${number}`">
                <small>kg</small>
              </label>
              <span class="attempt-suggestion" v-if="state.lifts[lift].next[number - 1] !== null">Suggested {{ state.lifts[lift].next[number - 1] }}</span>
              <span class="lamps" role="group" :aria-label="`${label} attempt ${number} judge lights`" data-testid="judge-lamps">
                <button
                  v-for="(red, index) in panel(lift, number)" :key="index" type="button"
                  :class="['lamp', { red }]" :aria-pressed="red" :disabled="busy || !unlocked(lift, number)"
                  :aria-label="`Judge ${index + 1} light, ${red ? 'red, miss' : 'white, good'}. Activate to mark it ${red ? 'white' : 'red'}.`"
                  :data-testid="`judge-${lift}-${number}-${index + 1}`"
                  @click="toggleVote(lift, number, index)"
                ></button>
              </span>
              <span class="attempt-tally" :class="verdict(lift, number)" :data-testid="`tally-${lift}-${number}`">{{ tally(lift, number) }}</span>
              <span class="attempt-actions">
                <button type="button" class="good" :disabled="busy || !unlocked(lift, number)" :data-testid="`attempt-confirm-${lift}-${number}`" @click="confirm(lift, number)">Confirm attempt</button>
              </span>
            </template>
            <template v-else>
              <span class="attempt-result" :data-testid="`attempt-result-${lift}-${number}`">
                <strong>{{ attemptAt(lift, number).load }} kg</strong>
                <span :class="attemptAt(lift, number).result">{{ attemptAt(lift, number).result === 'good' ? 'GOOD LIFT' : 'MISSED' }}</span>
              </span>
              <span class="lamps static" role="img" :aria-label="`${label} attempt ${number} judges: ${attemptAt(lift, number).result === 'good' ? 'two white lights, good lift' : 'two red lights, miss'}`">
                <span v-for="(red, index) in savedVotes(lift, number)" :key="index" :class="['lamp', { red, off: red === null }]"></span>
              </span>
              <button type="button" class="attempt-edit" :disabled="busy" :data-testid="`attempt-edit-${lift}-${number}`" @click="editing[voteKey(lift, number)] = true">Change</button>
            </template>
            <span v-if="!unlocked(lift, number)" class="attempt-lock-note">Confirm attempt {{ number - 1 }} first</span>
            <span class="attempt-bar"><BarbellStrip :load="rowLoad(lift, number)" :bar-kg="barKg" :collar-pair="collarPair" /></span>
          </li>
        </ol>
      </article>

      <section class="planned" data-testid="planned-rows" aria-label="Planned rows in this test week">
        <div class="section-kicker"><span>PLANNED ROWS</span><span>{{ extraRows.length }} THIS WEEK</span></div>
        <p class="reading-note">The fourth group is the work this plan really schedules in the test week. Rows from other sessions of the week keep their own inputs; nothing outside the plan is added.</p>
        <div v-for="group in extraDays" :key="group.key" class="planned-day">
          <h3 class="planned-day-head">W{{ String(group.week).padStart(2, '0') }} · DAY {{ group.day }}</h3>
          <ExerciseRows :rows="group.rows" :cycle-id="cycleId" :logs="logs" :system-loads="systemLoads" @saved="emit('saved', $event)" />
        </div>
        <p v-if="!extraRows.length" class="reading-note planned-empty" data-testid="planned-empty">No other rows are prescribed in this test week.</p>
      </section>

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
/* Judge lights: three white lamps by default, tap to turn one red. */
.lamps { display: inline-flex; align-items: center; gap: 6px; }
.lamp { width: 44px; height: 44px; padding: 0; display: grid; place-items: center; border: 1px solid var(--line); border-radius: 2px; background: var(--panel2); cursor: pointer; }
.lamp::before { content: ''; width: 18px; height: 18px; border-radius: 50%; background: var(--panel); border: 2px solid var(--line2); box-shadow: inset 0 -2px 3px rgba(17, 17, 17, .12); transition: background var(--dur-fast, .15s) var(--ease-out, ease), border-color var(--dur-fast, .15s) var(--ease-out, ease); }
.lamp.red::before { background: var(--accent); border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.lamp.off::before { background: var(--soft, #E7E5DE); border-color: var(--line-soft); }
.lamps.static .lamp { cursor: default; background: none; border: 0; width: 20px; height: 20px; }
.lamps.static .lamp::before { width: 16px; height: 16px; }
.lamp:disabled { cursor: default; opacity: .6; }
.attempt-tally { font: 700 10px var(--mono); letter-spacing: .06em; }
.attempt-tally.good { color: var(--accent); }
.attempt-tally.miss { color: var(--muted); }
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
.planned { margin-top: 26px; padding-top: 18px; border-top: 1px solid var(--line); }
.planned-empty { font-style: italic; }
.planned-day { margin-top: 12px; }
.planned-day-head { margin: 0 0 4px; font: 700 10px var(--mono); letter-spacing: .08em; color: var(--muted); }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
@media (max-width: 430px) {
  .attempt-actions { margin-left: 0; }
  .attempt-rows li { padding: 12px 10px; }
  .lamps { gap: 4px; }
}
</style>
