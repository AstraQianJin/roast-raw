<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';

const props = defineProps({
  cycleId: { type: String, required: true },
  date: { type: String, required: true },
  sessionId: { type: String, default: 'daily' },
  readonly: { type: Boolean, default: false },
  readonlyNote: { type: String, default: 'Read-only record.' },
});
const emit = defineEmits(['saved']);

const ratings = [
  { key: 'recovery', label: 'Muscle Recovery', low: 'Very fatigued', high: 'Fully recovered' },
  { key: 'arousal', label: 'Arousal', low: 'Very low', high: 'Alert and focused' },
  { key: 'nutrition', label: 'Nutrition', low: 'Poorly fueled', high: 'Well fueled' },
];
const measurementFields = [
  { key: 'waist', label: 'Waist' },
  { key: 'chest', label: 'Chest' },
  { key: 'hips', label: 'Hips' },
  { key: 'upper_arm', label: 'Upper arm' },
  { key: 'thigh', label: 'Thigh' },
  { key: 'calf', label: 'Calf' },
];
const emptyReadiness = () => ({
  recovery: '', arousal: '', nutrition: '', hrv: '', rhr: '', sleep_score: '',
  session_time: '', joint_pain: false, note: '',
});
const emptyBody = () => ({
  bodyweight: '', bodyfat: '',
  measurements: Object.fromEntries(measurementFields.map(({ key }) => [key, ''])),
});
const formState = () => ({
  loading: false, loaded: false, saving: false, saved: false, loadError: '', saveError: '',
});
const readiness = reactive(emptyReadiness());
const body = reactive(emptyBody());
const readinessState = reactive(formState());
const bodyState = reactive(formState());
const evaluation = ref(null);
const bodyweightSource = ref(null);
let loadSequence = 0;

const scoredInputs = computed(() => {
  const value = evaluation.value?.validInputs;
  if (Array.isArray(value)) return value.length;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
});
const completeEvaluation = computed(() => scoredInputs.value !== null && scoredInputs.value >= 3);
const score = computed(() => {
  const value = evaluation.value?.score;
  return completeEvaluation.value && typeof value === 'number' && Number.isFinite(value) ? value : null;
});
const recoveryCoefficient = computed(() => {
  const value = evaluation.value?.rec;
  return completeEvaluation.value && typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '';
});
const timeAdjustment = computed(() => {
  const value = evaluation.value?.timeAdjustmentPct;
  return completeEvaluation.value && typeof value === 'number' && Number.isFinite(value) && value !== 0
    ? `${value > 0 ? '+' : ''}${value}%` : '';
});
const priorBodyweight = computed(() => {
  const source = bodyweightSource.value;
  return source && source.date < props.date ? source : null;
});

function context() {
  return { cycle_id: props.cycleId, date: props.date, session_id: props.sessionId };
}
function readinessUrl(scope) {
  return `/api/readiness?${new URLSearchParams(scope)}`;
}
function bodyUrl(scope) {
  return `/api/body-metrics?${new URLSearchParams({ cycle_id: scope.cycle_id, date: scope.date })}`;
}
function errorMessage(payload, fallback) {
  const detail = payload?.detail ?? payload?.message ?? payload?.error;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((entry) => {
      if (typeof entry === 'string') return entry;
      const location = Array.isArray(entry?.loc) ? entry.loc.filter((part) => part !== 'body').join(' / ') : '';
      const message = entry?.msg ?? entry?.message;
      return typeof message === 'string' ? `${location ? `${location}: ` : ''}${message}` : '';
    }).filter(Boolean);
    if (messages.length) return messages.join('; ');
  }
  return fallback;
}
async function request(url, options) {
  const response = await fetch(url, { cache: 'no-store', ...options });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(response.ok ? 'The server returned an unreadable response.' : `Request failed (${response.status}).`);
  }
  if (!response.ok) throw new Error(errorMessage(payload, `Request failed (${response.status}).`));
  return payload;
}
function inputValue(value) {
  return value === null || value === undefined ? '' : String(value);
}
function applyReadiness(payload, scope) {
  if (!payload || !Object.hasOwn(payload, 'record') || !Object.hasOwn(payload, 'evaluation')
    || (payload.record !== null && (typeof payload.record !== 'object' || Array.isArray(payload.record)))
    || (payload.evaluation !== null && (typeof payload.evaluation !== 'object' || Array.isArray(payload.evaluation)))) {
    throw new Error('The server returned an invalid recovery record. Reload before saving.');
  }
  const record = payload.record;
  if (record && (record.date !== scope.date || record.session_id !== scope.session_id)) {
    throw new Error('The recovery record belongs to a different date or session. Reload before saving.');
  }
  const next = emptyReadiness();
  if (record) {
    for (const key of Object.keys(next)) {
      next[key] = key === 'joint_pain' ? record[key] === true : inputValue(record[key]);
    }
  }
  Object.assign(readiness, next);
  evaluation.value = payload.evaluation;
}
function applyBody(payload, scope) {
  if (!payload || !Array.isArray(payload.records) || !Object.hasOwn(payload, 'bodyweight')) {
    throw new Error('The server returned invalid body metrics. Reload before saving.');
  }
  const record = payload.records.find((entry) => entry?.date === scope.date);
  const next = emptyBody();
  if (record) {
    next.bodyweight = inputValue(record.bodyweight);
    next.bodyfat = inputValue(record.bodyfat);
    for (const { key } of measurementFields) next.measurements[key] = inputValue(record.measurements?.[key]);
  }
  Object.assign(body, next);
  bodyweightSource.value = payload.bodyweight;
}
async function loadReadiness(sequence, scope) {
  readinessState.loading = true;
  readinessState.loadError = '';
  try {
    const payload = await request(readinessUrl(scope));
    if (sequence !== loadSequence) return;
    applyReadiness(payload, scope);
    readinessState.loaded = true;
  } catch (error) {
    if (sequence !== loadSequence) return;
    readinessState.loaded = false;
    readinessState.loadError = `Recovery could not be loaded. ${error.message}`;
  } finally {
    if (sequence === loadSequence) readinessState.loading = false;
  }
}
async function loadBody(sequence, scope) {
  bodyState.loading = true;
  bodyState.loadError = '';
  try {
    const payload = await request(bodyUrl(scope));
    if (sequence !== loadSequence) return;
    applyBody(payload, scope);
    bodyState.loaded = true;
  } catch (error) {
    if (sequence !== loadSequence) return;
    bodyState.loaded = false;
    bodyState.loadError = `Body metrics could not be loaded. ${error.message}`;
  } finally {
    if (sequence === loadSequence) bodyState.loading = false;
  }
}
function retryReadiness() {
  if (!readinessState.loading) void loadReadiness(loadSequence, context());
}
function retryBody() {
  if (!bodyState.loading) void loadBody(loadSequence, context());
}
watch(() => [props.cycleId, props.date, props.sessionId], () => {
  const sequence = ++loadSequence;
  const scope = context();
  Object.assign(readiness, emptyReadiness());
  Object.assign(body, emptyBody());
  Object.assign(readinessState, formState());
  Object.assign(bodyState, formState());
  evaluation.value = null;
  bodyweightSource.value = null;
  void loadReadiness(sequence, scope);
  void loadBody(sequence, scope);
}, { immediate: true, flush: 'sync' });
onBeforeUnmount(() => { loadSequence += 1; });

function optionalNumber(value, label, { min, max, positive = false, integer = false } = {}) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  const number = Number(text);
  if (!Number.isFinite(number) || (integer && !Number.isInteger(number))
    || (positive && number <= 0) || (min !== undefined && number < min) || (max !== undefined && number > max)) {
    const range = positive ? 'a number greater than zero'
      : `${integer ? 'a whole number' : 'a number'} between ${min} and ${max}`;
    throw new Error(`${label} must be ${range}, or left blank.`);
  }
  return number;
}
function readinessPayload(scope) {
  const payload = { ...scope };
  for (const { key, label } of ratings) {
    payload[key] = optionalNumber(readiness[key], label, { min: 1, max: 7, integer: true });
  }
  payload.hrv = optionalNumber(readiness.hrv, 'HRV', { positive: true });
  payload.rhr = optionalNumber(readiness.rhr, 'Resting heart rate', { positive: true });
  payload.sleep_score = optionalNumber(readiness.sleep_score, 'Sleep score', { min: 0, max: 100 });
  const time = readiness.session_time.trim();
  if (time && !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) {
    throw new Error('Session time must use HH:MM in 24-hour time, or be left blank.');
  }
  payload.session_time = time || null;
  payload.joint_pain = readiness.joint_pain;
  if (readiness.note.length > 2000) throw new Error('The note must be 2,000 characters or fewer.');
  payload.note = readiness.note;
  return payload;
}
function bodyPayload(scope) {
  return {
    cycle_id: scope.cycle_id,
    date: scope.date,
    bodyweight: optionalNumber(body.bodyweight, 'Bodyweight', { positive: true }),
    bodyfat: optionalNumber(body.bodyfat, 'Body fat', { min: 0, max: 100 }),
    measurements: Object.fromEntries(measurementFields.map(({ key, label }) => [
      key, optionalNumber(body.measurements[key], label, { positive: true }),
    ])),
  };
}
async function saveReadiness() {
  if (props.readonly || !readinessState.loaded || readinessState.loading || readinessState.saving) return;
  const sequence = loadSequence;
  const scope = context();
  readinessState.saving = true;
  readinessState.saved = false;
  readinessState.saveError = '';
  try {
    const payload = await request('/api/readiness', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(readinessPayload(scope)),
    });
    if (sequence !== loadSequence) return;
    applyReadiness(payload, scope);
    readinessState.saved = true;
    emit('saved');
  } catch (error) {
    if (sequence === loadSequence) readinessState.saveError = `Recovery was not saved. ${error.message} Your inputs have been kept.`;
  } finally {
    if (sequence === loadSequence) readinessState.saving = false;
  }
}
async function saveBody() {
  if (props.readonly || !bodyState.loaded || bodyState.loading || bodyState.saving) return;
  const sequence = loadSequence;
  const scope = context();
  bodyState.saving = true;
  bodyState.saved = false;
  bodyState.saveError = '';
  try {
    const payload = await request('/api/body-metrics', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload(scope)),
    });
    if (sequence !== loadSequence) return;
    applyBody(payload, scope);
    bodyState.saved = true;
    emit('saved');
  } catch (error) {
    if (sequence === loadSequence) bodyState.saveError = `Body metrics were not saved. ${error.message} Your inputs have been kept.`;
  } finally {
    if (sequence === loadSequence) bodyState.saving = false;
  }
}
</script>

<template>
  <details class="daily-record" data-testid="daily-record">
    <summary>
      <span>Recovery &amp; body metrics</span>
      <svg class="disclosure" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="m6 9 6 6 6-6" />
      </svg>
    </summary>
    <div class="record-content">
      <p v-if="readonly" class="micro-copy">{{ readonlyNote }}</p>
      <form class="record-form" novalidate :aria-busy="readinessState.loading || readinessState.saving"
        @submit.prevent="saveReadiness" @input="readinessState.saved = false" @change="readinessState.saved = false">
        <header class="form-heading">
          <h3>Recovery</h3>
          <p class="micro-copy">For <time :datetime="date">{{ date }}</time> · Session: {{ sessionId }}</p>
        </header>
        <p v-if="readinessState.loading" class="micro-copy" role="status">Loading recovery…</p>
        <div v-if="readinessState.loadError" class="load-failure">
          <p class="error" role="alert">{{ readinessState.loadError }} Inputs are unavailable until a successful reload.</p>
          <button type="button" class="secondary-button" :disabled="readinessState.loading" @click="retryReadiness">Retry recovery</button>
        </div>
        <fieldset :disabled="readonly || !readinessState.loaded || readinessState.loading || readinessState.saving">
          <legend class="sr-only">Recovery for {{ date }}, session {{ sessionId }}</legend>
          <div class="rating-fields">
            <label v-for="rating in ratings" :key="rating.key" class="field">
              <span class="field-label">{{ rating.label }}</span>
              <select v-model="readiness[rating.key]" :name="rating.key">
                <option value="">Not recorded</option>
                <option v-for="value in 7" :key="value" :value="String(value)">
                  {{ value }}{{ value === 1 ? ` — ${rating.low}` : value === 7 ? ` — ${rating.high}` : '' }}
                </option>
              </select>
              <span class="field-hint">1 {{ rating.low }} · 7 {{ rating.high }}</span>
            </label>
          </div>
          <div class="field-grid">
            <label class="field">
              <span class="field-label">HRV <span class="unit">ms</span></span>
              <input v-model="readiness.hrv" name="hrv" type="number" inputmode="decimal" min="0" step="any" placeholder="Optional">
            </label>
            <label class="field">
              <span class="field-label">Resting HR <span class="unit">bpm</span></span>
              <input v-model="readiness.rhr" name="rhr" type="number" inputmode="decimal" min="0" step="any" placeholder="Optional">
            </label>
            <label class="field">
              <span class="field-label">Sleep score <span class="unit">0–100</span></span>
              <input v-model="readiness.sleep_score" name="sleep_score" type="number" inputmode="decimal" min="0" max="100" step="any" placeholder="Optional">
            </label>
            <label class="field">
              <span class="field-label">Session time <span class="unit">24h</span></span>
              <input v-model="readiness.session_time" name="session_time" type="time" step="60">
            </label>
          </div>
          <label class="pain-control">
            <input v-model="readiness.joint_pain" name="joint_pain" type="checkbox">
            <span>Joint pain today</span>
          </label>
          <p v-if="readiness.joint_pain" class="pain-warning" role="status">Pain warning: avoid painful movements and seek qualified advice if pain persists. A readiness score does not override pain.</p>
          <label class="field">
            <span class="field-label">Note <span class="unit">optional · up to 2,000 characters</span></span>
            <textarea v-model="readiness.note" name="note" rows="3" maxlength="2000" placeholder="How you feel today"></textarea>
          </label>
        </fieldset>
        <div v-if="readinessState.loaded && !readinessState.loading" class="evaluation" aria-live="polite">
          <p class="evaluation-line">
            <span class="field-label">Readiness</span>
            <strong v-if="!completeEvaluation">Incomplete</strong>
            <strong v-else-if="score !== null">{{ score.toFixed(1) }}</strong>
            <span v-else>Score unavailable</span>
          </p>
          <p v-if="!completeEvaluation" class="micro-copy">At least 3 valid scored inputs are needed<span v-if="scoredInputs !== null">; {{ scoredInputs }} available</span>.</p>
          <p v-if="recoveryCoefficient" class="micro-copy" data-testid="recovery-coefficient">REC {{ recoveryCoefficient }} · recovery coefficient, not applied.</p>
          <p class="micro-copy">HRV and resting HR are raw measurements until each has 28 valid baseline days.</p>
          <div v-if="evaluation?.baseline" class="baseline-line">
            <span v-for="key in ['hrv', 'rhr']" :key="key">
              {{ key === 'hrv' ? 'HRV' : 'Resting HR' }}:
              <template v-if="typeof evaluation.baseline[key]?.count === 'number'">
                {{ evaluation.baseline[key].count >= 28 ? 'baseline ready' : 'baseline pending' }}
                · {{ evaluation.baseline[key].count }} valid days
              </template>
              <template v-else>baseline unavailable</template>
            </span>
          </div>
          <p v-if="timeAdjustment" class="micro-copy">Session-time guidance: {{ timeAdjustment }} · not applied.</p>
          <p class="micro-copy advice-only">Advice only — never changes prescribed loads.</p>
        </div>
        <p v-if="readinessState.saveError" class="error" role="alert">{{ readinessState.saveError }}</p>
        <div class="form-actions">
          <button type="submit" :disabled="readonly || !readinessState.loaded || readinessState.loading || readinessState.saving">
            {{ readinessState.saving ? 'Saving recovery…' : 'Save recovery' }}
          </button>
          <span v-if="readinessState.saved" class="save-success" role="status">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
            Saved
          </span>
        </div>
      </form>

      <form class="record-form body-form" novalidate :aria-busy="bodyState.loading || bodyState.saving"
        @submit.prevent="saveBody" @input="bodyState.saved = false" @change="bodyState.saved = false">
        <header class="form-heading">
          <h3>Body metrics</h3>
          <p class="micro-copy">Measurements for <time :datetime="date">{{ date }}</time> · Shared across this date’s sessions.</p>
        </header>
        <p v-if="bodyState.loading" class="micro-copy" role="status">Loading body metrics…</p>
        <div v-if="bodyState.loadError" class="load-failure">
          <p class="error" role="alert">{{ bodyState.loadError }} Inputs are unavailable until a successful reload.</p>
          <button type="button" class="secondary-button" :disabled="bodyState.loading" @click="retryBody">Retry body metrics</button>
        </div>
        <p v-if="bodyState.loaded && !bodyState.loading && priorBodyweight" class="bodyweight-source">
          Past bodyweight source: <strong>{{ priorBodyweight.value }} kg</strong> from
          <time :datetime="priorBodyweight.date">{{ priorBodyweight.date }}</time>.
          Not copied into this date’s fields.
        </p>
        <fieldset :disabled="readonly || !bodyState.loaded || bodyState.loading || bodyState.saving">
          <legend class="sr-only">Body metrics for {{ date }}</legend>
          <div class="field-grid">
            <label class="field">
              <span class="field-label">Bodyweight <span class="unit">kg</span></span>
              <input v-model="body.bodyweight" name="bodyweight" type="number" inputmode="decimal" min="0" step="any" placeholder="Optional">
            </label>
            <label class="field">
              <span class="field-label">Body fat <span class="unit">%</span></span>
              <input v-model="body.bodyfat" name="bodyfat" type="number" inputmode="decimal" min="0" max="100" step="any" placeholder="Optional">
            </label>
          </div>
          <p class="measurement-heading">Circumferences <span class="unit">cm · all optional</span></p>
          <div class="field-grid">
            <label v-for="measurement in measurementFields" :key="measurement.key" class="field">
              <span class="field-label">{{ measurement.label }} <span class="unit">cm</span></span>
              <input v-model="body.measurements[measurement.key]" :name="measurement.key" type="number" inputmode="decimal" min="0" step="any" placeholder="Optional">
            </label>
          </div>
        </fieldset>
        <p class="micro-copy">Blank fields stay unrecorded. Saving affects only the date shown above.</p>
        <p v-if="bodyState.saveError" class="error" role="alert">{{ bodyState.saveError }}</p>
        <div class="form-actions">
          <button type="submit" :disabled="readonly || !bodyState.loaded || bodyState.loading || bodyState.saving">
            {{ bodyState.saving ? 'Saving body metrics…' : 'Save body metrics' }}
          </button>
          <span v-if="bodyState.saved" class="save-success" role="status">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
            Saved
          </span>
        </div>
      </form>
    </div>
  </details>
</template>

<style scoped>
.daily-record { min-width: 0; width: 100%; border-block: 1px solid var(--line); color: var(--ink); font-family: var(--sans); }
.daily-record *, .daily-record *::before, .daily-record *::after { box-sizing: border-box; }
summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; padding: 10px 0; cursor: pointer; list-style: none; font: 600 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; }
summary::-webkit-details-marker { display: none; }
summary span { min-width: 0; overflow-wrap: anywhere; }
.disclosure { flex: 0 0 18px; width: 18px; height: 18px; }
svg path { stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
details[open] > summary .disclosure { transform: rotate(180deg); }
.record-content { min-width: 0; padding: 2px 0 18px; }
.record-form { min-width: 0; margin: 0; }
.body-form { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--line-soft); }
.form-heading { margin-bottom: 14px; }
h3 { margin: 0 0 5px; font-family: var(--display); font-weight: 800; text-transform: uppercase; font-size: 22px; line-height: 1.2; font-weight: 500; }
p { margin: 0 0 10px; overflow-wrap: anywhere; }
.micro-copy, .field-hint, .baseline-line, .bodyweight-source { color: var(--muted); font-size: 12px; line-height: 1.5; }
fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }
.rating-fields, .field-grid { display: grid; min-width: 0; gap: 12px; margin-bottom: 14px; }
.rating-fields { grid-template-columns: minmax(0, 1fr); }
.field-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.field { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.field-label, .measurement-heading { font-size: 12px; font-weight: 650; line-height: 1.5; overflow-wrap: anywhere; }
.unit { color: var(--muted); font-weight: 400; }
input:not([type='checkbox']), select, textarea { display: block; width: 100%; min-width: 0; max-width: 100%; min-height: 44px; margin: 0; padding: 9px 10px; border: 1px solid var(--line); border-radius: 3px; background: var(--panel); color: var(--ink); font-family: var(--sans); font-size: 16px; line-height: 1.4; }
input[type='time'] { appearance: none; }
input::placeholder, textarea::placeholder { color: var(--muted); opacity: 1; }
textarea { resize: vertical; }
.pain-control { display: flex; align-items: center; gap: 10px; min-height: 44px; margin-bottom: 8px; cursor: pointer; font-size: 13px; }
.pain-control input { flex: 0 0 20px; width: 20px; height: 20px; margin: 0; accent-color: var(--accent); }
.pain-warning, .error { color: var(--accent); font-size: 13px; line-height: 1.5; }
.pain-warning { padding-left: 10px; border-left: 2px solid var(--accent); }
.evaluation { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line-soft); }
.evaluation-line { display: flex; align-items: baseline; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
.evaluation-line strong { font-size: 16px; }
.baseline-line { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-bottom: 10px; }
.advice-only { color: var(--ink); }
.bodyweight-source { padding-left: 10px; border-left: 2px solid var(--line); }
.form-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; margin-top: 12px; }
button { min-width: 44px; max-width: 100%; min-height: 44px; padding: 10px 14px; border: 1px solid var(--ink); border-radius: 3px; background: var(--ink); color: var(--panel); font-family: var(--sans); font-size: 13px; font-weight: 650; line-height: 1.5; white-space: normal; overflow-wrap: anywhere; cursor: pointer; }
.secondary-button { margin-bottom: 12px; border-color: var(--line); background: transparent; color: var(--ink); }
button:disabled { opacity: .55; cursor: not-allowed; }
fieldset:disabled { opacity: .7; }
fieldset:disabled .pain-control { cursor: default; }
.save-success { display: inline-flex; align-items: center; gap: 5px; color: var(--accessory); font-size: 13px; }
.save-success svg { width: 20px; height: 20px; }
summary:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
@media (min-width: 600px) { .rating-fields { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
