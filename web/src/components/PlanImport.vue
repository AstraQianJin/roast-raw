<script setup>
import { computed, getCurrentInstance, onBeforeUnmount, ref, shallowRef } from 'vue';

const prefix = `plan-import-${getCurrentInstance().uid}`;
const maxBytes = 2_000_000;
const file = shallowRef(null);
const preview = shallowRef(null);
const acknowledged = ref(false);
const pending = ref('');
const error = shallowRef(null);
const success = shallowRef(null);
const expanded = ref({ current: false, candidate: false });
let requestId = 0;
let controller;
let disposed = false;

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const hexId = value => typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value);
const nonempty = value => typeof value === 'string' && value.trim().length > 0;
const display = value => value === null ? 'Not specified (null)' : value === undefined ? 'Not supplied'
  : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
const countFields = [
  ['weeks', 'Weeks'], ['sessions', 'Sessions'], ['workouts', 'Workout rows'], ['sets', 'Working sets'],
  ['tonnageKg', 'Planned tonnage (kg)'],
];
const contextFields = [
  ['profile', 'Profile'], ['prescriptionPolicy', 'Prescription policy'], ['testPlan', 'Test dates and plan'],
];
const issueFields = [
  ['file', 'File'], ['week', 'Week'], ['day', 'Day'], ['movement', 'Movement'],
  ['field', 'Field'], ['expected', 'Expected'],
];
const validPreview = computed(() => !!preview.value && preview.value.file === file.value);
const confirming = computed(() => pending.value === 'confirm');
const canConfirm = computed(() => validPreview.value && acknowledged.value && !pending.value && !success.value);
const columns = computed(() => validPreview.value ? [
  { key: 'current', title: 'Current cycle', note: 'To be archived · read-only',
    id: preview.value.payload.currentId, summary: preview.value.payload.current, plan: preview.value.payload.currentPlan },
  { key: 'candidate', title: 'New cycle', note: 'To become active',
    id: preview.value.payload.candidateId, summary: preview.value.payload.candidate, plan: preview.value.payload.candidatePlan },
] : []);

function clearPreview() {
  preview.value = null;
  acknowledged.value = false;
  expanded.value = { current: false, candidate: false };
}
function invalidate() {
  ++requestId;
  controller?.abort();
  pending.value = '';
  clearPreview();
}
function fileProblem(selected) {
  if (!/\.json$/i.test(selected.name)) return 'Choose a JSON file (.json). Other file types are not accepted.';
  if (!selected.size) return 'The selected file is empty. Choose a complete plan JSON file.';
  if (selected.size > maxBytes) return 'The UTF-8 file must be no larger than 2 MB (2,000,000 bytes).';
  return '';
}
function changeFile(event) {
  if (confirming.value || success.value) return;
  invalidate();
  error.value = null;
  file.value = event.target.files?.[0] ?? null;
  const problem = file.value && fileProblem(file.value);
  if (problem) error.value = { message: problem, issues: [], uncertain: false };
}
function cancel() {
  if (confirming.value || success.value) return;
  invalidate();
  error.value = null;
}
function begin(action) {
  controller?.abort();
  const context = { id: ++requestId, file: file.value, controller: new AbortController() };
  controller = context.controller;
  pending.value = action;
  error.value = null;
  return context;
}
function current(context) {
  return !disposed && context.id === requestId && context.file === file.value && !context.controller.signal.aborted;
}
function failureFrom(payload, fallback) {
  const detail = payload?.detail;
  const message = payload?.error ?? (object(detail) ? detail.error ?? detail.message ?? detail : detail);
  const failure = new Error(message === undefined || message === null || message === '' ? fallback : display(message));
  const issues = payload?.errors ?? (object(detail) ? detail.errors : null);
  failure.issues = Array.isArray(issues) ? issues : [];
  return failure;
}
async function post(path, body, context) {
  const response = await fetch(path, {
    method: 'POST', cache: 'no-store', signal: context.controller.signal,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  let payload;
  try { payload = await response.json(); }
  catch {
    throw new Error(response.ok ? 'The server returned an unreadable response.' : `Request failed (${response.status}).`);
  }
  if (!response.ok) throw failureFrom(payload, `Request failed (${response.status}).`);
  return payload;
}
function validatePreview(payload) {
  const keys = ['cycleId', 'name', 'startDate', 'endDate', ...countFields.map(([key]) => key),
    ...contextFields.map(([key]) => key)];
  const summary = value => object(value) && keys.every(key => Object.hasOwn(value, key))
    && nonempty(value.cycleId)
    && ['name', 'startDate', 'endDate'].every(key => value[key] === null || typeof value[key] === 'string')
    && countFields.every(([key]) => value[key] === null || (typeof value[key] === 'number'
      && Number.isFinite(value[key]) && value[key] >= 0));
  if (!object(payload) || !hexId(payload.currentId) || !hexId(payload.candidateId)
    || !hexId(payload.sourceSha256) || !summary(payload.current) || !summary(payload.candidate)
    || !object(payload.currentPlan) || !Object.keys(payload.currentPlan).length
    || !object(payload.candidatePlan) || !Object.keys(payload.candidatePlan).length
    || payload.current.cycleId === payload.candidate.cycleId) {
    throw new Error('The server returned an incomplete or invalid comparison. Preview again before confirming.');
  }
}
async function previewFile() {
  if (!file.value || pending.value || success.value) return;
  clearPreview();
  const context = begin('preview');
  try {
    const problem = fileProblem(context.file);
    if (problem) throw new Error(problem);
    const buffer = await context.file.arrayBuffer();
    if (!current(context)) return;
    if (buffer.byteLength > maxBytes) throw new Error('The UTF-8 file exceeds the 2 MB upload limit.');
    let text;
    try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(buffer); }
    catch { throw new Error('The file is not valid UTF-8. Save the source as UTF-8 JSON and select it again.'); }
    // Preserve original text, including any BOM. The server owns strict JSON and plan validation.
    const body = { plan_json: text, filename: context.file.name };
    const payload = await post('/api/plan/import/preview', body, context);
    if (!current(context)) return;
    validatePreview(payload);
    preview.value = { payload, body, file: context.file };
  } catch (failure) {
    if (!current(context)) return;
    clearPreview();
    error.value = { message: failure.message || 'Preview could not be loaded. Try again manually.',
      issues: failure.issues ?? [], uncertain: false };
  } finally {
    if (current(context)) pending.value = '';
  }
}
async function confirmImport() {
  if (!canConfirm.value) return;
  const selected = preview.value;
  const context = begin('confirm');
  try {
    const payload = await post('/api/plan/import/confirm', {
      ...selected.body, current_id: selected.payload.currentId,
      candidate_id: selected.payload.candidateId, confirm: true,
    }, context);
    if (!current(context)) return;
    if (payload?.saved !== true || payload.active_cycle_id !== selected.payload.candidate.cycleId
      || payload.archived_cycle_id !== selected.payload.current.cycleId) {
      throw new Error('The server did not acknowledge the reviewed activation and archive.');
    }
    success.value = payload;
    clearPreview();
  } catch (failure) {
    if (!current(context)) return;
    clearPreview();
    error.value = { message: failure.message || 'Activation was not acknowledged.',
      issues: failure.issues ?? [], uncertain: true };
  } finally {
    if (current(context)) pending.value = '';
  }
}
onBeforeUnmount(() => {
  disposed = true;
  ++requestId;
  controller?.abort();
});
</script>

<template>
  <section class="plan-import" data-testid="plan-import" :aria-busy="!!pending" :aria-labelledby="`${prefix}-heading`">
    <header>
      <p class="kicker">CYCLE IMPORT</p>
      <h2 :id="`${prefix}-heading`">A new cycle.<br><em>A preserved history.</em></h2>
      <p class="reading-note">Upload a complete JSON plan for strict validation. Previewing does not activate it. Confirming archives the current cycle and activates the reviewed new plan without overwriting historical records.</p>
    </header>

    <form class="upload-form" @submit.prevent="previewFile">
      <label :for="`${prefix}-file`">Plan JSON file</label>
      <input :id="`${prefix}-file`" data-testid="import-file" type="file" accept=".json,application/json"
        :disabled="confirming || !!success" :aria-describedby="`${prefix}-file-note`" @change="changeFile">
      <p :id="`${prefix}-file-note`" class="reading-note">UTF-8 JSON only · maximum 2 MB (2,000,000 bytes). Invalid input is rejected, not silently repaired.</p>
      <p v-if="file" class="file-name">Selected: {{ file.name }} · {{ file.size }} bytes</p>
      <button type="submit" data-testid="import-preview" :disabled="!file || !!pending || !!success">
        {{ pending === 'preview' ? 'Preparing preview…' : 'Preview plan' }}
      </button>
    </form>

    <p v-if="pending" class="reading-note" role="status">{{ confirming ? 'Waiting for activation acknowledgement. Keep this page open; file changes and cancellation are locked.' : 'Reading the file and requesting a strict comparison…' }}</p>

    <section v-if="error" class="import-error" data-testid="import-error" role="alert">
      <h3>{{ error.uncertain ? 'Activation not acknowledged' : 'File could not be previewed' }}</h3>
      <p class="error-message">{{ error.message }}</p>
      <ol v-if="error.issues.length" class="error-list" aria-label="Validation details">
        <li v-for="(issue, index) in error.issues" :key="index">
          <dl v-if="object(issue)">
            <template v-for="[key, label] in issueFields" :key="key">
              <div v-if="Object.hasOwn(issue, key)"><dt>{{ label }}</dt><dd>{{ display(issue[key]) }}</dd></div>
            </template>
          </dl>
          <p v-if="!object(issue) || !issueFields.some(([key]) => Object.hasOwn(issue, key))">{{ display(issue) }}</p>
        </li>
      </ol>
      <p v-if="error.uncertain" class="reading-note">The outcome is uncertain, including after a lost connection: the server may already have committed the change. Verify the active cycle and preview this file again before confirming. Your selected file is retained; nothing is retried automatically.</p>
      <a v-if="error.uncertain" href="/cycle">Open the cycle to verify the active cycle</a>
    </section>

    <section v-if="validPreview" class="comparison" data-testid="import-comparison" aria-label="Current and new plan comparison">
      <h3>Review both cycles.</h3>
      <p class="reading-note">Server-supplied plan values, not actual training statistics. Both complete plans are read-only below.</p>
      <div class="comparison-columns">
        <article v-for="column in columns" :key="column.key" class="cycle-column">
          <p class="kicker">{{ column.note }}</p>
          <h4>{{ column.title }}</h4>
          <p class="cycle-name">{{ display(column.summary.name) }}</p>
          <dl class="identity">
            <div><dt>Cycle ID</dt><dd><code :data-testid="column.key === 'current' ? 'import-current-id' : 'import-candidate-id'">{{ column.summary.cycleId }}</code></dd></div>
            <div><dt>Reviewed SHA-256</dt><dd><code>{{ column.id }}</code></dd></div>
            <div><dt>Start date</dt><dd>{{ display(column.summary.startDate) }}</dd></div>
            <div><dt>End date</dt><dd>{{ display(column.summary.endDate) }}</dd></div>
          </dl>
          <dl class="counts">
            <div v-for="[key, label] in countFields" :key="key"><dt>{{ label }}</dt><dd>{{ display(column.summary[key]) }}</dd></div>
          </dl>
          <dl class="context">
            <div v-for="[key, label] in contextFields" :key="key"><dt>{{ label }}</dt><dd><pre>{{ display(column.summary[key]) }}</pre></dd></div>
          </dl>
          <details @toggle="expanded[column.key] = $event.currentTarget.open">
            <summary>Complete {{ column.key === 'current' ? 'current' : 'new' }} plan JSON · read-only</summary>
            <pre v-if="expanded[column.key]" tabindex="0" :aria-label="`Complete ${column.title.toLowerCase()} JSON, read-only`">{{ JSON.stringify(column.plan, null, 2) }}</pre>
          </details>
        </article>
      </div>
      <p class="source-id">Source SHA-256 (server reported)<br><code>{{ preview.payload.sourceSha256 }}</code></p>
    </section>

    <div class="confirmation">
      <label class="confirm-label" :class="{ unavailable: !validPreview || confirming || !!success }">
        <input v-model="acknowledged" data-testid="import-confirm-check" type="checkbox" :disabled="!validPreview || !!pending || !!success">
        <span>I have reviewed both plans. I understand that the current cycle and its records will become a read-only archive, and the new plan will become active.</span>
      </label>
      <div class="actions">
        <button type="button" class="confirm-button" data-testid="import-confirm" :disabled="!canConfirm" @click="confirmImport">{{ confirming ? 'Confirming activation…' : 'Archive current and activate new plan' }}</button>
        <button type="button" data-testid="import-cancel" :disabled="confirming || !!success" @click="cancel">Cancel preview</button>
      </div>
      <p class="reading-note">Cancelling clears the comparison and acknowledgement, retains your file, and sends no write request. Confirmation cannot be cancelled once sent.</p>
    </div>

    <section v-if="success" class="import-success" data-testid="import-success" role="status">
      <h3>New cycle activated.</h3>
      <p>The server acknowledged that the reviewed plan was saved and the previous cycle was archived.</p>
      <dl class="identity">
        <div><dt>Active cycle</dt><dd><code>{{ success.active_cycle_id }}</code></dd></div>
        <div><dt>Archived cycle · read-only</dt><dd><code>{{ success.archived_cycle_id }}</code></dd></div>
      </dl>
      <a href="/cycle" data-testid="import-open-plan">Open the new active cycle</a>
      <p class="reading-note">This link reloads the active plan from the server.</p>
    </section>
  </section>
</template>

<style scoped>
.plan-import { box-sizing: border-box; min-width: 0; width: 100%; max-width: 100%; margin: 24px 0; padding: 20px 16px; border: 1px solid var(--line); color: var(--ink); background: var(--panel); font: 14px/1.6 var(--sans); overflow-wrap: anywhere; }
.plan-import *, .plan-import *::before, .plan-import *::after { box-sizing: border-box; }
p, h2, h3, h4, dl, dd, pre { margin: 0; }
h2 { margin-top: 8px; font: 800 clamp(28px, 5vw, 36px)/1.15 var(--display); }
h2 em { color: var(--muted); font-weight: 400; }
h3 { font: 800 26px/1.25 var(--display); }
h4 { font: 800 24px/1.3 var(--display); }
.kicker { color: var(--accent); font: 11px/1.6 var(--mono); letter-spacing: .06em; text-transform: uppercase; }
.reading-note { margin-top: 10px; max-width: 75ch; color: var(--muted); font: 12px/1.7 var(--sans); }
.upload-form { display: grid; gap: 10px; min-width: 0; margin-top: 22px; }
.upload-form > label { display: flex; align-items: center; min-height: 44px; font-weight: 600; }
.upload-form .reading-note { margin: 0; }
input[type='file'] { width: 100%; min-width: 0; min-height: 44px; padding: 8px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--panel2); font: 12px var(--sans); }
input[type='file']::file-selector-button { min-height: 44px; margin-right: 8px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--panel); font: inherit; cursor: pointer; }
.file-name, .source-id { color: var(--muted); font: 11px/1.7 var(--mono); }
button, a { min-width: 44px; min-height: 44px; max-width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--panel); font: 12px/1.6 var(--sans); white-space: normal; overflow-wrap: anywhere; cursor: pointer; }
button { text-align: left; }
a { display: inline-flex; align-items: center; margin-top: 14px; text-underline-offset: 4px; }
button:hover:not(:disabled), a:hover { border-color: var(--accent); background: var(--panel2); }
button:disabled, input:disabled { opacity: .6; cursor: not-allowed; }
:is(button, input, summary, a, pre):focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.upload-form > button { justify-self: start; }
.comparison, .confirmation { min-width: 0; margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--line); }
.comparison-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; margin-top: 20px; }
.cycle-column { min-width: 0; padding-top: 12px; border-top: 2px solid var(--line); }
.cycle-column:last-child { border-top-color: var(--accent); }
.cycle-column h4 { margin-top: 8px; }
.cycle-name { margin-top: 6px; font-weight: 600; }
.identity, .context { display: grid; gap: 12px; margin-top: 16px; }
dt { color: var(--muted); font: 11px/1.7 var(--sans); }
dd { min-width: 0; margin-top: 3px; font: 12px/1.7 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; }
code { color: var(--ink); font: inherit; white-space: normal; overflow-wrap: anywhere; }
.counts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 10px; margin-top: 18px; padding: 14px 0; border-top: 1px solid var(--line-soft); border-bottom: 1px solid var(--line-soft); }
.counts > div { min-width: 0; }
.counts dd { font: 600 20px/1.4 var(--mono); }
pre { min-width: 0; max-width: 100%; font: 11px/1.7 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 2; }
details { min-width: 0; margin-top: 16px; border-top: 1px solid var(--line); }
summary { min-width: 44px; min-height: 44px; padding: 12px 4px; font: 12px/1.6 var(--sans); cursor: pointer; }
summary:hover { background: var(--panel2); }
details > pre { margin-top: 8px; padding: 12px; border: 1px solid var(--line-soft); background: var(--panel2); }
.source-id { margin-top: 20px; }
.confirm-label { display: flex; align-items: flex-start; gap: 10px; min-height: 44px; padding: 10px 0; font-size: 12px; cursor: pointer; }
.confirm-label input { flex: 0 0 44px; width: 44px; height: 44px; margin: 0; accent-color: var(--accent); }
.confirm-label span { min-width: 0; }
.confirm-label.unavailable { color: var(--muted); cursor: default; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
.actions .confirm-button { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.import-error, .import-success { min-width: 0; margin-top: 20px; padding: 16px 12px; border: 1px solid var(--accent); }
.import-error { border-left-width: 3px; }
.import-error > p, .import-success > p { margin-top: 10px; }
.error-message { white-space: pre-wrap; }
.error-list { margin: 12px 0 0; padding-left: 22px; }
.error-list li { min-width: 0; padding: 10px 0; border-top: 1px solid var(--line-soft); }
.error-list dl { display: grid; gap: 6px; }
@media (max-width: 600px) {
  .comparison-columns { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 420px) {
  .plan-import { padding: 16px 12px; }
  .upload-form > button, .actions button { width: 100%; }
  .comparison-columns { gap: 22px; }
}
</style>
