<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { animate } from '@motionone/dom';
import packageInfo from '../package.json';
const [major, , patch] = packageInfo.version.split('.');
const releaseVersion = `${major}.${patch.padStart(2, '0')}`;
import MuscleMap from './components/MuscleMap.vue';
import ExerciseRows from './components/ExerciseRows.vue';
import WarmupSuggestions from './components/WarmupSuggestions.vue';
import WeekCapacity from './components/WeekCapacity.vue';
import CapacityBoard from './components/CapacityBoard.vue';
import DailyRecord from './components/DailyRecord.vue';
import PrescriptionSettings from './components/PrescriptionSettings.vue';
import TrendView from './components/TrendView.vue';
import ArchiveView from './components/ArchiveView.vue';
import PlanImport from './components/PlanImport.vue';
import QuestionnaireView from './components/QuestionnaireView.vue';
import AiOutlook from './components/AiOutlook.vue';
import AttemptBoard from './components/AttemptBoard.vue';
import WelcomeView from './components/WelcomeView.vue';
import LoginView from './components/LoginView.vue';
import RegisterView from './components/RegisterView.vue';
import CycleStrip from './components/CycleStrip.vue';
import ShareButton from './components/ShareButton.vue';
import BeanMark from './components/BeanMark.vue';
import CyclePrestart from './components/CyclePrestart.vue';
import LoadProfile from './components/LoadProfile.vue';

const route = useRoute();
const router = useRouter();
const plan = ref(null);
const analysis = ref(null);
const performance = ref(null);
const geometry = ref(null);
const calendar = ref(null);
const cycles = ref(null);
const logs = ref({});
const prescriptionInfo = ref(null);
async function refreshPrescription() {
  try { prescriptionInfo.value = await get(`/api/prescription?${new URLSearchParams({ cycle_id: plan.value.meta.planId })}`); }
  catch { error.value = 'Updated prescription details could not be loaded. Your saved data has not been changed.'; }
}
async function savedLog(saved) {
  const { key, ...values } = saved;
  logs.value[key] = values;
  try {
    [analysis.value, calendar.value, performance.value] = await Promise.all([get(`/api/analysis?mode=${mode.value}`), get('/api/today'), get('/api/performance')]);
    await refreshPrescription();
  } catch { error.value = 'Your log was saved, but the updated summary could not be loaded. Retry the connection.'; }
}
const error = ref('');
const loading = ref(false);
const session = ref(null);
const authReady = ref(false);
const mode = ref('plan');
const page = computed(() => {
  if (['/', '/welcome'].includes(route.path)) return 'welcome';
  if (route.path === '/login') return 'login';
  if (route.path === '/register') return 'register';
  if (route.path.startsWith('/plan')) return 'plan';
  if (route.path === '/archive' || route.path.startsWith('/archive/')) return 'archive';
  if (route.path === '/today') return 'today';
  return route.path.slice(1);
});
const isPublic = computed(() => ['welcome', 'login', 'register'].includes(page.value));
const currentWeek = computed(() => {
  if (!plan.value) return 1;
  if (route.params.blockId) return plan.value.weeks.find(week => week.blockId === route.params.blockId)?.n || 0;
  if (route.path === '/plan/test') return plan.value.weeks.find(week => week.kind === 'test')?.n || 0;
  return Number(route.params.week || route.query.week || calendar.value?.week || 1);
});
const week = computed(() => analysis.value?.perWeek.find(week => week.n === currentWeek.value));
const weekMeta = computed(() => plan.value?.weeks.find(week => week.n === currentWeek.value));
const validRoute = computed(() => {
  if (['welcome', 'login', 'register'].includes(page.value)) return true;
  if (!['today', 'plan', 'analysis', 'archive', 'questionnaire', 'settings'].includes(page.value)) return false;
  if (!week.value) return false;
  return !route.params.day || plan.value.workouts.some(row => row.week === currentWeek.value && row.day === route.params.day);
});
const days = computed(() => {
  if (!weekMeta.value) return [];
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(`${weekMeta.value.dateStart}T00:00:00+08:00`);
    date.setUTCDate(date.getUTCDate() + index);
    const iso = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
    const rows = plan.value.workouts.filter(row => row.date === iso);
    return { date: iso, rows, id: rows[0]?.day, label: dateLabel(iso), weekday: new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: 'Asia/Shanghai' }).format(date).toUpperCase() };
  });
});
const todaySession = computed(() => calendar.value?.day ? { date: calendar.value.date, week: calendar.value.week, day: calendar.value.day } : calendar.value?.nextSession);
const todayRows = computed(() => todaySession.value ? plan.value.workouts.filter(row => row.week === todaySession.value.week && row.day === todaySession.value.day) : []);
const topLifts = rows => ['S', 'B', 'D'].flatMap(code => {
  const candidates = rows.filter(row => row.bucket === 'main' && row.lift === code && row.loadKg !== null && !(row.sets === 1 && row.reps === 3 && row.mode === 'T1.3x3'));
  const row = candidates.sort((a, b) => (b.pct || 0) - (a.pct || 0))[0];
  return row ? [{ code, label: { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT' }[code], load: row.loadKg, pct: (row.pct || 0) * 100 }] : [];
});
const todayLifts = computed(() => topLifts(todayRows.value));
const todayTotals = computed(() => Object.fromEntries(['main', 'sbdVar', 'nonSbdVar', 'accessory'].map(role => [role, todayRows.value.filter(row => row.bucket === role).reduce((sum, row) => sum + row.sets, 0)])));
const todaySetCount = computed(() => Object.values(todayTotals.value).reduce((a, b) => a + b, 0));
const leaves = computed(() => analysis.value.leafOrder.map(id => {
  const values = week.value.leaves[id];
  const range = analysis.value.ranges.leaf[id];
  const verdict = range.mev === null || range.mrv === null ? 'No separate reference' : range.scope === 'group_back' ? 'Group-scope reference' : values.d < range.mev ? 'Below MEV' : values.d > range.mrv ? 'Above MRV' : 'Within reference range';
  return { id, name: geometry.value.leaves[id].en, weighted: values.w, raw: values.raw, heat: values.heat, direct: values.d, primaryWeighted: values.primaryWeighted, secondaryWeighted: values.secondaryWeighted, mev: range.mev, mrv: range.mrv, scope: range.scope, verdict };
}));
const display = value => value === null || value === undefined ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 });
const DELOAD_NOTE = 'Deload week: lighter loads, same movements. Nothing is skipped and no date moves.';
const needsMicroPlates = rows => rows.some(row => row.segments.some(segment => segment.load !== null && segment.load % 2.5 !== 0));
const blockType = blockId => (plan.value?.blocks.find(block => block.id === blockId)?.cycleType || 'custom').toLowerCase();
const planView = computed(() => route.params.day ? 'day' : route.params.week ? 'week' : route.params.blockId ? 'block' : 'cycle');
const blockMeta = computed(() => plan.value?.blocks.find(block => block.id === route.params.blockId));
const blockWeeks = computed(() => blockMeta.value ? plan.value.weeks.filter(item => item.blockId === blockMeta.value.id) : []);
const blockPerWeek = computed(() => analysis.value ? blockWeeks.value.map(item => analysis.value.perWeek.find(row => row.n === item.n)).filter(Boolean) : []);
const blockTonnage = computed(() => blockWeeks.value.reduce((sum, item) => sum + (item.tonnageKg || 0), 0));
const blockTopPct = computed(() => Math.max(0, ...blockPerWeek.value.map(row => row.topPct || 0), 0));
const weekGpp = computed(() => (plan.value?.gpp || []).filter(item => item.week === currentWeek.value));
const weekCardio = computed(() => (plan.value?.runPlan || []).filter(item => item.week === currentWeek.value));
const conditioningWeek = computed(() => weekCardio.value.reduce((sum, item) => sum + (item.duration_min || 0), 0));
const conditioningBars = computed(() => plan.value ? plan.value.weeks.map(item => ({
  n: item.n,
  kind: item.kind,
  minutes: (plan.value.runPlan || []).filter(row => row.week === item.n).reduce((sum, row) => sum + (row.duration_min || 0), 0),
})) : []);
function dateLabel(value) { return new Intl.DateTimeFormat('en-US', { month: 'short', day: '2-digit', timeZone: 'Asia/Shanghai' }).format(new Date(`${value}T00:00:00+08:00`)).toUpperCase(); }
const ACRONYMS = new Set(['SBD', 'AMRAP', 'RPE', 'GPP', 'SSB', 'RDL', 'EMOM', 'TOP', 'SET', 'W13', '5KM']);
function titleCase(text) {
  return String(text || '').split(' ').map(word => {
    const clean = word.replace(/[^A-Za-z0-9]/g, '');
    if (clean && ACRONYMS.has(clean.toUpperCase())) return word;
    return word ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase() : word;
  }).join(' ');
}
function selectWeek(number) {
  if (number < 1 || number > plan.value.weeks.length) return;
  if (page.value === 'plan') router.push(`/plan/week/${number}`);
  else router.replace({ path: route.path, query: { week: number } });
}
async function get(path) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Server request failed (${response.status}). Your saved data has not been changed.`);
  return response.json();
}
async function refresh() {
  loading.value = true;
  error.value = '';
  try {
    const result = await Promise.all(['/api/plan', `/api/analysis?mode=${mode.value}`, '/api/geometry', '/api/today', '/api/cycle', '/api/log', '/api/performance'].map(get));
    [plan.value, analysis.value, geometry.value, calendar.value, cycles.value] = result;
    logs.value = result[5].logs;
    performance.value = result[6];
    prescriptionInfo.value = await get(`/api/prescription?${new URLSearchParams({ cycle_id: plan.value.meta.planId })}`);
  } catch (failure) { error.value = failure.message || 'The server is unavailable. Reconnect and try again.'; }
  finally { loading.value = false; }
}
async function changeMode(value) {
  if (loading.value || isPublic.value) return;
  mode.value = value;
  await refresh();
}
async function loadSession() {
  try { session.value = await get('/api/session'); }
  catch { session.value = { authenticated: false, gate: true }; }
  finally { authReady.value = true; }
}
async function ensureData() {
  if (plan.value || loading.value) return;
  await refresh();
  await nextTick();
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches && document.querySelector('.main-loads')) {
    animate('.main-loads', { transform: ['translateY(6px)', 'translateY(0)'] }, { duration: .24, easing: 'ease-out' });
  }
}
async function onAuthed(account) {
  await loadSession();
  const next = typeof account.next === 'string' && account.next.startsWith('/') ? account.next : '/today';
  router.replace(next);
}
async function logout() {
  try { await fetch('/api/logout', { method: 'POST' }); } catch { /* session cleared client-side regardless */ }
  plan.value = null;
  error.value = '';
  router.replace('/');
  await loadSession();
}
onMounted(loadSession);
watch([page, authReady, () => session.value?.authenticated], async () => {
  if (!authReady.value) return;
  const authed = !!session.value?.authenticated;
  if (!isPublic.value && !authed) {
    router.replace({ path: '/login', query: { next: route.fullPath } });
    return;
  }
  if ((page.value === 'login' || page.value === 'register') && authed && session.value?.gate) {
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/today';
    router.replace(next);
    return;
  }
  if (!isPublic.value && authed) await ensureData();
}, { immediate: true });
watch(() => route.path, () => {
  const titles = { welcome: 'Roast Raw — Powerlifting training journal', login: 'Sign in — Roast Raw', register: 'Create account — Roast Raw', today: 'Today — Roast Raw' };
  document.title = titles[page.value] || `${page.value.charAt(0).toUpperCase() + page.value.slice(1)} — Roast Raw`;
}, { immediate: true });
watch(page, value => { if (!isPublic.value && value !== 'analysis' && mode.value !== 'plan') changeMode('plan'); });
watch([() => route.fullPath, loading], async () => {
  if (loading.value || error.value || !validRoute.value || !route.params.day) return;
  await nextTick();
  const target = document.getElementById(`day-${currentWeek.value}-${route.params.day}`);
  if (!target) return;
  target.focus({ preventScroll: true });
  scrollTo(0, target.getBoundingClientRect().top + scrollY - 16);
}, { flush: 'post' });
</script>

<template>
  <div class="shell">
    <header class="masthead"><RouterLink :to="isPublic ? '/' : '/plan'" class="brand" aria-label="Roast Raw home"><BeanMark class="brand-mark" />Roast Raw</RouterLink><span class="edition">TRAINING JOURNAL / {{ releaseVersion }}</span><template v-if="!isPublic"><RouterLink to="/settings" class="settings-link" aria-label="Settings"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M18.5 5.5l-1.8 1.8M7.3 16.7l-1.8 1.8"/></svg></RouterLink><button type="button" class="settings-link" aria-label="Sign out" @click="logout"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v8"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/></svg></button></template><RouterLink v-else-if="page === 'welcome'" :to="session?.authenticated ? '/plan' : { path: '/login', query: { next: '/plan' } }" class="masthead-cta">MyPlan</RouterLink></header>
    <nav v-if="!isPublic" class="primary-nav" aria-label="Primary"><RouterLink to="/plan">PLAN</RouterLink><RouterLink to="/analysis">ANALYSIS</RouterLink><RouterLink to="/archive">ARCHIVE</RouterLink><RouterLink to="/questionnaire">OUTLOOK</RouterLink></nav>
    <main :aria-busy="loading">
      <WelcomeView v-if="page === 'welcome'" />
      <LoginView v-else-if="page === 'login'" :next="typeof route.query.next === 'string' ? route.query.next : ''" @authed="onAuthed" />
      <RegisterView v-else-if="page === 'register'" @authed="onAuthed" />
      <div v-else-if="loading" class="empty-state" role="status"><h1>Reading the plan.</h1><p>Loading your training data from the server.</p></div>
      <div v-else-if="error" class="error-panel" role="alert"><h2>Connection interrupted.</h2><p>{{ error }}</p><p>No offline copy is used for statistics.</p><button @click="refresh">Retry connection</button></div>
      <div v-else-if="!validRoute" class="empty-state"><h1>Not in this plan.</h1><p>This page, block, week or day does not exist.</p><RouterLink to="/plan" class="inline-link">Return to the plan</RouterLink></div>
      <template v-else>
        <div v-if="page === 'today'" class="workspace" data-testid="today">
          <div>
            <div class="eyebrow">TODAY · {{ dateLabel(calendar.date) }} · BEIJING TIME</div>
            <h1>{{ calendar.status === 'training' ? todayLifts.map(lift => lift.label.charAt(0) + lift.label.slice(1).toLowerCase()).join(' · ') || 'Training day.' : calendar.status === 'ended' ? 'Cycle complete.' : 'Rest & recover.' }}</h1>
            <p class="hero-subtitle">{{ calendar.status === 'training' ? plan.weeks.find(week => week.n === calendar.week).blockName : calendar.status === 'upcoming' ? 'A stronger cycle starts here.' : 'The calendar stays. Recovery matters.' }}</p>
            <p v-if="calendar.status !== 'training'" class="notice">{{ calendar.status === 'upcoming' ? `Your plan starts ${dateLabel(plan.meta.startDate)}. There is no session today.` : calendar.status === 'ended' ? 'The scheduled cycle has ended. No training dates have been moved.' : 'No session scheduled today. Missed sessions do not move the calendar.' }}</p>
            <p v-if="calendar.status === 'training' && plan.weeks.find(item => item.n === calendar.week)?.kind === 'deload'" class="notice">{{ DELOAD_NOTE }}</p>
            <CyclePrestart v-if="calendar.status === 'upcoming'" :plan="plan" :date="calendar.date" />
            <template v-if="todaySession">
              <div class="badges"><span class="badge">{{ calendar.day ? 'TODAY’S SESSION' : 'NEXT SESSION · PREVIEW' }}</span><span class="badge">W{{ String(todaySession.week).padStart(2, '0') }} · DAY {{ todaySession.day }} · {{ dateLabel(todaySession.date) }}</span></div>
              <section v-if="todayLifts.length" class="main-loads" :style="{ '--columns': todayLifts.length }" aria-label="Main lift loads">
                <div v-for="lift in todayLifts" :key="lift.code" class="main-load"><div class="section-label">{{ lift.label }}</div><div class="load-value"><b>{{ display(lift.load) }}</b><small>kg</small></div><div class="intensity-label"><strong>{{ display(lift.pct) }}%</strong><span>{{ lift.pct >= 95 ? 'TEST' : lift.pct >= 85 ? 'HIGH' : lift.pct >= 75 ? 'BUILD' : 'BASE' }}</span></div><div class="intensity-track"><span v-for="mark in [75,85,95]" :key="mark" :style="{ left: `${(mark - 50) / 60 * 100}%` }"></span><i :style="{ left: `${Math.min(100, Math.max(0, (lift.pct - 50) / 60 * 100))}%` }"></i></div><div class="intensity-scale"><span v-for="mark in [75,85,95]" :key="mark" :style="{ left: `${(mark - 50) / 60 * 100}%` }">{{ mark }}</span></div></div>
                <div class="load-total"><small>TOTAL LOAD<br>main work + variations</small><strong>{{ display(todayRows.reduce((sum, row) => sum + row.tonnageKg, 0)) }}<small> kg</small></strong></div>
              </section>
              <section class="day-capacity" aria-label="Session capacity"><header><span class="section-label">SESSION CAPACITY · PLANNED</span><strong>{{ todaySetCount }} SETS</strong></header><div class="capacity-track"><i v-for="(sets, index) in [todayTotals.main, todayTotals.sbdVar + todayTotals.nonSbdVar, todayTotals.accessory]" :key="index" :style="{ width: `${sets / Math.max(todaySetCount, 1) * 100}%` }"></i></div><div class="capacity-key"><span>MAIN {{ todayTotals.main }}</span><span>VAR {{ todayTotals.sbdVar + todayTotals.nonSbdVar }}</span><span>ACCESSORY {{ todayTotals.accessory }}</span></div></section>
              <CycleStrip :weeks="plan.weeks" :blocks="plan.blocks" :current="todaySession.week" />
              <RouterLink :to="`/plan/week/${todaySession.week}/day/${todaySession.day}`" class="inline-link">Open the scheduled day →</RouterLink>
              <DailyRecord :cycle-id="plan.meta.planId" :date="todaySession.date" :session-id="`${todaySession.week}|${todaySession.day}`" @saved="refreshPrescription" />
              <details class="gear"><summary>GEAR <span class="chip">{{ needsMicroPlates(todayRows) ? 'MICRO PLATES' : 'SESSION SETUP' }}</span><span v-if="plan.meta.profile.bar_kg" class="chip">{{ display(plan.meta.profile.bar_kg) }} KG BAR</span></summary><p>{{ needsMicroPlates(todayRows) ? 'Some prescribed loads need micro plates. Prepare equipment before the session; loads remain unchanged.' : 'Standard plates cover these prescribed loads. Prepare equipment before the session.' }}</p><p v-if="plan.meta.profile.bar_kg">Plan bar reference: {{ display(plan.meta.profile.bar_kg) }} kg. {{ plan.meta.profile.collars ? 'Collars included in the plan setup.' : 'Collars are not included in the plan load reference.' }}</p><p v-if="todayRows.some(row => prescriptionInfo?.systemLoads[row.week + '|' + row.day + '|' + row.seq])">Pull-up and dip loads include bodyweight. Check the dated bodyweight reading before choosing assistance or added weight.</p></details>
              <WarmupSuggestions :entries="plan.warmups?.[todaySession.date] || []" />
              <ExerciseRows :rows="todayRows" :cycle-id="plan.meta.planId" :logs="logs" :system-loads="prescriptionInfo?.systemLoads || {}" @saved="savedLog" />
              <ShareButton :plan="plan" :logs="logs" :default-date="todaySession.date" />
            </template>
          </div>
          <aside><MuscleMap compact :geometry="geometry" :leaves="leaves" :heat-scale="analysis.heatScale" :week-number="currentWeek" :week-count="plan.weeks.length" @week="selectWeek" /><WeekCapacity :week="week" :ranges="analysis.ranges" /></aside>
        </div>
                <template v-else-if="page === 'plan'">
          <template v-if="planView === 'cycle'">
            <div class="eyebrow">{{ plan.meta.weeks }} WEEKS · {{ plan.meta.sessions }} SESSIONS · FIXED CALENDAR</div><h1 class="plan-title">The plan.</h1><p class="hero-subtitle">{{ dateLabel(plan.meta.startDate) }} — {{ dateLabel(plan.meta.endDate) }}</p>
            <div class="plan-metrics"><div class="metric"><span class="section-label">START</span><strong>{{ dateLabel(plan.meta.startDate) }}</strong><small>{{ plan.meta.startDate.slice(0, 4) }} · {{ plan.meta.weeks }} WEEKS</small></div><div class="metric"><span class="section-label">TEST DAY</span><strong>{{ plan.testPlan?.dates?.sbd ? dateLabel(plan.testPlan.dates.sbd) : 'Not set' }}</strong><small>{{ plan.testPlan?.dates?.sbd ? `W${String(plan.weeks.find(w => w.kind === 'test')?.n || 0).padStart(2, '0')} · SBD` : 'Add a date in outlook' }}</small></div><div class="metric"><span class="section-label">CYCLE TONNAGE</span><strong>{{ display(analysis.cycle.tonnageKg / 1000) }} t</strong><small>{{ analysis.cycle.auxSets }} AUX SETS</small></div></div>
            <LoadProfile :weeks="plan.weeks" :blocks="plan.blocks" :per-week="analysis.perWeek" :test-date="plan.testPlan?.dates?.sbd" />
            <div class="section-head"><div class="eyebrow">CYCLE MAP</div><p class="annotation">Each square is one week. Pick a square to open that week; colour is the block.</p></div>
            <CycleStrip :weeks="plan.weeks" :blocks="plan.blocks" :current="Number(calendar?.week || 1)" />
            <p class="cycle-open"><RouterLink v-if="calendar?.week" :to="`/plan/week/${calendar.week}`" class="inline-link">Open week {{ String(calendar.week).padStart(2, '0') }}</RouterLink></p><nav class="block-index" aria-label="Blocks"><RouterLink v-for="block in plan.blocks" :key="block.id" :to="`/plan/block/${block.id}`"><b>{{ block.id }}</b><span>{{ block.nameEn }}</span></RouterLink></nav>
          </template>
          <template v-else-if="planView === 'block'">
            <div class="eyebrow">BLOCK {{ blockMeta?.id }} · {{ (blockMeta?.cycleType || 'custom').toUpperCase() }}</div><h1 class="plan-title">{{ blockMeta?.nameEn }}</h1><p class="hero-subtitle">W{{ String(blockWeeks[0]?.n || 0).padStart(2, '0') }} — W{{ String(blockWeeks.at(-1)?.n || 0).padStart(2, '0') }} · {{ blockWeeks.length }} WEEKS</p>
            <div class="plan-metrics"><div class="metric"><span class="section-label">SESSIONS</span><strong>{{ blockWeeks.reduce((sum, item) => sum + (item.sessions || 0), 0) }}</strong><small>ACROSS THIS BLOCK</small></div><div class="metric"><span class="section-label">BLOCK TONNAGE</span><strong>{{ display(blockTonnage / 1000) }} t</strong><small>PLANNED WORK</small></div><div class="metric"><span class="section-label">TOP %1RM</span><strong>{{ display(blockTopPct) }}%</strong><small>{{ (blockMeta?.cycleType || 'custom').toUpperCase() }} CEILING</small></div></div>
            <LoadProfile :weeks="blockWeeks" :blocks="plan.blocks" :per-week="blockPerWeek" :test-date="plan.testPlan?.dates?.sbd" />
            <div class="section-head"><div class="eyebrow">WEEKS IN THIS BLOCK</div><p class="annotation">Open any week to see its seven days.</p></div>
            <ul class="block-weeks"><li v-for="week in blockWeeks" :key="week.n"><RouterLink :to="`/plan/week/${week.n}`" :class="week.kind"><b>W{{ String(week.n).padStart(2, '0') }}</b><span>{{ week.kind.toUpperCase() }}</span><small>{{ display(week.tonnageKg / 1000) }} t · {{ week.sessions }} SESSIONS</small></RouterLink></li></ul>
          </template>
          <template v-else>
            <div class="eyebrow">{{ weekMeta.blockId }} · {{ week.kind.toUpperCase() }} WEEK</div><p class="breadcrumb"><RouterLink to="/plan">Plan</RouterLink> / <RouterLink :to="`/plan/block/${weekMeta.blockId}`">{{ weekMeta.blockId }}</RouterLink> / Week {{ currentWeek }}</p>
            <CycleStrip :weeks="plan.weeks" :blocks="plan.blocks" :current="currentWeek" />
            <div class="workspace"><div>
            <div class="week-header"><span class="week-number">{{ currentWeek }}</span><div><h2>{{ weekMeta.blockName }}</h2><small>{{ week.kind.toUpperCase() }} WEEK</small></div><div class="week-summary"><strong>{{ display(week.tonnageKg / 1000) }} t</strong><small>{{ week.sessions }} SESSIONS</small></div></div>
            <p v-if="weekMeta.kind === 'deload'" class="notice">{{ DELOAD_NOTE }}</p>
            <AttemptBoard v-if="weekMeta.kind === 'test'" :cycle-id="plan.meta.planId" :bar-kg="plan.meta.profile.bar_kg || 20" :collar-pair="plan.meta.profile.collars ? 5 : 0" />
            <div class="top-intensity"><span>TOP %1RM <b>{{ display(week.topPct) }}%</b></span><span>S {{ display(week.topPctByLift.S) }} · B {{ display(week.topPctByLift.B) }} · D {{ display(week.topPctByLift.D) }}</span></div>
            <div v-for="day in days" :id="day.id ? `day-${currentWeek}-${day.id}` : undefined" :key="day.date" :tabindex="route.params.day === day.id ? -1 : undefined" class="plan-day">
              <template v-if="day.rows.length">
                <RouterLink class="day-row" :to="route.params.day === day.id ? `/plan/week/${currentWeek}` : `/plan/week/${currentWeek}/day/${day.id}`" :aria-expanded="route.params.day === day.id"><span class="day-date"><strong>{{ day.label }}</strong>{{ day.weekday }}</span><span class="day-letter">{{ day.id }}</span><span class="day-info"><span v-if="topLifts(day.rows).length" class="top-load"><small>TOP</small><b v-for="lift in topLifts(day.rows)" :key="lift.code">{{ lift.code }} {{ display(lift.load) }}</b></span><span class="day-title">{{ titleCase(plan.days.find(item => item.id === day.id).titleEn) }}</span><span class="day-status">{{ (calendar.sessionStates[`${currentWeek}|${day.id}`] || 'scheduled').toUpperCase() }}</span></span><span class="day-open">{{ route.params.day === day.id ? '−' : '›' }}</span></RouterLink>
                <DailyRecord v-if="route.params.day === day.id" :cycle-id="plan.meta.planId" :date="day.date" :session-id="`${currentWeek}|${day.id}`" @saved="refreshPrescription" />
                <details v-if="route.params.day === day.id" class="gear"><summary>GEAR <span class="chip">{{ needsMicroPlates(day.rows) ? 'MICRO PLATES' : 'SESSION SETUP' }}</span><span v-if="plan.meta.profile.bar_kg" class="chip">{{ display(plan.meta.profile.bar_kg) }} KG BAR</span></summary><p>{{ needsMicroPlates(day.rows) ? 'Prepare micro plates for the prescribed loads.' : 'Standard plates cover these prescribed loads.' }} All loads stay as prescribed; bodyweight movements use dated total system weight when shown.</p></details>
                <WarmupSuggestions v-if="route.params.day === day.id" :entries="plan.warmups?.[day.date] || []" />
                <ExerciseRows v-if="route.params.day === day.id" :rows="day.rows" :cycle-id="plan.meta.planId" :logs="logs" :system-loads="prescriptionInfo?.systemLoads || {}" @saved="savedLog" />
                <ShareButton v-if="route.params.day === day.id" :plan="plan" :logs="logs" :default-date="day.date" />
              </template>
              <div v-else class="rest-row"><span>{{ day.label }} · {{ day.weekday }}</span><span>REST</span></div>
            </div>
            <WeekCapacity :week="week" :ranges="analysis.ranges" />
            <figure class="cond-card" aria-label="Conditioning equivalent minutes"><div class="cond-head"><div><div class="eyebrow">CONDITIONING</div><h3>Equivalent minutes <em>ESTIMATE</em></h3></div><strong>{{ conditioningWeek }}<small> min/wk</small></strong></div><div class="cond-band"><div class="cond-zone"></div><div class="cond-bars"><i v-for="bar in conditioningBars" :key="bar.n" :class="[bar.kind, { on: bar.n === currentWeek }]" :style="{ height: `${Math.min(100, bar.minutes / 60 * 100)}%` }" :title="`Week ${bar.n}: ${bar.minutes} min`"></i></div></div><div class="cond-scale"><span>0</span><span>20</span><span>60</span></div><p class="cond-note">Moderate-intensity equivalent from planned cardio. It is an estimate, not a measured load.</p></figure>
            <details class="gear gpp" data-testid="gpp"><summary>GPP <span class="chip">CARDIO / RECOVERY / WEAK POINT</span></summary><p class="micro-copy">Planned supporting work. These targets are not recorded completion and do not add SBD equivalent sets.</p><p v-if="!weekGpp.length && !weekCardio.length">No supporting work prescribed for this week.</p><article v-for="item in weekGpp" :key="item.item_idx"><h3>{{ item.item || item.domain || 'Supporting work' }}</h3><p>{{ item.rx_text || `${display(item.target_value)} ${item.target_unit || ''}` }}</p><small v-if="item.note">{{ item.note }}</small></article><article v-for="item in weekCardio" :key="item.day"><h3>Cardio · {{ dateLabel(item.date) }} <small v-if="item.optional">OPTIONAL</small></h3><p>{{ item.note }}</p><p v-if="item.duration_min">{{ display(item.duration_min) }} min · {{ item.zone || 'Prescribed effort' }}<template v-if="item.hr_low && item.hr_high"> · HR {{ item.hr_low }}–{{ item.hr_high }}</template></p></article></details>
            </div><aside class="week-aside"><MuscleMap compact :geometry="geometry" :leaves="leaves" :heat-scale="analysis.heatScale" :week-number="currentWeek" :week-count="plan.weeks.length" @week="selectWeek" /></aside></div>
          </template>
        </template>
<template v-else-if="page === 'analysis'">
          <div class="eyebrow">CAPACITY / ANALYSIS · {{ plan.meta.weeks }} WEEKS</div><h1>Every set counts.</h1><p class="hero-subtitle">One plan. Every contribution.</p>
          <div class="map-filters"><button :aria-pressed="mode === 'plan'" @click="changeMode('plan')">Planned</button><button :aria-pressed="mode === 'log'" @click="changeMode('log')">Logged + planned</button></div><p class="annotation">{{ mode === 'plan' ? 'Prescribed sets for the full cycle.' : 'Recorded sets replace their planned rows. Unrecorded rows still use the plan.' }}</p>
          <div class="workspace analysis-workspace">
            <MuscleMap :geometry="geometry" :leaves="leaves" :heat-scale="analysis.heatScale" :week-number="currentWeek" :week-count="plan.weeks.length" @week="selectWeek">
              <template #summary><section class="analysis-summary" data-testid="analysis-summary" aria-label="Selected week summary"><span class="section-label">W{{ String(currentWeek).padStart(2, '0') }} · {{ mode === 'plan' ? 'PLANNED' : 'LOGGED + PLANNED' }}</span><p><strong>{{ week.total }}</strong> raw working sets · <strong>{{ display(week.tonnageKg) }}</strong> kg</p><small>{{ week.dateStart }} — {{ week.dateEnd }} · {{ week.sessions }} sessions</small></section></template>
            </MuscleMap>
            <aside><WeekCapacity :week="week" :ranges="analysis.ranges" /><CapacityBoard :analysis="analysis" :week="week" /></aside>
          </div>
          <TrendView :analysis="analysis" :performance="performance" />
        </template>
        <ArchiveView v-else-if="page === 'archive'" :active-cycle-id="plan.meta.planId" />
        <template v-else-if="page === 'questionnaire'"><QuestionnaireView /><AiOutlook :cycle-id="plan.meta.planId" /></template>
        <template v-else-if="page === 'settings'"><div class="eyebrow">PREFERENCES / SYSTEM</div><h1>The essentials.</h1><div class="empty-state"><h2>Server storage</h2><p>Connected · SQLite · Asia/Shanghai</p><p>{{ plan.schemaVersion }} · {{ plan.meta.weeks }} weeks · {{ plan.meta.sessions }} sessions</p><p>Single-user release {{ releaseVersion }}. Records are saved on the server; prescribed and actual sets stay separate.</p></div><PlanImport /><PrescriptionSettings :cycle-id="plan.meta.planId" @changed="refresh" /></template>
      </template>
    </main>
    <footer class="site-footer"><span>ROAST RAW / TRAIN WITH INTENT</span><RouterLink to="/welcome" class="footer-about">ABOUT</RouterLink><span>{{ releaseVersion }} · LOCAL PREVIEW</span></footer>
  </div>
</template>

<style scoped>
.gear summary { flex-wrap: wrap; }
.analysis-summary { margin: 20px 0; padding: 16px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.analysis-summary p { margin-top: 8px; font-size: 14px; line-height: 1.7; }
.analysis-summary small { color: var(--muted); font-size: 11px; }
.gpp article { padding: 16px 0; border-top: 1px solid var(--line-soft); overflow-wrap: anywhere; }
.gpp h3 { font-size: 16px; }
.gpp small { color: var(--muted); line-height: 1.6; }
</style>
