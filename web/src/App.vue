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
const loading = ref(true);
const mode = ref('plan');
const theme = ref(localStorage.getItem('roastraw-theme') === 'dark' ? 'dark' : 'light');
watch(theme, value => {
  document.documentElement.dataset.theme = value;
  document.querySelector('meta[name="theme-color"]').content = value === 'dark' ? '#07090D' : '#F4F7FA';
  localStorage.setItem('roastraw-theme', value);
}, { immediate: true });
const page = computed(() => route.path.startsWith('/plan') ? 'plan' : route.path === '/archive' || route.path.startsWith('/archive/') ? 'archive' : ['/', '/today'].includes(route.path) ? 'today' : route.path.slice(1));
const currentWeek = computed(() => {
  if (!plan.value) return 1;
  if (route.params.blockId) return plan.value.weeks.find(week => week.blockId === route.params.blockId)?.n || 0;
  if (route.path === '/plan/test') return plan.value.weeks.find(week => week.kind === 'test')?.n || 0;
  return Number(route.params.week || route.query.week || calendar.value?.week || 1);
});
const week = computed(() => analysis.value?.perWeek.find(week => week.n === currentWeek.value));
const weekMeta = computed(() => plan.value?.weeks.find(week => week.n === currentWeek.value));
const validRoute = computed(() => {
  if (!['today', 'plan', 'analysis', 'archive', 'settings'].includes(page.value)) return false;
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
const weekGpp = computed(() => (plan.value?.gpp || []).filter(item => item.week === currentWeek.value));
const weekCardio = computed(() => (plan.value?.runPlan || []).filter(item => item.week === currentWeek.value));
function dateLabel(value) { return new Intl.DateTimeFormat('en-US', { month: 'short', day: '2-digit', timeZone: 'Asia/Shanghai' }).format(new Date(`${value}T00:00:00+08:00`)).toUpperCase(); }
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
  if (loading.value) return;
  mode.value = value;
  await refresh();
}
onMounted(async () => {
  await refresh();
  await nextTick();
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches && document.querySelector('.main-loads')) {
    animate('.main-loads', { transform: ['translateY(6px)', 'translateY(0)'] }, { duration: .24, easing: 'ease-out' });
  }
});
watch(() => route.path, () => { document.title = `${page.value === 'today' ? 'Today' : page.value.charAt(0).toUpperCase() + page.value.slice(1)} — Roast Raw`; }, { immediate: true });
watch(page, value => { if (value !== 'analysis' && mode.value !== 'plan') changeMode('plan'); });
watch([() => route.fullPath, loading], async () => {
  if (loading.value || error.value || !validRoute.value || !route.params.day) return;
  await nextTick();
  const target = document.getElementById(`day-${currentWeek.value}-${route.params.day}`);
  if (!target) return;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: 'start', behavior: 'instant' });
}, { flush: 'post' });
</script>

<template>
  <div class="shell">
    <header class="masthead"><RouterLink to="/" class="brand" aria-label="Roast Raw, Today">Roast Raw</RouterLink><span class="edition">TRAINING JOURNAL / {{ releaseVersion }}</span><button class="theme-toggle" aria-label="Toggle color theme" @click="theme = theme === 'light' ? 'dark' : 'light'">{{ theme === 'light' ? 'DARK' : 'LIGHT' }}</button></header>
    <nav class="primary-nav" aria-label="Primary"><RouterLink to="/plan">PLAN</RouterLink><RouterLink to="/analysis">ANALYSIS</RouterLink><RouterLink to="/archive">ARCHIVE</RouterLink><RouterLink to="/settings">SETTINGS</RouterLink></nav>
    <main :aria-busy="loading">
      <div v-if="loading" class="empty-state" role="status"><h1>Reading the plan.</h1><p>Loading your training data from the server.</p></div>
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
            <template v-if="todaySession">
              <div class="badges"><span class="badge">{{ calendar.day ? 'TODAY’S SESSION' : 'NEXT SESSION · PREVIEW' }}</span><span class="badge">W{{ String(todaySession.week).padStart(2, '0') }} · DAY {{ todaySession.day }} · {{ dateLabel(todaySession.date) }}</span></div>
              <section v-if="todayLifts.length" class="main-loads" :style="{ '--columns': todayLifts.length }" aria-label="Main lift loads">
                <div v-for="lift in todayLifts" :key="lift.code" class="main-load"><div class="section-label">{{ lift.label }}</div><div class="load-value"><b>{{ display(lift.load) }}</b><small>kg</small></div><div class="intensity-label"><strong>{{ display(lift.pct) }}%</strong><span>{{ lift.pct >= 95 ? 'TEST' : lift.pct >= 85 ? 'HIGH' : lift.pct >= 75 ? 'BUILD' : 'BASE' }}</span></div><div class="intensity-track"><span v-for="mark in [75,85,95]" :key="mark" :style="{ left: `${(mark - 50) / 60 * 100}%` }"></span><i :style="{ left: `${Math.min(100, Math.max(0, (lift.pct - 50) / 60 * 100))}%` }"></i></div><div class="intensity-scale"><span v-for="mark in [75,85,95]" :key="mark" :style="{ left: `${(mark - 50) / 60 * 100}%` }">{{ mark }}</span></div></div>
                <div class="load-total"><small>TOTAL LOAD<br>main work + variations</small><strong>{{ display(todayRows.reduce((sum, row) => sum + row.tonnageKg, 0)) }}<small> kg</small></strong></div>
              </section>
              <section class="day-capacity" aria-label="Session capacity"><header><span class="section-label">SESSION CAPACITY · PLANNED</span><strong>{{ todaySetCount }} SETS</strong></header><div class="capacity-track"><i v-for="(sets, index) in [todayTotals.main, todayTotals.sbdVar + todayTotals.nonSbdVar, todayTotals.accessory]" :key="index" :style="{ width: `${sets / Math.max(todaySetCount, 1) * 100}%` }"></i></div><div class="capacity-key"><span>MAIN {{ todayTotals.main }}</span><span>VAR {{ todayTotals.sbdVar + todayTotals.nonSbdVar }}</span><span>ACCESSORY {{ todayTotals.accessory }}</span></div></section>
              <details class="gear"><summary>GEAR <span class="chip">{{ needsMicroPlates(todayRows) ? 'MICRO PLATES' : 'SESSION SETUP' }}</span><span v-if="plan.meta.profile.bar_kg" class="chip">{{ display(plan.meta.profile.bar_kg) }} KG BAR</span></summary><p>{{ needsMicroPlates(todayRows) ? 'Some prescribed loads need micro plates. Prepare equipment before the session; loads remain unchanged.' : 'Standard plates cover these prescribed loads. Prepare equipment before the session.' }}</p><p v-if="plan.meta.profile.bar_kg">Plan bar reference: {{ display(plan.meta.profile.bar_kg) }} kg. {{ plan.meta.profile.collars ? 'Collars included in the plan setup.' : 'Collars are not included in the plan load reference.' }}</p><p v-if="todayRows.some(row => prescriptionInfo?.systemLoads[row.week + '|' + row.day + '|' + row.seq])">Pull-up and dip loads include bodyweight. Check the dated bodyweight reading before choosing assistance or added weight.</p></details>
              <RouterLink :to="`/plan/week/${todaySession.week}/day/${todaySession.day}`" class="inline-link">Open the scheduled day →</RouterLink>
              <WarmupSuggestions :entries="plan.warmups?.[todaySession.date] || []" />
              <ExerciseRows :rows="todayRows" :cycle-id="plan.meta.planId" :logs="logs" :system-loads="prescriptionInfo?.systemLoads || {}" @saved="savedLog" />
              <DailyRecord :cycle-id="plan.meta.planId" :date="todaySession.date" :session-id="`${todaySession.week}|${todaySession.day}`" @saved="refreshPrescription" />
            </template>
          </div>
          <aside><MuscleMap compact :geometry="geometry" :leaves="leaves" :heat-scale="analysis.heatScale" :week-number="currentWeek" :week-count="plan.weeks.length" @week="selectWeek" /><WeekCapacity :week="week" :ranges="analysis.ranges" /></aside>
        </div>
        <template v-else-if="page === 'plan'">
          <div class="eyebrow">{{ plan.meta.weeks }} WEEKS · {{ plan.meta.sessions }} SESSIONS · FIXED CALENDAR</div><h1>The plan.</h1><p class="hero-subtitle">{{ dateLabel(plan.meta.startDate) }} — {{ dateLabel(plan.meta.endDate) }}</p>
          <div class="plan-metrics"><div class="metric"><span class="section-label">START</span><strong>{{ plan.meta.startDate }}</strong></div><div class="metric"><span class="section-label">TEST DAY</span><strong>{{ plan.testPlan?.dates?.sbd || 'Not scheduled' }}</strong></div><div class="metric"><span class="section-label">CYCLE TONNAGE</span><strong>{{ display(analysis.cycle.tonnageKg / 1000) }} t</strong><small>{{ analysis.cycle.auxSets }} AUX SETS</small></div></div>
          <div class="workspace">
            <div>
              <nav class="block-nav" aria-label="Plan blocks"><RouterLink v-for="block in plan.blocks" :key="block.id" :to="`/plan/block/${block.id}`" :class="{ active: week.blockId === block.id }"><span>{{ block.id }} · {{ block.nameEn }}</span><small>W{{ String(plan.weeks.find(w => w.blockId === block.id)?.n).padStart(2, '0') }} — W{{ String(plan.weeks.filter(w => w.blockId === block.id).at(-1)?.n).padStart(2, '0') }}</small></RouterLink></nav>
              <div class="week-stepper"><button aria-label="Previous plan week" :disabled="currentWeek <= 1" @click="selectWeek(currentWeek-1)">‹</button><strong>WEEK {{ String(currentWeek).padStart(2, '0') }}</strong><button aria-label="Next plan week" :disabled="currentWeek >= plan.weeks.length" @click="selectWeek(currentWeek+1)">›</button></div>
              <div class="week-progress" aria-hidden="true"><i v-for="item in plan.weeks" :key="item.n" :class="{ active: item.n === currentWeek, deload: item.kind === 'deload' }"></i></div>
              <nav class="week-rail" aria-label="Weeks in selected block"><RouterLink v-for="item in plan.weeks.filter(w => w.blockId === week.blockId)" :key="item.n" :to="`/plan/week/${item.n}`" :class="[item.kind, { active: item.n === currentWeek }]">{{ String(item.n).padStart(2, '0') }}</RouterLink></nav>
              <div class="week-header"><span class="week-number">{{ currentWeek }}</span><div><h2>{{ weekMeta.blockName }}</h2><small>{{ week.kind.toUpperCase() }} WEEK</small></div><div class="week-summary"><strong>{{ display(week.tonnageKg / 1000) }} t</strong><small>{{ week.sessions }} SESSIONS</small></div></div>
              <p v-if="weekMeta.kind === 'deload'" class="notice">{{ DELOAD_NOTE }}</p>
              <div class="top-intensity"><span>TOP %1RM <b>{{ display(week.topPct) }}%</b></span><span>S {{ display(week.topPctByLift.S) }} · B {{ display(week.topPctByLift.B) }} · D {{ display(week.topPctByLift.D) }}</span></div>
              <p class="breadcrumb">Plan / {{ week.blockId }} / Week {{ currentWeek }}<template v-if="route.params.day"> / Day {{ route.params.day }}</template></p>
              <div v-for="day in days" :id="day.id ? `day-${currentWeek}-${day.id}` : undefined" :key="day.date" :tabindex="route.params.day === day.id ? -1 : undefined" class="plan-day">
                <template v-if="day.rows.length">
                  <RouterLink class="day-row" :to="route.params.day === day.id ? `/plan/week/${currentWeek}` : `/plan/week/${currentWeek}/day/${day.id}`" :aria-expanded="route.params.day === day.id"><span class="day-date"><strong>{{ day.label }}</strong>{{ day.weekday }}</span><span class="day-letter">{{ day.id }}</span><span class="day-info"><span class="top-load"><small>TOP</small>{{ topLifts(day.rows).map(lift => `${lift.code} ${display(lift.load)}`).join(' · ') || 'ACCESSORY WORK' }}</span><span class="day-title" style="display:block">{{ plan.days.find(item => item.id === day.id).titleEn }}</span><span class="day-status">{{ (calendar.sessionStates[`${currentWeek}|${day.id}`] || 'scheduled').toUpperCase() }}</span></span><span>{{ route.params.day === day.id ? '−' : '›' }}</span></RouterLink>
                  <details v-if="route.params.day === day.id" class="gear"><summary>GEAR <span class="chip">{{ needsMicroPlates(day.rows) ? 'MICRO PLATES' : 'SESSION SETUP' }}</span><span v-if="plan.meta.profile.bar_kg" class="chip">{{ display(plan.meta.profile.bar_kg) }} KG BAR</span></summary><p>{{ needsMicroPlates(day.rows) ? 'Prepare micro plates for the prescribed loads.' : 'Standard plates cover these prescribed loads.' }} All loads stay as prescribed; bodyweight movements use dated total system weight when shown.</p></details>
                  <WarmupSuggestions v-if="route.params.day === day.id" :entries="plan.warmups?.[day.date] || []" />
                  <ExerciseRows v-if="route.params.day === day.id" :rows="day.rows" :cycle-id="plan.meta.planId" :logs="logs" :system-loads="prescriptionInfo?.systemLoads || {}" @saved="savedLog" />
                  <DailyRecord v-if="route.params.day === day.id" :cycle-id="plan.meta.planId" :date="day.date" :session-id="`${currentWeek}|${day.id}`" @saved="refreshPrescription" />
                </template>
                <div v-else class="rest-row"><span>{{ day.label }} · {{ day.weekday }}</span><span>REST</span></div>
              </div>
              <WeekCapacity :week="week" :ranges="analysis.ranges" />
              <details class="gear gpp" data-testid="gpp"><summary>GPP <span class="chip">CARDIO / RECOVERY / WEAK POINT</span></summary><p class="micro-copy">Planned supporting work. These targets are not recorded completion and do not add SBD equivalent sets.</p><p v-if="!weekGpp.length && !weekCardio.length">No supporting work prescribed for this week.</p><article v-for="item in weekGpp" :key="item.item_idx"><h3>{{ item.item || item.domain || 'Supporting work' }}</h3><p>{{ item.rx_text || `${display(item.target_value)} ${item.target_unit || ''}` }}</p><small v-if="item.note">{{ item.note }}</small></article><article v-for="item in weekCardio" :key="item.day"><h3>Cardio · {{ dateLabel(item.date) }} <small v-if="item.optional">OPTIONAL</small></h3><p>{{ item.note }}</p><p v-if="item.duration_min">{{ display(item.duration_min) }} min · {{ item.zone || 'Prescribed effort' }}<template v-if="item.hr_low && item.hr_high"> · HR {{ item.hr_low }}–{{ item.hr_high }}</template></p></article></details>
            </div>
            <aside><MuscleMap compact :geometry="geometry" :leaves="leaves" :heat-scale="analysis.heatScale" :week-number="currentWeek" :week-count="plan.weeks.length" @week="selectWeek" /></aside>
          </div>
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
        <template v-else-if="page === 'settings'"><div class="eyebrow">PREFERENCES / SYSTEM</div><h1>The essentials.</h1><div class="empty-state"><h2>Appearance</h2><p>Light by default. Choose the contrast that suits your session.</p><button class="inline-link" @click="theme = theme === 'light' ? 'dark' : 'light'">Use {{ theme === 'light' ? 'dark' : 'light' }} theme</button></div><div class="empty-state"><h2>Server storage</h2><p>Connected · SQLite · Asia/Shanghai</p><p>{{ plan.schemaVersion }} · {{ plan.meta.weeks }} weeks · {{ plan.meta.sessions }} sessions</p><p>Single-user release {{ releaseVersion }}. Records are saved on the server; prescribed and actual sets stay separate.</p></div><PrescriptionSettings :cycle-id="plan.meta.planId" @changed="refresh" /></template>
      </template>
    </main>
    <footer class="site-footer"><span>ROAST RAW / TRAIN WITH INTENT</span><span>{{ releaseVersion }} · LOCAL PREVIEW</span></footer>
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
