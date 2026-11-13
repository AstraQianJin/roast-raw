<script setup>
import { computed, reactive, ref, watch } from 'vue';

const props = defineProps({
  row: { type: Object, required: true },
  cycleId: { type: String, default: '' },
  log: { type: Object, default: null },
});
const emit = defineEmits(['saved']);
const fields = reactive({ load: '', sets: '', reps: '', rpe: '', note: '' });
const suggested = reactive({ load: false, reps: false });
const dirty = ref(false);
const saving = ref(false);
const errors = ref([]);
const saved = ref(null);
const skipped = computed(() => /^\d+$/.test(fields.sets.trim()) && Number(fields.sets) === 0);
const lastSegment = computed(() => props.row.segments?.at(-1));
const plannedLoad = computed(() => props.row.bucket === 'accessory' ? null : (lastSegment.value?.load ?? props.row.loadKg));
const plannedReps = computed(() => lastSegment.value?.reps ?? props.row.reps);
const finite = value => typeof value === 'number' && Number.isFinite(value);
const count = value => Number.isSafeInteger(value) && value >= 0;
const asText = value => finite(value) ? String(value) : '';

function hydrate(log) {
  fields.load = log ? asText(log.load) : asText(plannedLoad.value);
  fields.sets = log ? asText(log.sets) : '';
  fields.reps = log ? asText(log.reps) : asText(plannedReps.value);
  fields.rpe = log ? asText(log.rpe) : '';
  fields.note = typeof log?.note === 'string' ? log.note : '';
  suggested.load = !log && fields.load !== '';
  suggested.reps = !log && fields.reps !== '';
}
hydrate(props.log);
watch(() => props.log, log => {
  if (!dirty.value && !saving.value) hydrate(log);
}, { deep: true });

function edit(field, event) {
  fields[field] = event.target.value;
  if (field === 'load' || field === 'reps') suggested[field] = false;
  dirty.value = true;
  saved.value = null;
  errors.value = [];
}

function numeric(field, label, integer = false, optional = false) {
  const text = fields[field].trim();
  if (!text && optional) return null;
  const value = Number(text);
  const syntax = integer ? /^\d+$/ : /^(?:\d+(?:\.\d*)?|\.\d+)$/;
  if (!syntax.test(text) || !Number.isFinite(value) || (integer && !count(value))) {
    errors.value.push(`${label}: enter a finite, non-negative ${integer ? 'whole number' : 'number'}.`);
    return null;
  }
  return value;
}

function responseErrors(data, status) {
  const messages = [`Save failed (${status}). Your entries are still here.`];
  const message = typeof data?.error === 'string' ? data.error : data?.detail;
  if (typeof message === 'string') messages.push(message);
  const details = Array.isArray(data?.errors) ? data.errors : (Array.isArray(data?.detail) ? data.detail : []);
  for (const detail of details) {
    if (!detail || typeof detail !== 'object') continue;
    const field = typeof detail.field === 'string' ? detail.field :
      (Array.isArray(detail.loc) ? detail.loc.filter(item => typeof item === 'string' || typeof item === 'number').join('.') : 'Request');
    const expected = typeof detail.expected === 'string' ? detail.expected : detail.msg;
    if (typeof expected === 'string') messages.push(`${field}: ${expected}`);
  }
  return messages;
}

function validSaved(data, key) {
  return data && data.key === key && count(data.sets) && count(data.reps) &&
    (data.load === null || (finite(data.load) && data.load >= 0)) &&
    (data.rpe === null || (finite(data.rpe) && data.rpe >= 5.5 && data.rpe <= 10)) &&
    typeof data.note === 'string' && typeof data.updated_at === 'string' && data.updated_at.length > 0;
}

async function save() {
  if (saving.value) return;
  errors.value = [];
  saved.value = null;
  const sets = numeric('sets', 'Actual working sets', true);
  const reps = skipped.value ? 0 : numeric('reps', 'Actual reps per set', true);
  const load = skipped.value ? null : numeric('load', 'Actual load', false, true);
  const rpe = skipped.value ? null : numeric('rpe', 'Actual RPE', false, true);
  if (sets > 0 && reps === 0) errors.value.push('Actual reps per set: enter a number greater than 0 for completed sets.');
  if (sets > 0 && props.row.bucket !== 'accessory' && load === null) errors.value.push('Actual load: required for main lifts and variations.');
  if (rpe !== null && (rpe < 5.5 || rpe > 10)) errors.value.push('Actual RPE: enter a value from 5.5 to 10, or leave it blank.');
  if (fields.note.length > 2000) errors.value.push('Log notes: use no more than 2000 characters.');
  if (!props.cycleId.trim() || !count(props.row.week) || props.row.week < 1 ||
      !count(props.row.seq) || props.row.seq < 1 || typeof props.row.day !== 'string' || !props.row.day.trim()) {
    errors.value.push('A valid cycle and workout row are required to save.');
  }
  if (errors.value.length) return;

  const payload = {
    cycle_id: props.cycleId,
    week: props.row.week,
    day: props.row.day,
    seq: props.row.seq,
    load,
    sets,
    reps,
    rpe,
    note: fields.note,
  };
  saving.value = true;
  try {
    const response = await fetch('/api/log', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      errors.value = responseErrors(data, response.status);
      return;
    }
    if (!validSaved(data, `${payload.week}|${payload.day}|${payload.seq}`)) {
      errors.value = ['The server returned an unexpected response. Your entries are still here; reload logs before retrying.'];
      return;
    }
    hydrate(data);
    dirty.value = false;
    saved.value = data;
    emit('saved', data);
  } catch {
    errors.value = ['Unable to save. Check your connection and try again. Your entries are still here.'];
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <form class="log-editor" :aria-label="`Log ${row.nameEn}`" :aria-busy="saving" novalidate @submit.prevent="save">
    <p class="editor-heading">Actual working sets</p>
    <p class="editor-help">Exclude warm-ups. Record the load and reps of your last working set.</p>
    <fieldset :disabled="saving" class="log-fields">
      <label class="log-field load-field">
        <span>Actual load (kg)</span>
        <input name="load" type="text" inputmode="decimal" autocomplete="off" :disabled="skipped" :value="fields.load" @input="edit('load', $event)">
        <small v-if="suggested.load && !skipped">Planned suggestion (last working set): {{ plannedLoad }} kg. Confirm or replace with your actual load.</small>
        <small v-else-if="!skipped">{{ row.bucket === 'accessory' ? 'Optional for accessories.' : 'Required when working sets are completed.' }}</small>
      </label>
      <div class="secondary-fields">
        <label class="log-field">
          <span>Actual sets</span>
          <input name="sets" type="text" inputmode="numeric" autocomplete="off" placeholder="Enter sets" required :value="fields.sets" @input="edit('sets', $event)">
        </label>
        <label class="log-field">
          <span>Reps per set</span>
          <input name="reps" type="text" inputmode="numeric" autocomplete="off" :disabled="skipped" :value="fields.reps" @input="edit('reps', $event)">
          <small v-if="suggested.reps && !skipped">Planned suggestion: {{ plannedReps }}. Confirm actual reps.</small>
        </label>
        <label class="log-field">
          <span>Actual RPE</span>
          <input name="rpe" type="text" inputmode="decimal" autocomplete="off" placeholder="Optional" :disabled="skipped" :value="fields.rpe" @input="edit('rpe', $event)">
          <small v-if="!skipped">5.5–10, or blank.</small>
        </label>
      </div>
      <p class="editor-help">{{ skipped ? 'Skipped: saved with 0 reps and no load or RPE.' : 'Enter 0 sets only to explicitly mark this exercise as skipped.' }}</p>
      <label class="log-field">
        <span>Log notes <small>(optional)</small></span>
        <textarea name="note" maxlength="2000" rows="3" :value="fields.note" @input="edit('note', $event)"></textarea>
      </label>
      <button class="save-log" type="submit">{{ saving ? 'Saving working sets…' : 'Save working sets' }}</button>
    </fieldset>
    <div v-if="errors.length" class="log-errors" role="alert">
      <p v-for="(message, index) in errors" :key="index">{{ message }}</p>
    </div>
    <p v-if="saved" class="log-saved" role="status">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" focusable="false"><path d="m5 12 4 4L19 6" /></svg>
      <span>{{ saved.sets === 0 ? 'Skipped exercise saved.' : 'Working sets saved.' }}</span>
    </p>
  </form>
</template>

<style scoped>
.log-editor {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  margin-top: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  color: var(--ink);
  overflow-wrap: anywhere;
}
.editor-heading {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}
.editor-help {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}
.log-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  margin: 14px 0 0;
  padding: 0;
  border: 0;
}
.log-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  font-size: 12px;
}
.log-field small {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}
.log-field input,
.log-field textarea {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  min-height: 44px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--panel);
  color: var(--ink);
  font: 16px var(--sans);
}
.load-field > span {
  font-size: 14px;
  font-weight: 600;
}
.load-field input {
  min-height: 56px;
  font: 600 28px var(--mono);
}
.log-field textarea {
  resize: vertical;
  line-height: 1.5;
}
.log-field input:disabled,
.log-field textarea:disabled {
  color: var(--muted);
  background: var(--panel2);
}
.secondary-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.save-log {
  box-sizing: border-box;
  min-height: 44px;
  min-width: 44px;
  max-width: 100%;
  align-self: flex-start;
  padding: 10px 12px;
  border: 1px solid var(--accent);
  color: var(--accent);
  white-space: normal;
  overflow-wrap: anywhere;
}
.log-editor input:focus-visible,
.log-editor textarea:focus-visible,
.save-log:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.log-errors {
  margin-top: 12px;
  color: var(--accent);
  font-size: 12px;
  line-height: 1.5;
}
.log-errors p {
  margin: 4px 0;
}
.log-saved {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 0 0;
  color: var(--accessory);
  font-size: 12px;
}
.log-saved svg {
  flex: 0 0 20px;
}
</style>
