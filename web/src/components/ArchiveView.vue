<script setup>
import { computed, defineComponent, h, onBeforeUnmount, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import TrendView from './TrendView.vue';
import CycleStrip from './CycleStrip.vue';

const props = defineProps({ activeCycleId: { type: String, required: true } });
const route = useRoute();
const router = useRouter();
const selectedCycleId = computed(() => typeof route.params.cycleId === 'string' ? route.params.cycleId : '');
const cycles = ref([]);
const archiveActiveId = ref('');
const review = ref(null);
const analysis = ref(null);
const performance = ref(null);
const loading = ref(false);
const exporting = ref(false);
const error = ref('');
const errorHeading = ref('');
const exportNotice = ref('');
const deleteToken = ref('');
const deleteConfirm = ref('');
const deleteBusy = ref(false);
const deleteError = ref('');
const selectedWeek = ref(null);
const retryCount = ref(0);
const expandedSections = ref({});
function toggleSection(key, event) { expandedSections.value[key] = event.currentTarget.open; }
let requestCount = 0;
let exportCount = 0;
let exportController;
const objectUrls = new Set();

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const own = (value, key) => object(value) && Object.hasOwn(value, key);
const finite = value => typeof value === 'number' && Number.isFinite(value);
const format = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const number = value => finite(value) ? format.format(value) : '—';
const percent = value => finite(value) ? `${number(value)}%` : '—';
const text = value => value === null || value === undefined || value === '' ? '—'
  : typeof value === 'object' ? JSON.stringify(value) : String(value);
const weekLabel = n => `Week ${text(n)}`;
// Vue Router has already decoded params. Only encode IDs when constructing a link.
const archivePath = id => router.resolve({ path: `/archive/${encodeURIComponent(id)}` }).fullPath;
const apiPath = (path, id, extra = {}) => `${path}?${new URLSearchParams({ cycle_id: id, ...extra })}`;
const activeId = computed(() => archiveActiveId.value || props.activeCycleId);
const historicalCycles = computed(() => cycles.value.filter(cycle =>
  cycle.id !== activeId.value && cycle.id !== props.activeCycleId && cycle.status !== 'active'));
const cycle = computed(() => review.value?.cycle ?? {});
const inProgress = computed(() => !!review.value && cycle.value.status === 'active');
const weeks = computed(() => review.value?.plan?.weeks ?? []);
const currentWeek = computed(() => weeks.value.find(week => week.n === selectedWeek.value));
const weekRows = computed(() => (review.value?.plan?.workouts ?? [])
  .filter(row => row.week === selectedWeek.value));
const logs = computed(() => review.value?.logs ?? []);
const logKey = row => `${row.week}|${row.day}|${row.seq}`;
const rowLogs = row => logs.value.filter(log => log.key === logKey(row));
const attainment = computed(() => review.value?.attainment ?? {});
const completion = computed(() => review.value?.completion ?? null);
const bodyweightDetail = computed(() => object(attainment.value.bodyweight_detail)
  ? attainment.value.bodyweight_detail : null);
const bodyweightFields = computed(() => [
  { key: 'start', label: 'Starting bodyweight', unit: 'kg' },
  { key: 'target', label: 'Target bodyweight', unit: 'kg' },
  { key: 'current', label: 'Recorded bodyweight', unit: 'kg' },
  { key: 'date', label: 'Record date' },
  { key: 'percent', label: 'Target progress', percentage: true },
  { key: 'mode', label: 'Goal mode' },
].filter(field => own(bodyweightDetail.value, field.key)));
const scoreLabels = [
  { key: 'goal', label: 'SBD goal attainment', weight: '40% of composite' },
  { key: 'bodyweight', label: 'Bodyweight progress', weight: '40% of composite' },
  { key: 'completion', label: 'Training completion', weight: '20% of composite' },
  { key: 'composite', label: 'Composite attainment', weight: 'All three components required' },
];
const roleLabels = [
  { key: 'main', label: 'Main lifts', weight: '60%' },
  { key: 'var', label: 'Variations', weight: '25%' },
  { key: 'acc', label: 'Accessories', weight: '15%' },
];
const completionCounts = computed(() => object(completion.value)
  ? Object.fromEntries(Object.entries(completion.value).filter(([key]) => !['main', 'var', 'acc'].includes(key)))
  : null);
const historySections = computed(() => review.value ? [
  { key: 'readiness', title: 'Readiness history', note: 'Recorded inputs and server-supplied evaluations. Legacy fatigue retains its original meaning; it is not Muscle Recovery and is not rescored here.' },
  { key: 'body_metrics', title: 'Body metrics history', note: 'Dated bodyweight, body fat and measurements as recorded; no missing measurement is filled in.' },
  { key: 'prescription_versions', title: 'Prescription version history', note: 'Historical versions are read-only. The complete review export preserves the supplied version plans; there is no restore or apply action here.' },
  { key: 'journals', title: 'Record journals', note: 'Original record changes and timestamps, including superseded entries where supplied.' },
  { key: 'profile_start', title: 'Starting profile' },
  { key: 'profile_end', title: 'Ending profile' },
  { key: 'end_state', title: 'Recorded end state' },
  { key: 'next_outlook', title: 'Next-cycle outlook' },
  { key: 'integrity', title: 'Export integrity', note: 'Server-supplied integrity metadata. Displaying it does not independently verify a digest.' },
] : []);
const planContext = computed(() => review.value
  ? Object.fromEntries(Object.entries(review.value.plan).filter(([key]) => !['weeks', 'workouts'].includes(key)))
  : null);

function fieldLabel(key) {
  if (/fatigue/i.test(key)) return 'Legacy fatigue (not recovery)';
  if (key === 'legacy') return 'Legacy readiness (original fatigue, not recovery)';
  const labels = { main: 'Main lifts', var: 'Variations', acc: 'Accessories', sbdVar: 'SBD variations',
    nonSbdVar: 'Other variations', accessory: 'Accessories', e1rm: 'Estimated 1RM', rpe: 'RPE',
    hrv: 'HRV', rhr: 'Resting heart rate', recovery: 'Muscle Recovery' };
  const readable = key.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replaceAll('_', ' ');
  return labels[key] ?? readable.charAt(0).toUpperCase() + readable.slice(1);
}
// Native text only: flexible review/history payloads stay readable without guessing their structure.
const ReadOnlyFields = defineComponent({
  name: 'ReadOnlyReviewFields',
  props: { value: { default: null } },
  setup(fields) {
    function renderValue(value) {
      if (Array.isArray(value)) {
        return value.length ? h('ol', { class: 'source-list' }, value.map((entry, index) =>
          h('li', { key: index }, [renderValue(entry)]))) : h('p', { class: 'source-empty' }, 'No entries supplied.');
      }
      if (object(value)) {
        const entries = Object.entries(value);
        return entries.length ? h('dl', { class: 'source-fields' }, entries.map(([key, entry]) =>
          h('div', { key }, [h('dt', fieldLabel(key)), h('dd', [renderValue(entry)])])))
          : h('p', { class: 'source-empty' }, 'No fields supplied.');
      }
      return h('span', { class: 'source-value' }, text(value));
    }
    return () => h('div', { class: 'source-reading' }, [renderValue(fields.value)]);
  },
});

function missingScore(key) {
  const suppliedReason = attainment.value?.reasons?.[key];
  if (typeof suppliedReason === 'string' && suppliedReason.trim()) return suppliedReason;
  if (key === 'goal') return 'Required actual SBD test results or goal values are missing. Estimated 1RM does not substitute for a test.';
  if (key === 'bodyweight') return 'A starting weight, target or dated bodyweight reading is missing.';
  if (key === 'completion') return 'At least one required role has no available planned/actual completion basis.';
  const missing = scoreLabels.filter(item => item.key !== 'composite' && !finite(attainment.value[item.key]))
    .map(item => item.label.toLowerCase());
  return missing.length ? `Unavailable: ${missing.join(', ')}. Missing weights are not redistributed.`
    : 'The server has not supplied a composite score. Missing values are not calculated here.';
}
function responseError(payload, fallback) {
  const detail = payload?.detail ?? payload?.message ?? payload?.error;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(entry => typeof entry === 'string' ? entry : entry?.msg ?? entry?.message)
      .filter(message => typeof message === 'string');
    if (messages.length) return messages.join('; ');
  }
  return fallback;
}
async function checkResponse(response) {
  if (response.ok) return;
  let payload;
  try { payload = await response.json(); } catch { /* HTTP status remains the fallback. */ }
  throw new Error(responseError(payload, response.status === 404
    ? 'Cycle not found. It may not exist at this address.' : `Request failed (${response.status}). Please retry.`));
}
async function getJson(path, signal) {
  const response = await fetch(path, { method: 'GET', cache: 'no-store', signal });
  await checkResponse(response);
  try { return await response.json(); }
  catch { throw new Error('The server returned an unreadable response. Please retry.'); }
}
function validateReview(payload, id) {
  // This checks identity and rendering boundaries, not a second copy of the exchange schema.
  const required = ['schema', 'exported_at', 'plan_id', 'profile_start', 'profile_end', 'plan', 'logs',
    'readiness', 'planned_vs_actual', 'completion', 'attainment', 'e1rm', 'end_state', 'next_outlook',
    'cycle', 'as_of', 'app_version', 'body_metrics', 'prescription_versions', 'journals', 'integrity'];
  if (!object(payload) || required.some(key => !own(payload, key)) || payload.schema !== 'RPL-Review-v1'
    || payload.plan_id !== id || !object(payload.cycle) || payload.cycle.id !== id
    || !['active', 'archived', 'completed'].includes(payload.cycle.status)
    || !object(payload.plan?.meta) || payload.plan.meta.planId !== id
    || ['weeks', 'workouts', 'blocks', 'days'].some(key => !Array.isArray(payload.plan[key]))
    || payload.plan.weeks.some(week => !object(week) || !Number.isInteger(week.n) || week.n < 1)
    || payload.plan.workouts.some(row => !object(row) || !Array.isArray(row.segments))
    || !Array.isArray(payload.logs) || payload.logs.some(log => !object(log) || typeof log.key !== 'string')
    || !Array.isArray(payload.body_metrics) || !Array.isArray(payload.prescription_versions)) {
    throw new Error('The server returned an incomplete review or a different cycle. No summary or export was retained.');
  }
}
function validateTrends(capacity, recorded, id) {
  if (!object(capacity) || !Array.isArray(capacity.perWeek)
    || !object(recorded) || !Array.isArray(recorded.movements)
    || [capacity, recorded].some(payload =>
      (own(payload, 'cycle_id') && payload.cycle_id !== id) || (own(payload, 'plan_id') && payload.plan_id !== id))) {
    throw new Error('The server returned invalid or mismatched cycle trends. Please retry the review.');
  }
}
function clearReview() {
  review.value = null;
  analysis.value = null;
  performance.value = null;
  selectedWeek.value = null;
  expandedSections.value = {};
  deleteToken.value = '';
  deleteConfirm.value = '';
  deleteError.value = '';
  deleteBusy.value = false;
}
function retry() { retryCount.value += 1; }

watch(() => [selectedCycleId.value, props.activeCycleId, retryCount.value], async (_, __, onCleanup) => {
  const sequence = ++requestCount;
  const id = selectedCycleId.value;
  const controller = new AbortController();
  exportCount += 1;
  exportController?.abort();
  onCleanup(() => {
    requestCount += 1;
    exportCount += 1;
    controller.abort();
    exportController?.abort();
  });
  clearReview();
  cycles.value = [];
  archiveActiveId.value = '';
  error.value = '';
  errorHeading.value = '';
  exportNotice.value = '';
  exporting.value = false;
  loading.value = true;
  try {
    if (id) {
      const [payload, capacity, recorded] = await Promise.all([
        getJson(apiPath('/api/review', id), controller.signal),
        getJson(apiPath('/api/analysis', id, { mode: 'log' }), controller.signal),
        getJson(apiPath('/api/performance', id), controller.signal),
      ]);
      if (sequence !== requestCount) return;
      validateReview(payload, id);
      validateTrends(capacity, recorded, id);
      review.value = payload;
      analysis.value = capacity;
      performance.value = recorded;
      selectedWeek.value = payload.plan.weeks[0]?.n ?? null;
    } else {
      const payload = await getJson('/api/archive', controller.signal);
      if (sequence !== requestCount) return;
      if (!object(payload) || !Array.isArray(payload.cycles) || !own(payload, 'active_cycle_id')
        || (payload.active_cycle_id !== null && typeof payload.active_cycle_id !== 'string')
        || payload.cycles.some(entry => !object(entry) || typeof entry.id !== 'string' || !entry.id)) {
        throw new Error('The server returned an invalid archive list. Please retry.');
      }
      cycles.value = payload.cycles;
      archiveActiveId.value = payload.active_cycle_id ?? '';
    }
  } catch (failure) {
    if (sequence !== requestCount) return;
    controller.abort();
    clearReview();
    cycles.value = [];
    errorHeading.value = id ? 'Review could not be loaded' : 'Archive could not be loaded';
    error.value = failure.message || 'The request failed. Please retry.';
  } finally {
    if (sequence === requestCount) loading.value = false;
  }
}, { immediate: true, flush: 'sync' });

async function downloadReview() {
  if (!review.value || loading.value || exporting.value) return;
  const id = selectedCycleId.value;
  const sequence = requestCount;
  const attempt = ++exportCount;
  const controller = new AbortController();
  exportController = controller;
  exporting.value = true;
  exportNotice.value = '';
  const current = () => attempt === exportCount && sequence === requestCount && id === selectedCycleId.value;
  try {
    const response = await fetch(apiPath('/api/review/export', id), {
      method: 'GET', cache: 'no-store', signal: controller.signal,
    });
    await checkResponse(response);
    const blob = await response.blob();
    if (!current()) return;
    let payload;
    try { payload = JSON.parse(await blob.text()); }
    catch { throw new Error('The server returned an unreadable review export. No file was downloaded.'); }
    if (!current()) return;
    validateReview(payload, id);
    // Download the complete server response, not a reconstructed or cached frontend summary.
    const url = URL.createObjectURL(blob);
    objectUrls.add(url);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'RoastRaw-review.json';
    try {
      document.body.appendChild(anchor);
      anchor.click();
    } finally {
      anchor.remove();
      // Let the browser consume the URL before releasing it.
      setTimeout(() => { URL.revokeObjectURL(url); objectUrls.delete(url); }, 0);
    }
    exportNotice.value = 'Download requested: RoastRaw-review.json. This does not change the cycle.';
  } catch (failure) {
    if (!current()) return;
    clearReview();
    errorHeading.value = 'Review export could not be downloaded';
    error.value = `${failure.message || 'The request failed.'} Retry to reload the review before exporting again.`;
  } finally {
    if (current()) exporting.value = false;
  }
}
async function prepareDeletion() {
  if (!review.value || deleteBusy.value || inProgress.value) return;
  const id = selectedCycleId.value;
  deleteBusy.value = true;
  deleteError.value = '';
  try {
    const response = await fetch('/api/archive/delete/prepare', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: id }), cache: 'no-store',
    });
    await checkResponse(response);
    const blob = await response.blob();
    let payload;
    try { payload = JSON.parse(await blob.text()); }
    catch { throw new Error('The deletion export was unreadable. Nothing was deleted.'); }
    if (payload?.cycle_id !== id || typeof payload?.token !== 'string' || !payload.token) {
      throw new Error('The deletion export did not match this cycle. Nothing was deleted.');
    }
    const url = URL.createObjectURL(blob);
    objectUrls.add(url);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `RoastRaw-delete-export-${id}.json`;
    try {
      document.body.appendChild(anchor);
      anchor.click();
    } finally {
      anchor.remove();
      setTimeout(() => { URL.revokeObjectURL(url); objectUrls.delete(url); }, 0);
    }
    deleteToken.value = payload.token;
    deleteConfirm.value = '';
  } catch (failure) {
    deleteError.value = failure.message || 'The deletion export failed. Nothing was deleted.';
  } finally {
    deleteBusy.value = false;
  }
}
async function confirmDeletion() {
  const id = selectedCycleId.value;
  if (!deleteToken.value || deleteConfirm.value !== id || deleteBusy.value || inProgress.value) return;
  deleteBusy.value = true;
  deleteError.value = '';
  try {
    const response = await fetch(`/api/archive/${encodeURIComponent(id)}`, {
      method: 'DELETE', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: deleteToken.value, confirm: deleteConfirm.value }), cache: 'no-store',
    });
    await checkResponse(response);
    deleteToken.value = '';
    deleteConfirm.value = '';
    router.push('/archive');
  } catch (failure) {
    deleteError.value = failure.message || 'The cycle was not deleted.';
  } finally {
    deleteBusy.value = false;
  }
}
onBeforeUnmount(() => {
  requestCount += 1;
  exportCount += 1;
  exportController?.abort();
  for (const url of objectUrls) URL.revokeObjectURL(url);
  objectUrls.clear();
});
</script>

<template>
  <section class="archive-view" data-testid="archive-view" :aria-busy="loading">
    <header v-if="!selectedCycleId" class="archive-heading">
      <p class="eyebrow">THE TRAINING RECORD</p>
      <h1>Previous cycles.<br><em>Nothing overwritten.</em></h1>
      <p class="reading-note">Historical plans and their execution stay together. Reviews are read-only; exporting is not an archive command.</p>
    </header>
    <nav v-else class="review-navigation" aria-label="Review navigation">
      <RouterLink to="/archive" class="text-link">Back to archive</RouterLink>
    </nav>

    <p v-if="loading" class="loading-note" role="status" data-testid="archive-loading">
      {{ selectedCycleId ? 'Loading this cycle’s review and recorded trends…' : 'Loading the archive…' }}
    </p>
    <section v-else-if="error" class="review-error" role="alert" data-testid="review-error">
      <h2>{{ errorHeading }}</h2>
      <p>{{ error }}</p>
      <p v-if="selectedCycleId" class="reading-note">Requested cycle <code>{{ selectedCycleId }}</code></p>
      <div class="actions">
        <button type="button" data-testid="review-retry" @click="retry">Retry</button>
        <RouterLink to="/archive" class="text-link">Open archive</RouterLink>
      </div>
    </section>

    <template v-else-if="!selectedCycleId">
      <section class="active-review" data-testid="archive-active-review" aria-label="Active cycle review">
        <div class="section-kicker"><span>ACTIVE REVIEW</span><span>IN PROGRESS</span></div>
        <h2>A review, not an ending.</h2>
        <p class="reading-note">Exporting does not end or archive this cycle.</p>
        <template v-if="activeId">
          <p class="cycle-id">Active cycle <code>{{ activeId }}</code></p>
          <RouterLink :to="archivePath(activeId)" class="review-link" data-testid="archive-active-link">Review active cycle</RouterLink>
        </template>
        <p v-else class="reading-note">No active cycle is available.</p>
      </section>
      <section class="archive-list-section" aria-label="Historical cycles">
        <div class="section-kicker"><span>HISTORICAL CYCLES</span><span>{{ historicalCycles.length }} RECORDS</span></div>
        <ol class="archive-list" data-testid="archive-list">
          <li v-for="entry in historicalCycles" :key="entry.id" class="archive-entry">
            <header class="entry-heading">
              <h2>{{ entry.name || entry.id }}</h2>
              <span class="status-label">{{ text(entry.status).toUpperCase() }} · READ-ONLY</span>
            </header>
            <p class="cycle-id"><code>{{ entry.id }}</code></p>
            <p class="reading-note">{{ text(entry.start_date) }} — {{ text(entry.end_date) }} · {{ text(entry.weeks) }} weeks</p>
            <dl class="archive-summary">
              <div v-for="role in roleLabels" :key="role.key"><dt>{{ role.label }} completion</dt><dd>{{ percent(entry.completion?.[role.key]) }}</dd></div>
              <div><dt>Composite attainment</dt><dd>{{ percent(entry.attainment?.composite) }}</dd></div>
            </dl>
            <p class="reading-note">Unavailable values remain —; missing components are not reweighted.</p>
            <details v-if="entry.e1rm?.main !== null && entry.e1rm?.main !== undefined" class="source-details">
              <summary>Main-lift recorded summary</summary>
              <p class="reading-note">Server-reported estimated 1RM context, not actual-test goal attainment.</p>
              <ReadOnlyFields :value="entry.e1rm.main" />
            </details>
            <RouterLink :to="archivePath(entry.id)" class="review-link" :data-testid="`archive-cycle-${entry.id}`">Open read-only review</RouterLink>
          </li>
        </ol>
        <div v-if="!historicalCycles.length" class="empty-note" data-testid="archive-empty">
          <h2>No historical cycles yet.</h2>
          <p class="reading-note">Your active cycle stays active. Its review can be exported without ending it.</p>
        </div>
      </section>
    </template>

    <article v-else-if="review" :key="selectedCycleId" class="review-body" data-testid="review-view">
      <header class="review-heading">
        <div class="section-kicker"><span>CYCLE REVIEW</span><span class="status-label" data-testid="review-status">{{ inProgress ? 'IN PROGRESS' : 'READ-ONLY' }}</span></div>
        <h1>{{ cycle.name || review.plan.meta.name || selectedCycleId }}</h1>
        <p class="cycle-id">Cycle <code>{{ selectedCycleId }}</code></p>
        <p class="reading-note">{{ text(cycle.start_date ?? review.plan.meta.startDate) }} — {{ text(cycle.end_date ?? review.plan.meta.endDate) }} · {{ text(review.plan.meta.weeks) }} weeks · {{ text(cycle.status) }}</p>
        <p class="reading-note">As of {{ text(review.as_of) }} · App {{ text(review.app_version) }} · {{ review.schema }}</p>
        <p class="cycle-boundary" data-testid="review-boundary">{{ inProgress ? 'Exporting does not end or archive this cycle.' : 'This historical cycle is read-only. Its plan and records cannot be changed here.' }}</p>
        <div class="actions">
          <button type="button" class="export-button" data-testid="review-export" :disabled="exporting" @click="downloadReview">{{ exporting ? 'Downloading review…' : 'Download complete review JSON' }}</button>
        </div>
        <p v-if="exporting" role="status" class="reading-note">Requesting a fresh, complete server export…</p>
        <p v-else-if="exportNotice" role="status" class="reading-note" data-testid="review-export-status">{{ exportNotice }}</p>
        <p class="reading-note">The export includes the complete plan, logs, readiness, body metrics, prescription versions and supplied journals. Nothing is stored offline.</p>
      </header>

      <section class="report-section" aria-label="Review attainment">
        <div class="section-kicker"><span>ATTAINMENT</span><span>API VALUES · NO FRONTEND SCORING</span></div>
        <h2>Three components.<br><em>One explicit basis.</em></h2>
        <p class="reading-note">Composite weights: goal 40% / bodyweight 40% / completion 20% (40/40/20). Completion weights: main 60% / variations 25% / accessories 15% (60/25/15). Values may exceed 100%; they are not capped here. Missing weights are never redistributed.</p>
        <dl class="score-grid">
          <div v-for="score in scoreLabels" :key="score.key" class="score-reading" :class="{ composite: score.key === 'composite' }" :data-testid="`review-score-${score.key}`">
            <dt>{{ score.label }}</dt>
            <dd class="score-value">{{ percent(attainment[score.key]) }}</dd>
            <dd class="reading-note">{{ score.weight }}</dd>
            <dd v-if="!finite(attainment[score.key])" class="reading-note">{{ missingScore(score.key) }}</dd>
          </div>
        </dl>
        <p class="reading-note">Goal attainment uses actual SBD tests with equal lift weights. Variation PRs and estimated 1RM observations are context, not substitute goal scores.</p>
        <dl v-if="bodyweightFields.length" class="bodyweight-readings" data-testid="review-bodyweight-detail">
          <div v-for="field in bodyweightFields" :key="field.key">
            <dt>{{ field.label }}</dt>
            <dd>{{ field.percentage ? percent(bodyweightDetail[field.key]) : field.unit ? number(bodyweightDetail[field.key]) : text(bodyweightDetail[field.key]) }}<small v-if="field.unit && finite(bodyweightDetail[field.key])"> {{ field.unit }}</small></dd>
          </div>
        </dl>
        <details class="source-details">
          <summary>Supplied score basis and weights</summary>
          <ReadOnlyFields :value="attainment" />
        </details>
      </section>

      <section class="report-section" data-testid="review-completion" aria-label="Actual training completion">
        <div class="section-kicker"><span>COMPLETION</span><span>RAW WORKING SETS</span></div>
        <h2>Planned. Actually recorded.</h2>
        <p class="reading-note">Completion uses actual working sets, not SBD equivalent capacity or muscle coefficients. Unlogged work is not assumed completed; an explicit zero remains zero.</p>
        <dl class="role-readings">
          <div v-for="role in roleLabels" :key="role.key" :data-testid="`review-completion-${role.key}`"><dt>{{ role.label }} · {{ role.weight }} weight</dt><dd>{{ percent(completion?.[role.key]) }}</dd><dd v-if="!finite(completion?.[role.key])" class="reading-note">No available planned/actual basis for this role.</dd></div>
        </dl>
        <div class="counts-reading" data-testid="review-counts">
          <h3>Supplied planned / actual counts</h3>
          <ReadOnlyFields v-if="completionCounts && Object.keys(completionCounts).length" :value="completionCounts" />
          <p v-else class="reading-note">Separate raw counts were not supplied in completion.</p>
          <details class="source-details" data-testid="review-comparison" @toggle="toggleSection('comparison', $event)">
            <summary>Weekly and per-row planned / actual comparison</summary>
            <ReadOnlyFields v-if="expandedSections.comparison && review.planned_vs_actual !== null" :value="review.planned_vs_actual" />
            <p v-else-if="review.planned_vs_actual === null" class="reading-note">No additional planned-versus-actual detail was supplied.</p>
          </details>
        </div>
      </section>

      <TrendView :key="selectedCycleId" :analysis="analysis" :performance="performance" />

      <details class="report-details" data-testid="archive-plan">
        <summary>Historical plan and actual logs · read-only</summary>
        <p class="reading-note">Every workout row for the selected week is shown as text. No log editor or prescription control is mounted, including for an active review.</p>
        <label class="week-control">
          <span>Plan week</span>
          <select v-model="selectedWeek" data-testid="archive-week" :disabled="!weeks.length">
            <option v-if="!weeks.length" :value="null">No weeks supplied</option>
            <option v-for="week in weeks" :key="week.n" :value="week.n">{{ weekLabel(week.n) }} · {{ text(week.blockName) }} · {{ text(week.kind) }}</option>
          </select>
        </label>
        <CycleStrip v-if="Array.isArray(review.plan.blocks) && review.plan.blocks.length && weeks.length" :weeks="weeks" :blocks="review.plan.blocks" :current="selectedWeek || 0" />
        <div v-if="currentWeek" class="week-context"><h3>{{ weekLabel(currentWeek.n) }}</h3><p class="reading-note">{{ text(currentWeek.dateStart) }} — {{ text(currentWeek.dateEnd) }} · {{ text(currentWeek.blockName) }} · {{ text(currentWeek.kind) }}</p></div>
        <ol class="workout-list" data-testid="archive-rows">
          <li v-for="row in weekRows" :key="logKey(row)" class="workout-row">
            <header><h3>{{ row.nameEn || row.movementId }}</h3><p class="reading-note">{{ text(row.date) }} · Day {{ text(row.day) }} · Row {{ text(row.seq) }} · {{ text(row.role) }}</p></header>
            <p class="cycle-id">Movement <code>{{ text(row.movementId) }}</code> · Key <code>{{ logKey(row) }}</code></p>
            <p class="reading-note">Planned target RPE {{ number(row.targetRpe) }}<template v-if="row.systemLoad"> · Load is total system weight, not external adjustment.</template></p>
            <ul class="segment-list" aria-label="Planned prescription segments">
              <li v-for="(segment, index) in row.segments" :key="index"><span>{{ segment.label || segment.kind }}</span><strong>{{ text(segment.sets) }} sets × {{ text(segment.reps) }} {{ segment.unit || 'reps' }}</strong><span>Planned load {{ number(segment.load) }}<template v-if="finite(segment.load)"> kg</template></span><span v-if="finite(segment.pct)">{{ number(segment.pct) }}% reference 1RM</span><span v-if="segment.amrap">AMRAP prescribed</span><span v-if="segment.text">{{ segment.text }}</span></li>
            </ul>
            <p v-if="row.rxEn" class="reading-note">Prescription: {{ row.rxEn }}</p>
            <p v-if="row.notes" class="preserved-note">Plan note: {{ row.notes }}</p>
            <div class="row-actual" aria-label="Actual row logs">
              <h4>Actual record</h4>
              <p v-if="!rowLogs(row).length" class="reading-note">No log recorded. Planned work is not substituted.</p>
              <div v-for="(log, index) in rowLogs(row)" :key="index" class="actual-log">
                <p>Load {{ number(log.load) }}<template v-if="finite(log.load)"> kg</template> · {{ number(log.sets) }} sets × {{ number(log.reps) }} reps · RPE {{ number(log.rpe) }}</p>
                <p v-if="log.sets === 0" class="reading-note">Explicit zero working sets.</p>
                <p class="preserved-note">Note: {{ text(log.note) }}</p>
                <p class="reading-note">Updated {{ text(log.updated_at) }} · Key <code>{{ log.key }}</code></p>
              </div>
            </div>
          </li>
        </ol>
        <p v-if="!weekRows.length" class="empty-note">No workout rows supplied for this week.</p>
        <details v-if="currentWeek" class="source-details"><summary>Complete selected-week metadata</summary><ReadOnlyFields :value="currentWeek" /></details>
        <details class="source-details" @toggle="toggleSection('context', $event)"><summary>Plan context, blocks and supplementary prescriptions</summary><ReadOnlyFields v-if="expandedSections.context" :value="planContext" /></details>
      </details>

      <details class="report-details" data-testid="review-logs">
        <summary>Complete recorded logs · {{ logs.length }} entries</summary>
        <p class="reading-note">Exact identities, keys, loads, working sets, reps, RPE, notes and update timestamps as supplied. Records are not merged across movement IDs.</p>
        <ol class="log-list">
          <li v-for="(log, index) in logs" :key="`${log.key}-${index}`" class="log-entry"><h3>Record {{ index + 1 }}</h3><ReadOnlyFields :value="log" /></li>
        </ol>
        <p v-if="!logs.length" class="empty-note">No actual logs recorded for this cycle.</p>
      </details>
      <details v-for="section in historySections" :key="section.key" class="report-details" :data-testid="`review-${section.key.replaceAll('_', '-')}`" @toggle="toggleSection(section.key, $event)">
        <summary>{{ section.title }}</summary>
        <p v-if="section.note" class="reading-note">{{ section.note }}</p>
        <ReadOnlyFields v-if="expandedSections[section.key]" :value="review[section.key]" />
      </details>
      <section v-if="!inProgress" class="report-section deletion-section" data-testid="review-deletion" aria-label="Delete this cycle">
        <div class="section-kicker"><span>DANGER ZONE</span><span>PERMANENT</span></div>
        <h2>Delete this cycle.</h2>
        <p class="reading-note">Deletion removes this plan, its logs, readiness, body metrics and journals from the server. Step 1 downloads a complete forced export — keep it, because it becomes your only remaining copy. This cannot be undone here.</p>
        <div class="actions">
          <button type="button" data-testid="delete-prepare" :disabled="deleteBusy" @click="prepareDeletion">{{ deleteToken ? 'Download a fresh forced export' : 'Step 1 · Download forced export' }}</button>
        </div>
        <template v-if="deleteToken">
          <label class="week-control delete-confirm-label">
            <span>Step 2 · Type the cycle ID to confirm: <code>{{ selectedCycleId }}</code></span>
            <input type="text" v-model="deleteConfirm" data-testid="delete-confirm" autocomplete="off" spellcheck="false" :placeholder="selectedCycleId">
          </label>
          <div class="actions">
            <button type="button" class="delete-final" data-testid="delete-final" :disabled="deleteBusy || deleteConfirm !== selectedCycleId" @click="confirmDeletion">{{ deleteBusy ? 'Deleting…' : 'Permanently delete this cycle' }}</button>
          </div>
        </template>
        <p v-if="deleteError" class="delete-error" role="alert" data-testid="delete-error">{{ deleteError }}</p>
      </section>
      <p class="reading-note report-footnote">Export generated {{ text(review.exported_at) }}. {{ inProgress ? 'This active review is a reading surface; the active cycle cannot be deleted here.' : 'Historical records stay read-only until you complete the forced-export deletion above.' }}</p>
    </article>
  </section>
</template>

<style scoped>
.archive-view { min-width: 0; max-width: 100%; overflow-wrap: anywhere; }
.archive-heading h1 em { color: var(--muted); font-weight: 400; }
.reading-note { margin-top: 10px; color: var(--muted); font: 12px/1.7 var(--sans); }
.section-kicker { flex-wrap: wrap; color: var(--accent); }
.archive-heading > .reading-note { max-width: 65ch; }
.cycle-id { margin-top: 10px; color: var(--muted); font: 11px/1.7 var(--mono); }
code { color: var(--ink); font-family: var(--mono); white-space: normal; overflow-wrap: anywhere; }
.loading-note { min-height: 160px; padding: 30px 0; color: var(--muted); font-size: 13px; }
.review-navigation { margin-bottom: 16px; }
.text-link, .review-link { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; max-width: 100%; padding: 10px 12px; font-size: 12px; white-space: normal; overflow-wrap: anywhere; }
.text-link { padding-left: 0; padding-right: 8px; text-decoration: underline; text-underline-offset: 4px; }
.review-link { margin-top: 14px; border: 1px solid var(--line); background: var(--panel); }
.actions { display: flex; flex-wrap: wrap; gap: 10px 14px; margin-top: 16px; }
.actions button { min-height: 44px; min-width: 44px; max-width: 100%; padding: 10px 12px; white-space: normal; overflow-wrap: anywhere; text-align: left; font-size: 12px; }
.export-button { border-color: var(--accent); background: var(--accent-soft); }
.review-error { margin: 24px 0; padding: 20px 16px; border: 1px solid var(--accent); background: var(--panel); }
.review-error h2 { font-size: 28px; }
.review-error > p { margin-top: 12px; }
.active-review { margin-top: 28px; padding: 20px 16px; border: 1px solid var(--accent); background: var(--panel); }
.active-review h2 { font-size: clamp(27px, 5vw, 34px); }
.archive-list-section { margin-top: 32px; }
.archive-list, .workout-list, .log-list { list-style: none; padding: 0; margin: 0; }
.archive-entry { min-width: 0; padding: 22px 0; border-top: 1px solid var(--line); }
.entry-heading { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 12px; }
.entry-heading h2 { font-size: 29px; }
.status-label { color: var(--muted); font: 10px/1.6 var(--mono); letter-spacing: .05em; }
.archive-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 16px 0 0; }
.archive-summary > div, .score-grid > div, .role-readings > div, .bodyweight-readings > div { min-width: 0; }
.archive-summary dt, .score-grid dt, .role-readings dt, .bodyweight-readings dt { color: var(--muted); font: 11px/1.6 var(--sans); }
.archive-summary dd { margin: 4px 0 0; font: 600 22px/1.4 var(--mono); }
.empty-note { padding: 22px 0; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
.empty-note h2 { color: var(--ink); font-size: 28px; }
.review-heading h1 { font-size: clamp(36px, 7vw, 56px); }
.cycle-boundary { margin-top: 18px; padding: 12px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); color: var(--ink); font-size: 13px; }
.report-section { min-width: 0; margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--accent); }
.report-section h2 { font-size: clamp(28px, 5vw, 36px); }
.score-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0; margin: 20px 0 0; border: 1px solid var(--line); background: var(--panel); }
.score-reading { padding: 16px 12px; }
.score-reading:nth-child(even) { border-left: 1px solid var(--line); }
.score-reading:nth-child(n+3) { border-top: 1px solid var(--line); }
.score-reading.composite { background: var(--panel2); }
.score-reading dd { margin-left: 0; }
.score-value { margin: 8px 0 0; font: 600 clamp(26px, 5vw, 40px)/1.2 var(--mono); letter-spacing: -.05em; }
.bodyweight-readings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin: 18px 0 0; padding: 16px 0; border-top: 1px solid var(--line); }
.bodyweight-readings dd { margin: 4px 0 0; font: 14px/1.7 var(--mono); }
.bodyweight-readings small { color: var(--muted); font-size: 11px; }
.role-readings { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 20px 0; }
.role-readings dd { margin: 6px 0 0; font: 600 23px/1.4 var(--mono); }
.role-readings dd.reading-note { font: 11px/1.7 var(--sans); }
.counts-reading { min-width: 0; padding-top: 16px; border-top: 1px solid var(--line); }
.counts-reading h3 { font-size: 24px; }
.report-details, .source-details { min-width: 0; border-top: 1px solid var(--line); }
.report-details { margin-top: 22px; padding-bottom: 6px; }
.source-details { margin-top: 16px; }
summary { min-height: 44px; min-width: 44px; padding: 12px 4px; cursor: pointer; font: 12px/1.6 var(--sans); color: var(--ink); }
summary:hover { background: var(--panel2); }
summary:focus-visible, .week-control select:focus-visible, .delete-confirm-label input:focus-visible, .actions button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.week-control { display: block; min-width: 0; margin-top: 18px; color: var(--muted); font-size: 12px; }
.week-control select { display: block; min-width: 0; width: 100%; max-width: 100%; min-height: 44px; margin-top: 6px; padding: 10px 8px; color: var(--ink); background: var(--panel); border: 1px solid var(--line); border-radius: 2px; font: 12px var(--sans); }
.week-control select:disabled { opacity: 1; background: var(--panel2); color: var(--muted); }
.delete-confirm-label input { display: block; min-width: 0; width: 100%; max-width: 100%; min-height: 44px; margin-top: 6px; padding: 10px 8px; color: var(--ink); background: var(--panel); border: 1px solid var(--line); border-radius: 2px; font: 12px var(--mono); }
.delete-final { border-color: var(--accent); background: var(--accent-soft); }
.delete-final:disabled { opacity: .6; }
.delete-error { margin-top: 12px; padding: 10px 12px; border: 1px solid var(--accent); background: var(--accent-soft); font-size: 13px; }
.week-context { padding: 20px 0 14px; }
.workout-row { padding: 18px 0; border-top: 1px solid var(--line); }
.workout-row h3, .log-entry h3 { font-size: 24px; }
.segment-list { list-style: none; padding: 0; margin: 14px 0 0; }
.segment-list li { display: flex; flex-wrap: wrap; gap: 6px 14px; padding: 10px 0; border-top: 1px solid var(--line-soft); font: 12px/1.7 var(--mono); }
.segment-list li > span:first-child { flex-basis: 100%; color: var(--muted); font: 11px/1.6 var(--sans); }
.preserved-note { white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 8px; font: 12px/1.7 var(--sans); }
.row-actual { margin-top: 14px; padding: 12px; background: var(--panel2); border: 1px solid var(--line); }
h4 { margin: 0; color: var(--muted); font: 600 10px/1.6 var(--sans); letter-spacing: .08em; text-transform: uppercase; }
.actual-log { margin-top: 10px; font: 12px/1.7 var(--mono); }
.log-entry { padding: 16px 0; border-bottom: 1px solid var(--line-soft); }
.report-footnote { margin-top: 24px; padding-top: 14px; border-top: 1px solid var(--line); }
/* Child render functions use these scoped deep rules; all payloads remain native text. */
.archive-view :deep(.source-reading) { min-width: 0; margin-top: 12px; font: 12px/1.7 var(--sans); }
.archive-view :deep(.source-fields) { min-width: 0; margin: 0; }
.archive-view :deep(.source-fields > div) { min-width: 0; padding: 9px 0; border-top: 1px solid var(--line-soft); }
.archive-view :deep(.source-fields dt) { color: var(--muted); font: 11px/1.7 var(--sans); }
.archive-view :deep(.source-fields dd) { min-width: 0; margin: 3px 0 0; }
.archive-view :deep(.source-fields dd > .source-fields), .archive-view :deep(.source-fields dd > .source-list) { padding-left: 12px; border-left: 1px solid var(--line); }
.archive-view :deep(.source-list) { min-width: 0; padding-left: 24px; margin: 0; }
.archive-view :deep(.source-list > li) { min-width: 0; padding: 8px 0; }
.archive-view :deep(.source-value) { font-family: var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; }
.archive-view :deep(.source-empty) { color: var(--muted); font: 12px/1.7 var(--sans); }
@media (max-width: 390px) {
  .active-review, .review-error { padding: 16px 12px; }
  .score-reading { padding: 14px 10px; }
  .role-readings { gap: 8px; }
  .role-readings dd { font-size: 20px; }
  .archive-summary { gap: 12px 8px; }
  .archive-view :deep(.source-fields dd > .source-fields), .archive-view :deep(.source-fields dd > .source-list) { padding-left: 6px; }
}
</style>
