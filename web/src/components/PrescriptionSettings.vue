<script setup>
import { computed, getCurrentInstance, onBeforeUnmount, reactive, ref, watch } from 'vue';

const props = defineProps({ cycleId: { type: String, required: true } });
const emit = defineEmits(['changed']);
const inputPrefix = `prescription-${getCurrentInstance().uid}`;
const settings = ref(null);
const references = reactive({});
const badInputs = reactive({});
const familyOpen = reactive({ S: false, B: false, D: false });
const loaded = ref(false);
const pending = ref('');
const error = ref('');
const success = ref('');
const stale = ref(false);
const review = ref(null);
let sequence = 0;
let controller;
let disposed = false;

const families = computed(() => [
  { id: 'S', name: 'Squat' }, { id: 'B', name: 'Bench press' }, { id: 'D', name: 'Deadlift' },
].map((family) => ({
  ...family, entries: (settings.value?.catalogue ?? []).filter((entry) => entry.lift === family.id),
})).filter((family) => family.entries.length));
const frozen = computed(() => !!pending.value || !loaded.value);
const canRequest = computed(() => !frozen.value && !stale.value);
const validation = computed(() => Object.fromEntries((settings.value?.catalogue ?? []).map((entry) => {
  const raw = String(references[entry.id] ?? '').trim();
  let message = '';
  if (badInputs[entry.id]) message = 'Enter a finite number greater than zero.';
  else if (!raw && requiredReference(entry)) message = 'A positive reference 1RM is required for this approved variation.';
  else if (raw && (!Number.isFinite(Number(raw)) || Number(raw) <= 0)) message = 'Enter a finite number greater than zero, or leave an optional reference blank.';
  return [entry.id, message];
})));
const validReferences = computed(() => Object.values(validation.value).every((message) => !message));
const rowGroups = computed(() => {
  const rows = review.value?.changes ?? [];
  return [
    { id: 'first', remaining: false, rows: rows.slice(0, 3) },
    { id: 'remaining', remaining: true, rows: rows.slice(3) },
  ].filter((group) => group.rows.length);
});
const busyLabel = computed(() => ({
  load: 'Loading settings…', preview: 'Preparing preview…', apply: 'Applying reviewed prescription…',
  compare: 'Loading version comparison…', restore: 'Restoring reviewed version…',
})[pending.value] ?? '');

function requiredReference(entry) {
  return entry.default !== null && entry.default !== undefined;
}
function referenceGroups(family) {
  return [
    { id: 'approved', optional: false, entries: family.entries.filter(requiredReference) },
    { id: 'other', optional: true, entries: family.entries.filter(entry => !requiredReference(entry)) },
  ].filter(group => group.entries.length);
}
function policyLabel(policy) {
  return policy === 'eight-variations-v1' ? 'Eight-variation prescription' : 'Original prescription';
}
function display(value) {
  if (value === null || value === undefined || value === '') return 'Not specified';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}
function shortId(id) {
  return String(id).slice(0, 8);
}
function hasId(id) {
  return (typeof id === 'string' && id.trim().length > 0) || (typeof id === 'number' && Number.isFinite(id));
}
function timestamp(value) {
  if (!value) return 'Timestamp unavailable';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return String(value);
  return `${new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).format(date)} · Shanghai`;
}
function inputId(id) {
  return `${inputPrefix}-reference-${id}`;
}
function updateReference(entry, event) {
  references[entry.id] = event.target.value;
  badInputs[entry.id] = event.target.validity.badInput;
  if (review.value?.kind === 'preview') review.value = null;
  success.value = '';
  if (!stale.value) error.value = '';
}
function referencePayload() {
  return Object.fromEntries(settings.value.catalogue.map(({ id }) => {
    const value = String(references[id] ?? '').trim();
    return [id, value === '' ? null : Number(value)];
  }));
}
function isCurrent(context) {
  return !disposed && context.sequence === sequence && context.cycleId === props.cycleId;
}
function responseError(payload, fallback) {
  const detail = payload?.detail ?? payload?.message ?? payload?.error;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((entry) => typeof entry === 'string' ? entry : entry?.msg ?? entry?.message)
      .filter((message) => typeof message === 'string');
    if (messages.length) return messages.join('; ');
  }
  return fallback;
}
async function request(path, context, body, expectJson = true) {
  const response = await fetch(path, {
    cache: 'no-store', signal: context.controller.signal,
    ...(body === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }),
  });
  let payload = null;
  try {
    if (response.status !== 204) payload = await response.json();
  } catch {
    if (response.ok && expectJson) throw new Error('The server returned an unreadable response. Please retry manually.');
  }
  if (!response.ok) {
    const failure = new Error(responseError(payload, `Request failed (${response.status}). Please retry manually.`));
    failure.status = response.status;
    throw failure;
  }
  return payload;
}
async function run(action, work, keepSuccess = false) {
  controller?.abort();
  controller = new AbortController();
  const context = { sequence: ++sequence, cycleId: props.cycleId, controller };
  pending.value = action;
  error.value = '';
  if (!keepSuccess) success.value = '';
  try {
    await work(context);
  } catch (failure) {
    if (!isCurrent(context)) return;
    if (action === 'load') loaded.value = false;
    if (failure.status === 409) {
      stale.value = true;
      review.value = null;
      error.value = 'The current prescription has changed. Refresh settings before trying again. Your draft reference values have been kept.';
    } else {
      const prefix = action === 'load' ? 'Settings could not be loaded. ' : '';
      error.value = `${prefix}${failure.message || 'The request failed. Please retry manually.'}`;
    }
  } finally {
    if (isCurrent(context)) pending.value = '';
  }
}
function validateSettings(payload, cycleId) {
  const nullableNumber = (value) => value === null || (typeof value === 'number' && Number.isFinite(value));
  if (!payload || payload.cycle_id !== cycleId || !hasId(payload.currentId)
    || typeof payload.policy !== 'string' || !Array.isArray(payload.catalogue)
    || !Array.isArray(payload.versions) || !payload.references || typeof payload.references !== 'object'
    || Array.isArray(payload.references)
    || new Set(payload.catalogue.map((entry) => String(entry?.id))).size !== payload.catalogue.length
    || payload.catalogue.some((entry) => !entry || !hasId(entry.id) || typeof entry.name !== 'string'
      || !['S', 'B', 'D'].includes(entry.lift) || typeof entry.system !== 'boolean'
      || !nullableNumber(entry.default) || !nullableNumber(entry.transfer)
      || (Object.hasOwn(payload.references, entry.id) && !nullableNumber(payload.references[entry.id])))
    || payload.versions.some((version) => !version || !hasId(version.id))) {
    throw new Error('The server returned invalid prescription settings. Refresh before making changes.');
  }
}
function validateChanges(payload) {
  if (!payload || !Array.isArray(payload.changes)
    || payload.changes.some((row) => !row || typeof row !== 'object' || Array.isArray(row))) {
    throw new Error('The server returned an invalid comparison. Please retry manually.');
  }
}
async function loadSettings(preserveDrafts = false, keepSuccess = false) {
  loaded.value = false;
  review.value = null;
  if (!props.cycleId) {
    error.value = 'Select a training cycle to load prescription settings.';
    return;
  }
  await run('load', async (context) => {
    const payload = await request(`/api/prescription?${new URLSearchParams({ cycle_id: context.cycleId })}`, context);
    if (!isCurrent(context)) return;
    validateSettings(payload, context.cycleId);
    const next = Object.fromEntries(payload.catalogue.map((entry) => [entry.id,
      preserveDrafts && Object.hasOwn(references, entry.id)
        ? references[entry.id] : payload.references[entry.id] == null ? '' : String(payload.references[entry.id]),
    ]));
    for (const key of Object.keys(references)) {
      if (!Object.hasOwn(next, key)) delete references[key];
    }
    Object.assign(references, next);
    if (!preserveDrafts) {
      for (const key of Object.keys(badInputs)) delete badInputs[key];
      for (const family of ['S', 'B', 'D']) {
        familyOpen[family] = payload.catalogue.some((entry) => entry.lift === family
          && (requiredReference(entry) || payload.references[entry.id] != null));
      }
    }
    settings.value = payload;
    loaded.value = true;
    stale.value = false;
  }, keepSuccess);
}
async function previewPrescription() {
  if (!canRequest.value || !validReferences.value) return;
  const body = { cycle_id: props.cycleId, current_id: settings.value.currentId, references: referencePayload() };
  review.value = null;
  await run('preview', async (context) => {
    const payload = await request('/api/prescription/preview', context, body);
    if (!isCurrent(context)) return;
    validateChanges(payload);
    if (!hasId(payload.previewId)) throw new Error('The preview has no review ID. Please retry manually.');
    if (payload.currentId !== body.current_id) {
      const failure = new Error('The preview belongs to a different current prescription.');
      failure.status = 409;
      throw failure;
    }
    review.value = { kind: 'preview', id: payload.previewId, currentId: payload.currentId, body, changes: payload.changes };
  });
}
async function compareVersion(version) {
  if (!canRequest.value) return;
  const currentId = settings.value.currentId;
  review.value = null;
  await run('compare', async (context) => {
    const query = new URLSearchParams({ cycle_id: context.cycleId, revision_id: version.id });
    const payload = await request(`/api/prescription/version?${query}`, context);
    if (!isCurrent(context)) return;
    validateChanges(payload);
    if (payload.id !== version.id) throw new Error('The server returned a different version. Please compare again.');
    review.value = { kind: 'version', id: version.id, currentId, version, changes: payload.changes };
  });
}
async function applyPrescription() {
  const selected = review.value;
  if (!canRequest.value || !validReferences.value || selected?.kind !== 'preview'
    || selected.currentId !== settings.value.currentId) return;
  await run('apply', async (context) => {
    const result = await request('/api/prescription/apply', context, { ...selected.body, preview_id: selected.id });
    if (!isCurrent(context)) return;
    if (result?.saved !== true || result.id !== selected.id) throw new Error('The save could not be confirmed. Refresh before retrying.');
    success.value = 'Reviewed prescription applied.';
    review.value = null;
    emit('changed');
    if (isCurrent(context)) await loadSettings(false, true);
  });
}
async function restoreVersion() {
  const selected = review.value;
  if (!canRequest.value || selected?.kind !== 'version' || selected.version.current
    || selected.currentId !== settings.value.currentId || selected.id === settings.value.currentId) return;
  await run('restore', async (context) => {
    const result = await request('/api/prescription/restore', context, {
      cycle_id: context.cycleId, current_id: selected.currentId, revision_id: selected.id,
    });
    if (!isCurrent(context)) return;
    if (result?.saved !== true || result.id !== selected.id) throw new Error('The restore could not be confirmed. Refresh before retrying.');
    success.value = 'Reviewed prescription version restored.';
    review.value = null;
    emit('changed');
    if (isCurrent(context)) await loadSettings(false, true);
  });
}
watch(() => props.cycleId, () => {
  ++sequence;
  controller?.abort();
  pending.value = '';
  settings.value = null;
  loaded.value = false;
  error.value = '';
  success.value = '';
  stale.value = false;
  review.value = null;
  for (const key of Object.keys(references)) delete references[key];
  for (const key of Object.keys(badInputs)) delete badInputs[key];
  void loadSettings();
}, { immediate: true, flush: 'sync' });
onBeforeUnmount(() => {
  disposed = true;
  ++sequence;
  controller?.abort();
});
</script>

<template>
  <details class="prescription-settings" data-testid="prescription-settings" :aria-busy="!!pending">
    <summary class="settings-summary">
      <span>Prescription settings</span>
      <span v-if="settings" class="policy-tag">{{ policyLabel(settings.policy) }}</span>
    </summary>
    <div class="settings-content">
      <p class="settings-description">Manual reference 1RMs are not automatically derived from estimated performance. Editing these fields alone never changes your prescription.</p>
      <p v-if="pending" class="request-status" role="status">{{ busyLabel }}</p>
      <div v-if="error" class="prescription-error" role="alert">
        <p>{{ error }}</p>
        <button v-if="!loaded || stale" type="button" :disabled="!!pending || !cycleId" @click="loadSettings(true, true)">
          {{ stale ? 'Refresh settings — keep draft values' : 'Retry loading settings' }}
        </button>
      </div>
      <p v-if="success" class="prescription-success" role="status">{{ success }}</p>

      <template v-if="settings">
        <p class="current-version">Current version <span :title="String(settings.currentId)">{{ shortId(settings.currentId) }}</span></p>
        <form class="reference-form" novalidate @submit.prevent="previewPrescription">
          <p :id="`${inputPrefix}-guidance`" class="reference-guidance">Reference loads are in kg. Approved variations require a positive value; other references may be left blank. Preview first, then explicitly apply.</p>
          <fieldset :disabled="frozen">
            <legend>Manual reference 1RMs</legend>
            <details v-for="family in families" :key="family.id" class="reference-family" :open="familyOpen[family.id]" @toggle="familyOpen[family.id] = $event.target.open">
              <summary>{{ family.id }} · {{ family.name }} <span>{{ family.entries.length }} movements</span></summary>
              <component :is="group.optional ? 'details' : 'div'" v-for="group in referenceGroups(family)" :key="group.id" class="reference-group">
                <summary v-if="group.optional">Other library references · {{ group.entries.length }} movements</summary>
                <div class="reference-grid">
                <div v-for="entry in group.entries" :key="entry.id" class="reference-field">
                  <label :for="inputId(entry.id)">{{ entry.name }}</label>
                  <div class="reference-load">
                    <input :id="inputId(entry.id)" class="reference-input" :name="String(entry.id)" type="number" inputmode="decimal" :min="Number.MIN_VALUE" step="any" :required="requiredReference(entry)" :disabled="frozen" :value="references[entry.id]" :aria-invalid="!!validation[entry.id]" :aria-describedby="`${inputId(entry.id)}-note ${inputPrefix}-guidance`" :placeholder="requiredReference(entry) ? 'Enter 1RM' : 'Optional'" @input="updateReference(entry, $event)">
                    <span>kg</span>
                  </div>
                  <div :id="`${inputId(entry.id)}-note`" class="reference-note">
                    <p>{{ entry.system ? 'Total system weight, not added weight: bodyweight plus added load, or minus assistance.' : 'Reference lifting load.' }}</p>
                    <p v-if="entry.default !== null">Approved baseline: {{ display(entry.default) }} kg.</p>
                    <p>{{ entry.transfer === null ? 'No user-experience transfer assigned.' : `User-experience transfer: ${display(entry.transfer)}.` }}</p>
                    <p v-if="validation[entry.id]" class="field-error">{{ validation[entry.id] }}</p>
                  </div>
                </div>
                </div>
              </component>
            </details>
          </fieldset>
          <p class="transfer-note">Transfer coefficients are user-experience capacity parameters, not research-derived prescription percentages. System-weight adjustments use bodyweight supplied by the server, not a calculation in this form.</p>
          <button class="preview-prescription" type="submit" :disabled="!canRequest || !validReferences">Preview prescription</button>
          <p class="draft-note">Closing this panel keeps your draft values. Any reference edit invalidates its preview.</p>
        </form>

        <details class="prescription-history">
          <summary>Prescription history <span>{{ settings.versions.length }} versions</span></summary>
          <p v-if="!settings.versions.length" class="empty-message">No saved versions available.</p>
          <ol v-else class="revision-list">
            <li v-for="version in settings.versions" :key="version.id">
              <div class="revision-meta">
                <div class="revision-heading"><span :title="String(version.id)">{{ shortId(version.id) }}</span><span v-if="version.current" class="current-tag">Current</span></div>
                <time :datetime="version.created_at">{{ timestamp(version.created_at) }}</time>
                <p>{{ policyLabel(version.policy) }}</p>
              </div>
              <button class="revision-compare" type="button" :disabled="!canRequest" :aria-label="`Compare version ${shortId(version.id)}`" @click="compareVersion(version)">Compare</button>
            </li>
          </ol>
        </details>

        <section v-if="review" :class="review.kind === 'preview' ? 'prescription-preview' : 'revision-comparison'" class="review-section" aria-live="polite">
          <h3>{{ review.kind === 'preview' ? 'Review prescription changes' : 'Review saved version' }}</h3>
          <p v-if="review.kind === 'version'" class="review-version">{{ shortId(review.id) }} · {{ timestamp(review.version.created_at) }} · {{ policyLabel(review.version.policy) }}</p>
          <p class="review-note">{{ review.kind === 'preview' ? 'Current → proposed prescription.' : 'Current → selected saved version. Comparisons are supplied by the server.' }} Dates, sets, reps and target RPE are preserved when applying reference changes.</p>
          <p v-if="!review.changes.length" class="empty-message">No load or prescription differences reported.</p>
          <component :is="group.remaining ? 'details' : 'div'" v-for="group in rowGroups" :key="`${review.kind}-${review.id}-${group.id}`" class="change-group">
            <summary v-if="group.remaining">All remaining dated rows ({{ group.rows.length }})</summary>
            <ol class="change-list">
              <li v-for="(row, index) in group.rows" :key="`${row.key ?? index}-${index}`" class="change-row">
                <header><time :datetime="row.date">{{ display(row.date) }}</time><strong>{{ display(row.movement) }}</strong></header>
                <div class="load-comparison">
                  <div><span>Current load</span><strong>{{ display(row.oldLoad) }} <small v-if="row.oldLoad != null">kg</small></strong></div>
                  <div><span>{{ review.kind === 'preview' ? 'Proposed load' : 'Saved load' }}</span><strong>{{ display(row.newLoad) }} <small v-if="row.newLoad != null">kg</small></strong></div>
                </div>
                <p class="preserved-fields">Sets: {{ display(row.sets) }} · Reps: {{ display(row.reps) }} · Target RPE: {{ display(row.targetRpe) }}</p>
                <dl class="change-facts">
                  <div><dt>Current prescription</dt><dd>{{ display(row.oldRx) }}</dd></div>
                  <div><dt>{{ review.kind === 'preview' ? 'Proposed prescription' : 'Saved prescription' }}</dt><dd>{{ display(row.newRx) }}</dd></div>
                  <div><dt>Basis</dt><dd>{{ display(row.basis) }}</dd></div>
                  <div><dt>Reference 1RM</dt><dd>{{ display(row.reference) }}<template v-if="row.reference != null"> kg</template></dd></div>
                  <div><dt>Prescription proportion</dt><dd>{{ display(row.percent) }}<template v-if="row.percent != null">%</template></dd></div>
                  <div><dt>Weight basis</dt><dd>{{ row.system ? 'Total system weight, not added weight' : 'Lifting load' }}</dd></div>
                </dl>
              </li>
            </ol>
          </component>
          <p v-if="review.kind === 'version'" class="restore-note">Restoring replaces the current prescription and reference values. Unsaved reference edits are replaced only after a successful restore.</p>
          <button v-if="review.kind === 'preview'" class="apply-prescription" type="button" :disabled="!canRequest || !validReferences" @click="applyPrescription">Apply reviewed prescription</button>
          <button v-else class="revision-restore" type="button" :disabled="!canRequest || review.version.current || review.id === settings.currentId" @click="restoreVersion">Restore reviewed version</button>
        </section>
      </template>
    </div>
  </details>
</template>

<style scoped>
.prescription-settings {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  margin: 20px 0;
  border: 1px solid var(--line);
  color: var(--ink);
  background: var(--surface, var(--panel));
  overflow-wrap: anywhere;
}
.prescription-settings *, .prescription-settings *::before, .prescription-settings *::after { box-sizing: border-box; }
.prescription-settings summary { min-height: 48px; padding: 12px; cursor: pointer; }
.settings-summary { font-weight: 600; }
.policy-tag { display: inline-block; margin: 4px 0 0 8px; color: var(--muted); font-size: 12px; font-weight: 400; }
.settings-content { display: grid; gap: 16px; padding: 16px; border-top: 1px solid var(--line); min-width: 0; }
.settings-content p { margin: 0; line-height: 1.6; }
.settings-description { max-width: 70ch; }
.request-status, .current-version, .reference-guidance, .reference-note, .transfer-note, .draft-note,
.review-note, .review-version, .restore-note, .empty-message { color: var(--muted); font-size: 12px; }
.current-version span, .revision-heading > span:first-child { font-family: var(--mono, monospace); }
.prescription-error, .prescription-success { padding: 12px; border: 1px solid var(--accent); }
.prescription-error { border-left-width: 3px; }
.prescription-error button { margin-top: 10px; }
.prescription-success { color: var(--accent); }
.reference-form { display: grid; gap: 14px; min-width: 0; }
.reference-form fieldset { display: grid; gap: 10px; margin: 0; padding: 0; min-width: 0; border: 0; }
.reference-form legend { padding: 0 0 10px; color: var(--ink); font-weight: 600; }
.reference-family, .prescription-history, .change-group[open], details.change-group { min-width: 0; border: 1px solid var(--line); }
.reference-family > summary, .prescription-history > summary { font-weight: 600; }
.reference-family > summary span, .prescription-history > summary span { margin-left: 8px; color: var(--muted); font-size: 12px; font-weight: 400; }
.reference-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: 18px; padding: 12px; border-top: 1px solid var(--line); }
.reference-field { display: grid; gap: 8px; align-content: start; min-width: 0; }
.reference-field label { font-size: 14px; font-weight: 600; }
.reference-load { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px; }
.reference-input { width: 100%; min-width: 0; min-height: 52px; padding: 10px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--surface, var(--panel)); font: 600 22px/1.2 var(--mono, monospace); }
.reference-input::placeholder { font-size: 16px; font-weight: 400; color: var(--muted); }
.reference-input[aria-invalid='true'] { border-color: var(--accent); }
.reference-input:disabled { opacity: .65; cursor: not-allowed; }
.reference-load > span { color: var(--muted); font-size: 12px; }
.reference-note { display: grid; gap: 5px; }
.reference-note .field-error { color: var(--accent); }
.prescription-settings button { min-height: 44px; max-width: 100%; padding: 10px 14px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--surface, var(--panel)); font: inherit; line-height: 1.4; white-space: normal; overflow-wrap: anywhere; cursor: pointer; }
.prescription-settings button:hover:not(:disabled) { border-color: var(--accent); }
.prescription-settings button:disabled { opacity: .6; cursor: not-allowed; }
.prescription-settings :is(button, input, summary):focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.preview-prescription { justify-self: start; }
.prescription-settings .apply-prescription, .prescription-settings .revision-restore { border-color: var(--accent); color: var(--accent); font-weight: 600; }
.revision-list, .change-list { list-style: none; margin: 0; padding: 0; }
.revision-list > li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 12px; border-top: 1px solid var(--line); }
.revision-meta { min-width: 0; display: grid; gap: 4px; font-size: 12px; color: var(--muted); }
.revision-heading { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; color: var(--ink); }
.current-tag { padding: 2px 6px; border: 1px solid var(--line); font-size: 11px; }
.prescription-history .empty-message { padding: 12px; }
.review-section { display: grid; gap: 14px; min-width: 0; border-top: 1px solid var(--line); padding-top: 18px; }
.review-section h3 { margin: 0; font: 400 24px/1.2 var(--serif, Georgia, serif); }
.change-row { display: grid; gap: 12px; padding: 14px; min-width: 0; border: 1px solid var(--line); }
.change-row + .change-row { border-top: 0; }
.change-row header { display: grid; gap: 4px; }
.change-row header time { color: var(--muted); font-size: 12px; }
.change-row header strong { font-family: inherit; font-size: 14px; }
.load-comparison { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.load-comparison > div { min-width: 0; display: grid; gap: 5px; }
.load-comparison span { font-size: 11px; color: var(--muted); }
.load-comparison strong { font: 600 23px/1.3 var(--mono, monospace); font-variant-numeric: tabular-nums; }
.load-comparison small { font-size: 12px; font-weight: 400; }
.load-comparison > div:last-child strong { color: var(--accent); }
.preserved-fields { font-size: 12px; }
.change-facts { display: grid; gap: 8px; margin: 0; font-size: 12px; }
.change-facts > div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr); gap: 10px; }
.change-facts dt { color: var(--muted); }
.change-facts dd { margin: 0; min-width: 0; white-space: pre-wrap; }
.change-group > .change-list > .change-row { border-left: 0; border-right: 0; }
.change-group > .change-list > .change-row:last-child { border-bottom: 0; }
.change-group:not(details) > .change-list > .change-row { border-left: 1px solid var(--line); border-right: 1px solid var(--line); }
.change-group:not(details) > .change-list > .change-row:last-child { border-bottom: 1px solid var(--line); }
@media (max-width: 420px) {
  .settings-content { padding: 12px; }
  .policy-tag { display: block; margin-left: 0; }
  .reference-grid { grid-template-columns: minmax(0, 1fr); padding: 10px; }
  .revision-list > li { grid-template-columns: minmax(0, 1fr); }
  .revision-compare, .preview-prescription { width: 100%; }
  .change-row { padding: 10px; }
  .change-facts > div { grid-template-columns: minmax(0, 1fr); gap: 2px; }
  .load-comparison strong { font-size: 20px; }
}
@media (max-width: 340px) {
  .load-comparison { grid-template-columns: minmax(0, 1fr); }
  .prescription-settings .apply-prescription, .prescription-settings .revision-restore { width: 100%; }
}
</style>
