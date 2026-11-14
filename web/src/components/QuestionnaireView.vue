<script setup>
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

const prefix = `questionnaire-${getCurrentInstance().uid}`;
const SCHEMA_VERSION = 'RR-Questionnaire-v1';

const VARIATIONS = [
  { id: 'S.Main|low-bar squat', fallback: 'Low-bar squat' },
  { id: 'B.Vari.Start|wide-grip bench', fallback: 'Wide-grip bench' },
  { id: 'D.Main|sumo deadlift', fallback: 'Sumo deadlift' },
  { id: 'D.Vari.Power|power clean', fallback: 'Power clean' },
  { id: 'B.Delts|ohp', fallback: 'Overhead press' },
  { id: 'D.Lats|pull-up', fallback: 'Pull-up' },
  { id: 'B.Triceps|dip', fallback: 'Dip' },
  { id: 'SBD.UpperBack|bent-over barbell row', fallback: 'Bent-over barbell row' },
];
const STICKING = {
  squat: ['bottom', 'midrange', 'lockout', 'forward-lean', 'knee-valgus', 'slow-ascent'],
  bench: ['chest', 'midrange', 'lockout', 'shoulder-discomfort', 'elbow-discomfort', 'wrist-discomfort'],
  deadlift: ['off-floor', 'below-knee', 'lockout', 'grip', 'back', 'hips'],
};
const WEAK_MUSCLES = ['chest', 'shoulders', 'back', 'legs', 'arms', 'core', 'calves'];
const TEST_GROUPS = ['sbd', 'primary-variations', 'secondary-variations', 'five-km'];
const SBD = ['squat', 'bench', 'deadlift'];
const SEX = ['male', 'female', 'other'];
const EQUIPMENT = ['classic', 'equipped'];
const ONE_RM = ['measured', 'estimated'];
const WEIGHT_DIR = ['cut', 'maintain', 'bulk'];
const EFFORT = ['all-in', 'low-stress', 'moderate', 'high-stress'];
const RISK = ['aggressive', 'steady', 'conservative'];
const STEP_NAMES = ['', 'Goal', 'Schedule', 'Personal', 'Level', 'Limits', 'Recovery', 'Outlook'];

// Scalar fields kept as raw strings so an empty input maps to null (never 0).
const SCALAR_PATHS = [
  'goal.type',
  'schedule.startDate', 'schedule.competitionDate', 'schedule.trainingDaysPerWeek', 'schedule.sessionMinutes',
  'personal.age', 'personal.sex', 'personal.heightCm', 'personal.bodyweightKg', 'personal.trainingYears',
  'personal.equipment', 'personal.activityLevel',
  'level.sbd1rm.squat', 'level.sbd1rm.bench', 'level.sbd1rm.deadlift', 'level.oneRmSource', 'level.recentPrs',
  'level.fiveKm.timeSeconds', 'level.fiveKm.date', 'level.fiveKm.conditions',
  'limits.technique', 'limits.injuries', 'limits.surgeries', 'limits.jointPain', 'limits.mobility',
  'recovery.sleepHours', 'recovery.sleepQuality', 'recovery.stressLevel', 'recovery.bodyFatPercent', 'recovery.otherSports',
  'outlook.targetBodyweightKg', 'outlook.weightDirection', 'outlook.targets.squat', 'outlook.targets.bench',
  'outlook.targets.deadlift', 'outlook.targets.total', 'outlook.fiveKmTargetSeconds', 'outlook.consistencyGoal',
  'outlook.effortLevel', 'outlook.riskPreference', 'outlook.competitionName', 'outlook.weightClass', 'outlook.targetTotalKg',
  'notes',
];
const NUMERIC = new Set([
  'schedule.trainingDaysPerWeek', 'schedule.sessionMinutes',
  'personal.age', 'personal.heightCm', 'personal.bodyweightKg', 'personal.trainingYears',
  'level.sbd1rm.squat', 'level.sbd1rm.bench', 'level.sbd1rm.deadlift', 'level.fiveKm.timeSeconds',
  'recovery.sleepHours', 'recovery.sleepQuality', 'recovery.stressLevel', 'recovery.bodyFatPercent',
  'outlook.targetBodyweightKg', 'outlook.targets.squat', 'outlook.targets.bench', 'outlook.targets.deadlift',
  'outlook.targets.total', 'outlook.fiveKmTargetSeconds', 'outlook.targetTotalKg',
]);
const LABELS = {
  'goal.type': 'Goal type',
  'schedule.startDate': 'Start date', 'schedule.competitionDate': 'Competition date',
  'schedule.trainingDaysPerWeek': 'Training days per week', 'schedule.sessionMinutes': 'Session minutes',
  'schedule.testDates': 'Test dates',
  'personal.age': 'Age', 'personal.sex': 'Sex', 'personal.heightCm': 'Height (cm)',
  'personal.bodyweightKg': 'Bodyweight (kg)', 'personal.trainingYears': 'Training years',
  'personal.equipment': 'Equipment', 'personal.activityLevel': 'Activity level',
  'level.sbd1rm.squat': 'Squat 1RM (kg)', 'level.sbd1rm.bench': 'Bench 1RM (kg)', 'level.sbd1rm.deadlift': 'Deadlift 1RM (kg)',
  'level.oneRmSource': '1RM source', 'level.recentPrs': 'Recent PRs',
  'level.fiveKm.timeSeconds': '5 km time (seconds)', 'level.fiveKm.date': '5 km date', 'level.fiveKm.conditions': '5 km conditions',
  'limits.squat': 'Squat sticking points', 'limits.bench': 'Bench sticking points', 'limits.deadlift': 'Deadlift sticking points',
  'limits.weakMuscles': 'Weak muscles', 'limits.technique': 'Technique', 'limits.injuries': 'Injuries',
  'limits.surgeries': 'Surgeries', 'limits.jointPain': 'Joint pain', 'limits.mobility': 'Mobility',
  'recovery.sleepHours': 'Sleep hours', 'recovery.sleepQuality': 'Sleep quality (1-5)', 'recovery.stressLevel': 'Stress level (1-5)',
  'recovery.proteinSufficient': 'Protein sufficient', 'recovery.caloriesSufficient': 'Calories sufficient',
  'recovery.bodyFatPercent': 'Body fat (%)', 'recovery.otherSports': 'Other sports',
  'outlook.targetBodyweightKg': 'Target bodyweight (kg)', 'outlook.weightDirection': 'Weight direction',
  'outlook.sbdFocus': 'SBD focus', 'outlook.targets.squat': 'Target squat (kg)', 'outlook.targets.bench': 'Target bench (kg)',
  'outlook.targets.deadlift': 'Target deadlift (kg)', 'outlook.targets.total': 'Target total (kg)',
  'outlook.fiveKmTargetSeconds': '5 km target (seconds)', 'outlook.consistencyGoal': 'Consistency goal',
  'outlook.effortLevel': 'Effort level', 'outlook.riskPreference': 'Risk preference',
  'outlook.competitionName': 'Competition name', 'outlook.weightClass': 'Weight class', 'outlook.targetTotalKg': 'Target total (kg)',
  'outlook.keepMovements': 'Keep movements', 'outlook.avoidMovements': 'Avoid movements', 'outlook.testGroups': 'Test groups',
  'notes': 'Notes',
};

const vals = reactive(Object.fromEntries(SCALAR_PATHS.map(path => [path, ''])));
const varPrs = reactive(Object.fromEntries(VARIATIONS.map(v => [v.id, ''])));
const varTargets = reactive(Object.fromEntries(VARIATIONS.map(v => [v.id, ''])));
const bools = reactive({ protein: null, calories: null });
const lists = reactive({
  testDates: [], squat: [], bench: [], deadlift: [], weakMuscles: [],
  sbdFocus: [], keep: [], avoid: [], testGroups: [],
});

const cycleId = ref('');
const record = ref(null);
const movementOptions = ref([]);
const loaded = ref(false);
const pending = ref('');
const loadError = ref('');
const saveError = ref(null);
const savedAt = ref('');
const step = ref(1);
const completedView = ref(false);
const confirmNewDraft = ref(false);
const goalNote = ref('');
let sequence = 0;
let controller;
let disposed = false;

const busy = computed(() => !!pending.value);
const isCompetition = computed(() => vals['goal.type'] === 'competition');
const isNonCompetition = computed(() => vals['goal.type'] === 'non-competition');
const movementName = computed(() => Object.fromEntries(movementOptions.value.map(m => [m.id, m.name])));
const errorSteps = computed(() => {
  const issues = saveError.value?.issues ?? [];
  const steps = new Set();
  for (const issue of issues) {
    const n = stepForField(issue?.field);
    if (n) steps.add(n);
  }
  return [...steps].sort((a, b) => a - b);
});

function labelize(value) {
  return String(value).replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function variationLabel(id) {
  return movementName.value[id] || VARIATIONS.find(v => v.id === id)?.fallback || id;
}
function stepForField(field) {
  const head = String(field ?? '').split('.')[0];
  const index = ['goal', 'schedule', 'personal', 'level', 'limits', 'recovery', 'outlook'].indexOf(head);
  if (index >= 0) return index + 1;
  if (head === 'notes') return 7;
  return 0;
}
function getPath(object, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), object);
}
function setPath(object, path, value) {
  const keys = path.split('.');
  let node = object;
  for (let i = 0; i < keys.length - 1; i += 1) {
    if (node[keys[i]] == null || typeof node[keys[i]] !== 'object') node[keys[i]] = {};
    node = node[keys[i]];
  }
  node[keys[keys.length - 1]] = value;
}
function stringify(value) {
  return value === null || value === undefined ? '' : String(value);
}
function skeleton() {
  return {
    schemaVersion: SCHEMA_VERSION,
    goal: { type: null },
    schedule: { startDate: null, competitionDate: null, testDates: [], trainingDaysPerWeek: null, sessionMinutes: null },
    personal: { age: null, sex: null, heightCm: null, bodyweightKg: null, trainingYears: null, equipment: null, activityLevel: null },
    level: {
      sbd1rm: { squat: null, bench: null, deadlift: null }, oneRmSource: null, recentPrs: null,
      variationPrs: Object.fromEntries(VARIATIONS.map(v => [v.id, null])),
      fiveKm: { timeSeconds: null, date: null, conditions: null },
    },
    limits: { squat: [], bench: [], deadlift: [], weakMuscles: [], technique: null, injuries: null, surgeries: null, jointPain: null, mobility: null },
    recovery: { sleepHours: null, sleepQuality: null, stressLevel: null, proteinSufficient: null, caloriesSufficient: null, bodyFatPercent: null, otherSports: null },
    outlook: {
      targetBodyweightKg: null, weightDirection: null, sbdFocus: [],
      targets: { squat: null, bench: null, deadlift: null, total: null },
      variationTargets: Object.fromEntries(VARIATIONS.map(v => [v.id, null])),
      fiveKmTargetSeconds: null, consistencyGoal: null, effortLevel: null, riskPreference: null,
      competitionName: null, weightClass: null, targetTotalKg: null, keepMovements: [], avoidMovements: [], testGroups: [],
    },
    notes: null,
  };
}
function scalarValue(path, raw) {
  const text = typeof raw === 'string' ? raw.trim() : raw;
  if (text === '' || text === null || text === undefined) return null;
  if (NUMERIC.has(path)) {
    const number = Number(text);
    return Number.isFinite(number) ? number : null;
  }
  return text;
}
function buildPayload() {
  const payload = skeleton();
  const numericOrNull = raw => {
    const text = typeof raw === 'string' ? raw.trim() : raw;
    if (text === '' || text === null || text === undefined) return null;
    const number = Number(text);
    return Number.isFinite(number) ? number : null;
  };
  for (const path of SCALAR_PATHS) setPath(payload, path, scalarValue(path, vals[path]));
  for (const v of VARIATIONS) {
    payload.level.variationPrs[v.id] = numericOrNull(varPrs[v.id]);
    payload.outlook.variationTargets[v.id] = numericOrNull(varTargets[v.id]);
  }
  payload.recovery.proteinSufficient = bools.protein;
  payload.recovery.caloriesSufficient = bools.calories;
  payload.schedule.testDates = [...lists.testDates];
  payload.limits.squat = [...lists.squat];
  payload.limits.bench = [...lists.bench];
  payload.limits.deadlift = [...lists.deadlift];
  payload.limits.weakMuscles = [...lists.weakMuscles];
  payload.outlook.sbdFocus = [...lists.sbdFocus];
  payload.outlook.keepMovements = [...lists.keep];
  payload.outlook.avoidMovements = [...lists.avoid];
  payload.outlook.testGroups = [...lists.testGroups];
  return payload;
}
function loadFromPayload(payload) {
  const source = payload && typeof payload === 'object' ? payload : skeleton();
  for (const path of SCALAR_PATHS) vals[path] = stringify(getPath(source, path));
  for (const v of VARIATIONS) {
    varPrs[v.id] = stringify(source.level?.variationPrs?.[v.id]);
    varTargets[v.id] = stringify(source.outlook?.variationTargets?.[v.id]);
  }
  bools.protein = source.recovery?.proteinSufficient ?? null;
  bools.calories = source.recovery?.caloriesSufficient ?? null;
  lists.testDates = [...(source.schedule?.testDates ?? [])];
  lists.squat = [...(source.limits?.squat ?? [])];
  lists.bench = [...(source.limits?.bench ?? [])];
  lists.deadlift = [...(source.limits?.deadlift ?? [])];
  lists.weakMuscles = [...(source.limits?.weakMuscles ?? [])];
  lists.sbdFocus = [...(source.outlook?.sbdFocus ?? [])];
  lists.keep = [...(source.outlook?.keepMovements ?? [])];
  lists.avoid = [...(source.outlook?.avoidMovements ?? [])];
  lists.testGroups = [...(source.outlook?.testGroups ?? [])];
}
function toggle(list, value) {
  const index = list.indexOf(value);
  if (index >= 0) list.splice(index, 1);
  else list.push(value);
}
function applyGoal(type) {
  vals['goal.type'] = type;
  if (type === 'competition') {
    lists.testGroups = ['sbd'];
    lists.testDates = vals['schedule.competitionDate'] ? [vals['schedule.competitionDate']] : [];
    goalNote.value = 'Competition goal: test groups are locked to SBD and the test date mirrors your competition date.';
  } else if (type === 'non-competition') {
    lists.testGroups = [];
    lists.testDates = [];
    goalNote.value = 'Non-competition goal: choose 1-4 test groups and 1-4 test dates below.';
  } else {
    goalNote.value = '';
  }
}
watch(() => vals['schedule.competitionDate'], value => {
  if (isCompetition.value) lists.testDates = value ? [value] : [];
});
function addTestDate() {
  if (lists.testDates.length < 4) lists.testDates.push('');
}
function removeTestDate(index) {
  lists.testDates.splice(index, 1);
}

function isCurrent(context) {
  return !disposed && context.sequence === sequence;
}
function responseError(payload, fallback) {
  const detail = payload?.detail ?? payload?.error ?? payload?.message;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}
async function request(path, context, options = {}) {
  const response = await fetch(path, { cache: 'no-store', signal: context.controller.signal, ...options });
  let payload = null;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) {
    const failure = new Error(responseError(payload, `Request failed (${response.status}).`));
    failure.status = response.status;
    failure.issues = Array.isArray(payload?.errors) ? payload.errors : [];
    throw failure;
  }
  return payload;
}
async function loadAll() {
  controller?.abort();
  controller = new AbortController();
  const context = { sequence: ++sequence, controller };
  pending.value = 'load';
  loadError.value = '';
  saveError.value = null;
  loaded.value = false;
  try {
    const cycles = await request('/api/cycle', context);
    if (!isCurrent(context)) return;
    const active = cycles?.active_cycle_id;
    if (!active) throw new Error('No active cycle is available. Activate a plan before filling the questionnaire.');
    cycleId.value = active;
    const [questionnaire, plan] = await Promise.all([
      request(`/api/questionnaire?${new URLSearchParams({ cycle_id: active })}`, context),
      request('/api/plan', context),
    ]);
    if (!isCurrent(context)) return;
    const seen = new Map();
    for (const row of plan?.workouts ?? []) {
      if (row?.movementId && !seen.has(row.movementId)) seen.set(row.movementId, row.movement || row.movementId);
    }
    movementOptions.value = [...seen.entries()].map(([id, name]) => ({ id, name }));
    record.value = questionnaire;
    savedAt.value = questionnaire?.updated_at ?? '';
    loadFromPayload(questionnaire?.payload);
    completedView.value = questionnaire?.status === 'complete';
    step.value = 1;
    goalNote.value = '';
    loaded.value = true;
  } catch (failure) {
    if (!isCurrent(context)) return;
    loadError.value = failure.message || 'The questionnaire could not be loaded. Try again.';
  } finally {
    if (isCurrent(context)) pending.value = '';
  }
}
async function save(status) {
  if (busy.value || !loaded.value) return;
  controller?.abort();
  controller = new AbortController();
  const context = { sequence: ++sequence, controller };
  pending.value = status;
  saveError.value = null;
  try {
    const body = { cycle_id: cycleId.value, status, payload: buildPayload() };
    const result = await request('/api/questionnaire', context, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!isCurrent(context)) return;
    record.value = result;
    savedAt.value = result?.updated_at ?? '';
    if (status === 'complete') {
      completedView.value = true;
      confirmNewDraft.value = false;
    }
  } catch (failure) {
    if (!isCurrent(context)) return;
    saveError.value = {
      message: failure.status === 409
        ? failure.message || 'This cycle is archived and read-only. Your inputs are kept.'
        : failure.message || 'The questionnaire could not be saved. Your inputs are kept.',
      issues: failure.issues ?? [],
      status: failure.status,
    };
  } finally {
    if (isCurrent(context)) pending.value = '';
  }
}
async function startNewDraft() {
  if (busy.value) return;
  controller?.abort();
  controller = new AbortController();
  const context = { sequence: ++sequence, controller };
  pending.value = 'newdraft';
  saveError.value = null;
  try {
    const body = { cycle_id: cycleId.value, status: 'draft', payload: skeleton() };
    const result = await request('/api/questionnaire', context, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!isCurrent(context)) return;
    record.value = result;
    savedAt.value = result?.updated_at ?? '';
    loadFromPayload(result?.payload ?? skeleton());
    completedView.value = false;
    confirmNewDraft.value = false;
    step.value = 1;
    goalNote.value = '';
  } catch (failure) {
    if (!isCurrent(context)) return;
    saveError.value = { message: failure.message || 'A new draft could not be started.', issues: failure.issues ?? [], status: failure.status };
  } finally {
    if (isCurrent(context)) pending.value = '';
  }
}
function next() { if (step.value < 7) step.value += 1; }
function back() { if (step.value > 1) step.value -= 1; }
function goTo(n) { step.value = n; }

function fmt(value) {
  if (value === null || value === undefined || value === '') return 'Not provided';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.length ? value.map(v => labelize(v)).join(', ') : 'Not provided';
  return String(value);
}
function fmtMovements(ids) {
  return ids.length ? ids.map(id => movementName.value[id] || id).join(', ') : 'Not provided';
}
const summary = computed(() => {
  const p = buildPayload();
  const row = (label, text) => ({ label, text });
  const scalar = path => row(LABELS[path] ?? path, fmt(getPath(p, path)));
  return [
    { n: 1, name: STEP_NAMES[1], rows: [scalar('goal.type')] },
    { n: 2, name: STEP_NAMES[2], rows: [
      scalar('schedule.startDate'), scalar('schedule.competitionDate'),
      row(LABELS['schedule.testDates'], fmt(p.schedule.testDates)),
      scalar('schedule.trainingDaysPerWeek'), scalar('schedule.sessionMinutes'),
    ] },
    { n: 3, name: STEP_NAMES[3], rows: [
      scalar('personal.age'), scalar('personal.sex'), scalar('personal.heightCm'), scalar('personal.bodyweightKg'),
      scalar('personal.trainingYears'), scalar('personal.equipment'), scalar('personal.activityLevel'),
    ] },
    { n: 4, name: STEP_NAMES[4], rows: [
      scalar('level.sbd1rm.squat'), scalar('level.sbd1rm.bench'), scalar('level.sbd1rm.deadlift'),
      scalar('level.oneRmSource'), scalar('level.recentPrs'),
      ...VARIATIONS.map(v => row(`PR · ${variationLabel(v.id)}`, fmt(p.level.variationPrs[v.id]))),
      scalar('level.fiveKm.timeSeconds'), scalar('level.fiveKm.date'), scalar('level.fiveKm.conditions'),
    ] },
    { n: 5, name: STEP_NAMES[5], rows: [
      row(LABELS['limits.squat'], fmt(p.limits.squat)), row(LABELS['limits.bench'], fmt(p.limits.bench)),
      row(LABELS['limits.deadlift'], fmt(p.limits.deadlift)), row(LABELS['limits.weakMuscles'], fmt(p.limits.weakMuscles)),
      scalar('limits.technique'), scalar('limits.injuries'), scalar('limits.surgeries'), scalar('limits.jointPain'), scalar('limits.mobility'),
    ] },
    { n: 6, name: STEP_NAMES[6], rows: [
      scalar('recovery.sleepHours'), scalar('recovery.sleepQuality'), scalar('recovery.stressLevel'),
      row(LABELS['recovery.proteinSufficient'], fmt(p.recovery.proteinSufficient)),
      row(LABELS['recovery.caloriesSufficient'], fmt(p.recovery.caloriesSufficient)),
      scalar('recovery.bodyFatPercent'), scalar('recovery.otherSports'),
    ] },
    { n: 7, name: STEP_NAMES[7], rows: [
      scalar('outlook.targetBodyweightKg'), scalar('outlook.weightDirection'),
      row(LABELS['outlook.sbdFocus'], fmt(p.outlook.sbdFocus)),
      scalar('outlook.targets.squat'), scalar('outlook.targets.bench'), scalar('outlook.targets.deadlift'), scalar('outlook.targets.total'),
      ...VARIATIONS.map(v => row(`Target · ${variationLabel(v.id)}`, fmt(p.outlook.variationTargets[v.id]))),
      scalar('outlook.fiveKmTargetSeconds'), scalar('outlook.consistencyGoal'), scalar('outlook.effortLevel'), scalar('outlook.riskPreference'),
      scalar('outlook.competitionName'), scalar('outlook.weightClass'), scalar('outlook.targetTotalKg'),
      row(LABELS['outlook.keepMovements'], fmtMovements(p.outlook.keepMovements)),
      row(LABELS['outlook.avoidMovements'], fmtMovements(p.outlook.avoidMovements)),
      row(LABELS['outlook.testGroups'], fmt(p.outlook.testGroups)),
      row(LABELS['notes'], fmt(p.notes)),
    ] },
  ];
});

onMounted(loadAll);
onBeforeUnmount(() => { disposed = true; sequence += 1; controller?.abort(); });
</script>

<template>
  <section class="questionnaire" data-testid="questionnaire-view" :aria-busy="busy" :aria-labelledby="`${prefix}-heading`">
    <header>
      <p class="kicker">NEXT-CYCLE QUESTIONNAIRE</p>
      <h2 :id="`${prefix}-heading`">Seven steps.<br><em>One clear next cycle.</em></h2>
      <p class="reading-note">Answer one step at a time. Nothing is auto-filled from your plan or profile; blank fields stay empty. Save a draft at any point, then complete when you are ready.</p>
    </header>

    <p v-if="pending === 'load'" class="reading-note" role="status">Loading your cycle and questionnaire…</p>

    <section v-if="loadError" class="panel-error" data-testid="questionnaire-error" role="alert">
      <h3>Could not load the questionnaire</h3>
      <p class="error-message">{{ loadError }}</p>
      <button type="button" data-testid="questionnaire-retry" :disabled="busy" @click="loadAll">Retry</button>
    </section>

    <template v-if="loaded">
      <!-- Completed, read-only summary -->
      <section v-if="completedView" class="completed" data-testid="questionnaire-summary">
        <h3>Questionnaire complete.</h3>
        <p class="reading-note">Saved {{ savedAt || 'timestamp unavailable' }}. This record is read-only. Start a new draft to make changes.</p>
        <div v-for="group in summary" :key="group.n" class="summary-group">
          <h4>{{ group.n }} · {{ group.name }}</h4>
          <dl>
            <div v-for="r in group.rows" :key="r.label"><dt>{{ r.label }}</dt><dd>{{ r.text }}</dd></div>
          </dl>
        </div>
        <section v-if="saveError" class="panel-error" data-testid="questionnaire-error" role="alert">
          <p class="error-message">{{ saveError.message }}</p>
        </section>
        <div v-if="!confirmNewDraft" class="actions">
          <button type="button" data-testid="questionnaire-new-draft" :disabled="busy" @click="confirmNewDraft = true">Start a new draft</button>
        </div>
        <div v-else class="confirm-box">
          <p>Starting a new draft replaces this completed record with an empty draft. This cannot be undone. Continue?</p>
          <div class="actions">
            <button type="button" class="primary" data-testid="questionnaire-new-draft" :disabled="busy" @click="startNewDraft">
              {{ pending === 'newdraft' ? 'Starting…' : 'Yes, start a new draft' }}
            </button>
            <button type="button" :disabled="busy" @click="confirmNewDraft = false">Cancel</button>
          </div>
        </div>
      </section>

      <!-- Wizard -->
      <template v-else>
        <p class="progress" data-testid="questionnaire-progress">Step {{ step }} of 7 · {{ STEP_NAMES[step] }}</p>
        <div class="progress-track" aria-hidden="true"><span :style="{ width: `${(step / 7) * 100}%` }"></span></div>

        <section v-if="saveError" class="panel-error" data-testid="questionnaire-error" role="alert">
          <h3>{{ saveError.status === 409 ? 'Cycle is read-only' : 'The server rejected some fields' }}</h3>
          <p class="error-message">{{ saveError.message }}</p>
          <ol v-if="saveError.issues.length" class="error-list">
            <li v-for="(issue, index) in saveError.issues" :key="index">
              <strong>{{ issue.field || 'Field' }}</strong>
              <span>Expected: {{ issue.expected ?? 'a valid value' }}</span>
              <span v-if="issue.got !== undefined">Got: {{ typeof issue.got === 'object' ? JSON.stringify(issue.got) : issue.got }}</span>
            </li>
          </ol>
          <div v-if="errorSteps.length" class="actions">
            <button v-for="n in errorSteps" :key="n" type="button" @click="goTo(n)">Go to step {{ n }} · {{ STEP_NAMES[n] }}</button>
          </div>
        </section>

        <form class="wizard" @submit.prevent="next">
          <!-- Step 1: Goal -->
          <div v-show="step === 1" class="step" data-testid="questionnaire-step" data-step="1">
            <h3>What is this cycle for?</h3>
            <div class="choice-row" role="radiogroup" aria-label="Goal type">
              <label class="choice"><input type="radio" name="goal" data-field="goal.type" value="competition" :checked="vals['goal.type'] === 'competition'" @change="applyGoal('competition')"><span>Competition</span></label>
              <label class="choice"><input type="radio" name="goal" data-field="goal.type" value="non-competition" :checked="vals['goal.type'] === 'non-competition'" @change="applyGoal('non-competition')"><span>Non-competition</span></label>
            </div>
            <p v-if="goalNote" class="reading-note" role="status">{{ goalNote }}</p>
          </div>

          <!-- Step 2: Schedule -->
          <div v-show="step === 2" class="step" data-testid="questionnaire-step" data-step="2">
            <h3>Schedule</h3>
            <div class="grid">
              <label class="field"><span>Start date</span>
                <input type="date" data-field="schedule.startDate" v-model="vals['schedule.startDate']"></label>
              <label class="field"><span>Training days per week (1-6)</span>
                <input type="number" min="1" max="6" step="1" inputmode="numeric" data-field="schedule.trainingDaysPerWeek" v-model="vals['schedule.trainingDaysPerWeek']"></label>
              <label class="field"><span>Session minutes</span>
                <input type="number" min="15" max="240" step="1" inputmode="numeric" data-field="schedule.sessionMinutes" v-model="vals['schedule.sessionMinutes']"></label>
              <label v-if="isCompetition" class="field"><span>Competition date</span>
                <input type="date" data-field="schedule.competitionDate" v-model="vals['schedule.competitionDate']"></label>
            </div>
            <div v-if="isCompetition" class="field">
              <span>Test dates (locked to competition date)</span>
              <p class="readonly-value" data-field="schedule.testDates">{{ lists.testDates[0] || 'Set a competition date above' }}</p>
            </div>
            <div v-else-if="isNonCompetition" class="field">
              <span>Test dates (1-4)</span>
              <div v-for="(d, i) in lists.testDates" :key="i" class="date-row">
                <input type="date" :data-field="`schedule.testDates.${i}`" v-model="lists.testDates[i]">
                <button type="button" class="small" @click="removeTestDate(i)">Remove</button>
              </div>
              <button type="button" class="small" :disabled="lists.testDates.length >= 4" @click="addTestDate">Add test date</button>
            </div>
          </div>

          <!-- Step 3: Personal -->
          <div v-show="step === 3" class="step" data-testid="questionnaire-step" data-step="3">
            <h3>Personal</h3>
            <div class="grid">
              <label class="field"><span>Age</span>
                <input type="number" min="10" max="100" step="1" inputmode="numeric" data-field="personal.age" v-model="vals['personal.age']"></label>
              <label class="field"><span>Sex</span>
                <select data-field="personal.sex" v-model="vals['personal.sex']">
                  <option value="">Not provided</option>
                  <option v-for="s in SEX" :key="s" :value="s">{{ labelize(s) }}</option>
                </select></label>
              <label class="field"><span>Height (cm)</span>
                <input type="number" min="100" max="250" step="any" inputmode="decimal" data-field="personal.heightCm" v-model="vals['personal.heightCm']"></label>
              <label class="field"><span>Bodyweight (kg)</span>
                <input type="number" min="30" max="300" step="any" inputmode="decimal" data-field="personal.bodyweightKg" v-model="vals['personal.bodyweightKg']"></label>
              <label class="field"><span>Training years</span>
                <input type="number" min="0" max="60" step="any" inputmode="decimal" data-field="personal.trainingYears" v-model="vals['personal.trainingYears']"></label>
              <label class="field"><span>Equipment</span>
                <select data-field="personal.equipment" v-model="vals['personal.equipment']">
                  <option value="">Not provided</option>
                  <option v-for="e in EQUIPMENT" :key="e" :value="e">{{ labelize(e) }}</option>
                </select></label>
              <label class="field wide"><span>Activity level</span>
                <input type="text" maxlength="200" data-field="personal.activityLevel" v-model="vals['personal.activityLevel']"></label>
            </div>
          </div>

          <!-- Step 4: Level -->
          <div v-show="step === 4" class="step" data-testid="questionnaire-step" data-step="4">
            <h3>Current level</h3>
            <div class="grid">
              <label v-for="lift in SBD" :key="lift" class="field"><span>{{ labelize(lift) }} 1RM (kg)</span>
                <input type="number" min="20" max="600" step="any" inputmode="decimal" :data-field="`level.sbd1rm.${lift}`" v-model="vals[`level.sbd1rm.${lift}`]"></label>
              <label class="field"><span>1RM source</span>
                <select data-field="level.oneRmSource" v-model="vals['level.oneRmSource']">
                  <option value="">Not provided</option>
                  <option v-for="o in ONE_RM" :key="o" :value="o">{{ labelize(o) }}</option>
                </select></label>
              <label class="field wide"><span>Recent PRs</span>
                <textarea rows="2" maxlength="500" data-field="level.recentPrs" v-model="vals['level.recentPrs']"></textarea></label>
            </div>
            <h4>Variation PRs (kg)</h4>
            <div class="grid">
              <label v-for="v in VARIATIONS" :key="v.id" class="field"><span>{{ variationLabel(v.id) }}</span>
                <input type="number" min="0" max="600" step="any" inputmode="decimal" :data-field="`level.variationPrs.${v.id}`" v-model="varPrs[v.id]"></label>
            </div>
            <h4>Five kilometre</h4>
            <div class="grid">
              <label class="field"><span>Time (seconds)</span>
                <input type="number" min="600" max="3600" step="1" inputmode="numeric" data-field="level.fiveKm.timeSeconds" v-model="vals['level.fiveKm.timeSeconds']"></label>
              <label class="field"><span>Date</span>
                <input type="date" data-field="level.fiveKm.date" v-model="vals['level.fiveKm.date']"></label>
              <label class="field wide"><span>Conditions</span>
                <input type="text" maxlength="200" data-field="level.fiveKm.conditions" v-model="vals['level.fiveKm.conditions']"></label>
            </div>
          </div>

          <!-- Step 5: Limits -->
          <div v-show="step === 5" class="step" data-testid="questionnaire-step" data-step="5">
            <h3>Limits</h3>
            <fieldset v-for="lift in SBD" :key="lift" class="check-group">
              <legend>{{ labelize(lift) }} sticking points</legend>
              <label v-for="opt in STICKING[lift]" :key="opt" class="check">
                <input type="checkbox" :data-field="`limits.${lift}`" :checked="lists[lift].includes(opt)" @change="toggle(lists[lift], opt)">
                <span>{{ labelize(opt) }}</span>
              </label>
            </fieldset>
            <fieldset class="check-group">
              <legend>Weak muscles</legend>
              <label v-for="opt in WEAK_MUSCLES" :key="opt" class="check">
                <input type="checkbox" data-field="limits.weakMuscles" :checked="lists.weakMuscles.includes(opt)" @change="toggle(lists.weakMuscles, opt)">
                <span>{{ labelize(opt) }}</span>
              </label>
            </fieldset>
            <div class="grid">
              <label v-for="key in ['technique', 'injuries', 'surgeries', 'jointPain', 'mobility']" :key="key" class="field wide">
                <span>{{ labelize(key) }}</span>
                <textarea rows="2" maxlength="500" :data-field="`limits.${key}`" v-model="vals[`limits.${key}`]"></textarea></label>
            </div>
          </div>

          <!-- Step 6: Recovery -->
          <div v-show="step === 6" class="step" data-testid="questionnaire-step" data-step="6">
            <h3>Recovery</h3>
            <div class="grid">
              <label class="field"><span>Sleep hours</span>
                <input type="number" min="0" max="14" step="any" inputmode="decimal" data-field="recovery.sleepHours" v-model="vals['recovery.sleepHours']"></label>
              <label class="field"><span>Sleep quality (1-5)</span>
                <input type="number" min="1" max="5" step="1" inputmode="numeric" data-field="recovery.sleepQuality" v-model="vals['recovery.sleepQuality']"></label>
              <label class="field"><span>Stress level (1-5)</span>
                <input type="number" min="1" max="5" step="1" inputmode="numeric" data-field="recovery.stressLevel" v-model="vals['recovery.stressLevel']"></label>
              <label class="field"><span>Body fat (%)</span>
                <input type="number" min="3" max="60" step="any" inputmode="decimal" data-field="recovery.bodyFatPercent" v-model="vals['recovery.bodyFatPercent']"></label>
              <label class="field wide"><span>Other sports</span>
                <input type="text" maxlength="300" data-field="recovery.otherSports" v-model="vals['recovery.otherSports']"></label>
            </div>
            <div class="tri" data-field="recovery.proteinSufficient">
              <span>Protein sufficient</span>
              <div class="choice-row">
                <button type="button" :class="{ on: bools.protein === true }" @click="bools.protein = true">Yes</button>
                <button type="button" :class="{ on: bools.protein === false }" @click="bools.protein = false">No</button>
                <button type="button" :class="{ on: bools.protein === null }" @click="bools.protein = null">Not provided</button>
              </div>
            </div>
            <div class="tri" data-field="recovery.caloriesSufficient">
              <span>Calories sufficient</span>
              <div class="choice-row">
                <button type="button" :class="{ on: bools.calories === true }" @click="bools.calories = true">Yes</button>
                <button type="button" :class="{ on: bools.calories === false }" @click="bools.calories = false">No</button>
                <button type="button" :class="{ on: bools.calories === null }" @click="bools.calories = null">Not provided</button>
              </div>
            </div>
          </div>

          <!-- Step 7: Outlook + summary -->
          <div v-show="step === 7" class="step" data-testid="questionnaire-step" data-step="7">
            <h3>Outlook</h3>
            <div class="grid">
              <label class="field"><span>Target bodyweight (kg)</span>
                <input type="number" min="30" max="300" step="any" inputmode="decimal" data-field="outlook.targetBodyweightKg" v-model="vals['outlook.targetBodyweightKg']"></label>
              <label class="field"><span>Weight direction</span>
                <select data-field="outlook.weightDirection" v-model="vals['outlook.weightDirection']">
                  <option value="">Not provided</option>
                  <option v-for="w in WEIGHT_DIR" :key="w" :value="w">{{ labelize(w) }}</option>
                </select></label>
              <label class="field"><span>Effort level</span>
                <select data-field="outlook.effortLevel" v-model="vals['outlook.effortLevel']">
                  <option value="">Not provided</option>
                  <option v-for="e in EFFORT" :key="e" :value="e">{{ labelize(e) }}</option>
                </select></label>
              <label class="field"><span>Risk preference</span>
                <select data-field="outlook.riskPreference" v-model="vals['outlook.riskPreference']">
                  <option value="">Not provided</option>
                  <option v-for="r in RISK" :key="r" :value="r">{{ labelize(r) }}</option>
                </select></label>
              <label v-for="lift in [...SBD, 'total']" :key="lift" class="field"><span>Target {{ lift }} (kg)</span>
                <input type="number" min="20" max="1500" step="any" inputmode="decimal" :data-field="`outlook.targets.${lift}`" v-model="vals[`outlook.targets.${lift}`]"></label>
              <label class="field"><span>5 km target (seconds)</span>
                <input type="number" min="600" max="3600" step="1" inputmode="numeric" data-field="outlook.fiveKmTargetSeconds" v-model="vals['outlook.fiveKmTargetSeconds']"></label>
              <label class="field"><span>Target total (kg)</span>
                <input type="number" min="60" max="1800" step="any" inputmode="decimal" data-field="outlook.targetTotalKg" v-model="vals['outlook.targetTotalKg']"></label>
              <label class="field"><span>Competition name</span>
                <input type="text" maxlength="200" data-field="outlook.competitionName" v-model="vals['outlook.competitionName']"></label>
              <label class="field"><span>Weight class</span>
                <input type="text" maxlength="50" data-field="outlook.weightClass" v-model="vals['outlook.weightClass']"></label>
              <label class="field wide"><span>Consistency goal</span>
                <input type="text" maxlength="300" data-field="outlook.consistencyGoal" v-model="vals['outlook.consistencyGoal']"></label>
            </div>

            <fieldset class="check-group">
              <legend>SBD focus (up to 3)</legend>
              <label v-for="lift in SBD" :key="lift" class="check">
                <input type="checkbox" data-field="outlook.sbdFocus" :checked="lists.sbdFocus.includes(lift)" :disabled="!lists.sbdFocus.includes(lift) && lists.sbdFocus.length >= 3" @change="toggle(lists.sbdFocus, lift)">
                <span>{{ labelize(lift) }}</span>
              </label>
            </fieldset>

            <h4>Variation targets (kg)</h4>
            <div class="grid">
              <label v-for="v in VARIATIONS" :key="v.id" class="field"><span>{{ variationLabel(v.id) }}</span>
                <input type="number" min="0" max="600" step="any" inputmode="decimal" :data-field="`outlook.variationTargets.${v.id}`" v-model="varTargets[v.id]"></label>
            </div>

            <fieldset class="check-group">
              <legend>Keep movements (from active plan)</legend>
              <p v-if="!movementOptions.length" class="reading-note">No movements available in the active plan.</p>
              <label v-for="m in movementOptions" :key="`keep-${m.id}`" class="check">
                <input type="checkbox" data-field="outlook.keepMovements" :checked="lists.keep.includes(m.id)" @change="toggle(lists.keep, m.id)">
                <span>{{ m.name }}</span>
              </label>
            </fieldset>
            <fieldset class="check-group">
              <legend>Avoid movements (from active plan)</legend>
              <p v-if="!movementOptions.length" class="reading-note">No movements available in the active plan.</p>
              <label v-for="m in movementOptions" :key="`avoid-${m.id}`" class="check">
                <input type="checkbox" data-field="outlook.avoidMovements" :checked="lists.avoid.includes(m.id)" @change="toggle(lists.avoid, m.id)">
                <span>{{ m.name }}</span>
              </label>
            </fieldset>

            <div v-if="isCompetition" class="field">
              <span>Test groups (locked to SBD)</span>
              <p class="readonly-value" data-field="outlook.testGroups">SBD</p>
            </div>
            <fieldset v-else-if="isNonCompetition" class="check-group">
              <legend>Test groups (1-4)</legend>
              <label v-for="g in TEST_GROUPS" :key="g" class="check">
                <input type="checkbox" data-field="outlook.testGroups" :checked="lists.testGroups.includes(g)" :disabled="!lists.testGroups.includes(g) && lists.testGroups.length >= 4" @change="toggle(lists.testGroups, g)">
                <span>{{ labelize(g) }}</span>
              </label>
            </fieldset>

            <label class="field wide"><span>Notes</span>
              <textarea rows="3" maxlength="1000" data-field="notes" v-model="vals['notes']"></textarea></label>

            <section class="summary" data-testid="questionnaire-summary">
              <h4>Review your answers</h4>
              <p class="reading-note">Blank fields show "Not provided". Required fields are enforced by the server when you complete.</p>
              <div v-for="group in summary" :key="group.n" class="summary-group">
                <h5>{{ group.n }} · {{ group.name }}</h5>
                <dl>
                  <div v-for="r in group.rows" :key="r.label"><dt>{{ r.label }}</dt><dd>{{ r.text }}</dd></div>
                </dl>
              </div>
            </section>
          </div>

          <div class="actions wizard-actions">
            <button type="button" data-testid="questionnaire-back" :disabled="step === 1 || busy" @click="back">Back</button>
            <button type="button" data-testid="questionnaire-save-draft" :disabled="busy" @click="save('draft')">
              {{ pending === 'draft' ? 'Saving…' : 'Save draft' }}
            </button>
            <button v-if="step < 7" type="button" class="primary" data-testid="questionnaire-next" :disabled="busy" @click="next">Next</button>
            <button v-else type="button" class="primary" data-testid="questionnaire-complete" :disabled="busy" @click="save('complete')">
              {{ pending === 'complete' ? 'Completing…' : 'Complete' }}
            </button>
          </div>
          <p v-if="savedAt && !saveError" class="reading-note" role="status">Draft saved · {{ savedAt }}</p>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.questionnaire { box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0; margin: 24px 0; padding: 20px 16px; border: 1px solid var(--line); color: var(--ink); background: var(--panel); font: 14px/1.6 var(--sans); overflow-wrap: anywhere; }
.questionnaire *, .questionnaire *::before, .questionnaire *::after { box-sizing: border-box; }
p, h2, h3, h4, h5, dl, dd { margin: 0; }
h2 { margin-top: 8px; font: 400 clamp(28px, 5vw, 36px)/1.15 var(--serif); }
h2 em { color: var(--muted); font-weight: 400; }
h3 { font: 400 24px/1.25 var(--serif); }
h4 { margin-top: 18px; font: 600 15px/1.4 var(--sans); }
h5 { font: 600 13px/1.4 var(--sans); }
.kicker { color: var(--accent); font: 11px/1.6 var(--mono); letter-spacing: .06em; text-transform: uppercase; }
.reading-note { margin-top: 10px; max-width: 75ch; color: var(--muted); font: 12px/1.7 var(--sans); }
.progress { margin-top: 20px; font: 600 13px/1.5 var(--mono); color: var(--accent); }
.progress-track { height: 4px; margin-top: 8px; background: var(--panel2); border-radius: 2px; overflow: hidden; }
.progress-track span { display: block; height: 100%; background: var(--accent); transition: width .2s ease; }
.wizard { display: grid; gap: 16px; min-width: 0; margin-top: 18px; }
.step { display: grid; gap: 14px; min-width: 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 14px; min-width: 0; }
.field { display: grid; gap: 6px; min-width: 0; align-content: start; }
.field.wide { grid-column: 1 / -1; }
.field > span { font-size: 13px; font-weight: 600; }
input, select, textarea { width: 100%; min-width: 0; min-height: 44px; padding: 10px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--panel2); font: 14px/1.4 var(--sans); }
textarea { min-height: 60px; resize: vertical; }
input:focus-visible, select:focus-visible, textarea:focus-visible, button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.readonly-value { min-height: 44px; display: flex; align-items: center; padding: 10px; border: 1px dashed var(--line); border-radius: 2px; background: var(--panel2); color: var(--muted); font: 14px/1.4 var(--mono); }
.choice-row { display: flex; flex-wrap: wrap; gap: 10px; }
.choice { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 2px; cursor: pointer; }
.choice input { width: 20px; height: 20px; min-height: 20px; accent-color: var(--accent); }
.check-group { display: grid; gap: 8px; margin: 0; padding: 12px; min-width: 0; border: 1px solid var(--line); border-radius: 2px; }
.check-group legend { padding: 0 6px; font-weight: 600; font-size: 13px; }
.check { display: flex; align-items: center; gap: 10px; min-height: 44px; cursor: pointer; }
.check input { flex: 0 0 22px; width: 22px; height: 22px; min-height: 22px; accent-color: var(--accent); }
.check span { min-width: 0; }
.date-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; margin-bottom: 8px; }
.tri { display: grid; gap: 8px; }
.tri > span { font-size: 13px; font-weight: 600; }
.tri .choice-row button { min-height: 44px; }
.tri .choice-row button.on { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
button { min-width: 44px; min-height: 44px; max-width: 100%; padding: 10px 14px; border: 1px solid var(--line); border-radius: 2px; color: var(--ink); background: var(--panel); font: 13px/1.5 var(--sans); white-space: normal; overflow-wrap: anywhere; cursor: pointer; }
button.small { min-height: 44px; padding: 8px 12px; font-size: 12px; }
button:hover:not(:disabled) { border-color: var(--accent); background: var(--panel2); }
button:disabled { opacity: .55; cursor: not-allowed; }
button.primary { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
.wizard-actions { border-top: 1px solid var(--line); padding-top: 16px; }
.panel-error { min-width: 0; margin-top: 18px; padding: 16px 12px; border: 1px solid var(--accent); border-left-width: 3px; }
.panel-error h3 { font-size: 18px; }
.error-message { margin-top: 8px; white-space: pre-wrap; }
.error-list { margin: 12px 0 0; padding-left: 20px; display: grid; gap: 8px; }
.error-list li { display: grid; gap: 2px; min-width: 0; font-size: 12px; }
.error-list strong { font-family: var(--mono); }
.error-list span { color: var(--muted); }
.summary { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--line); }
.summary-group { margin-top: 14px; }
.summary-group dl { display: grid; gap: 6px; margin-top: 8px; }
.summary-group dl > div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 10px; }
.summary-group dt { color: var(--muted); font-size: 12px; }
.summary-group dd { min-width: 0; font: 12px/1.6 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; }
.completed .summary-group h4 { margin-top: 16px; }
.confirm-box { margin-top: 14px; padding: 14px; border: 1px solid var(--accent); border-radius: 2px; }
.confirm-box p { font-size: 13px; }
@media (max-width: 420px) {
  .questionnaire { padding: 16px 12px; }
  .grid { grid-template-columns: minmax(0, 1fr); }
  .wizard-actions button, .actions button { flex: 1 1 auto; }
  .summary-group dl > div { grid-template-columns: minmax(0, 1fr); gap: 2px; }
}
</style>