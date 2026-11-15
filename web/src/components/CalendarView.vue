<script setup>
// Calendar-first projection: week / month / agenda over the same session records.
// Nothing here writes: the plan and its logs are read from /api/calendar and shown.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';

const VIEWS = [
  { id: 'week', label: 'Week' },
  { id: 'month', label: 'Month' },
  { id: 'agenda', label: 'Agenda' },
];
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const pad = value => String(value).padStart(2, '0');
const iso = date => `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
const parse = value => { const [y, m, d] = value.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)); };
const addDays = (value, count) => { const date = parse(value); date.setUTCDate(date.getUTCDate() + count); return iso(date); };
const mondayOf = value => { const date = parse(value); const shift = (date.getUTCDay() + 6) % 7; return addDays(value, -shift); };
const monthStart = value => `${value.slice(0, 7)}-01`;
const monthEnd = value => { const date = parse(monthStart(value)); date.setUTCMonth(date.getUTCMonth() + 1); return iso(date); };

const view = ref('week');
const anchor = ref(new Date().toISOString().slice(0, 10));
const selected = ref(anchor.value);
const payload = ref(null);
const loading = ref(false);
const error = ref('');
const today = ref(anchor.value);
let controller = null;
let primed = false;

const range = computed(() => {
  if (view.value === 'month') {
    const first = mondayOf(monthStart(anchor.value));
    return { from: first, to: addDays(first, 42) };
  }
  if (view.value === 'agenda') return { from: addDays(today.value, -14), to: addDays(today.value, 91) };
  const monday = mondayOf(anchor.value);
  return { from: monday, to: addDays(monday, 7) };
});

const days = computed(() => payload.value?.days || []);
const byDate = computed(() => {
  const map = new Map();
  days.value.forEach(day => {
    if (!map.has(day.date)) map.set(day.date, []);
    map.get(day.date).push(day);
  });
  return map;
});
const weekDays = computed(() => Array.from({ length: 7 }, (_, i) => addDays(range.value.from, i)));
const monthCells = computed(() => Array.from({ length: 42 }, (_, i) => addDays(range.value.from, i)));
const monthLabel = computed(() => new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(parse(monthStart(anchor.value))));
const rangeLabel = computed(() => {
  if (view.value === 'month') return monthLabel.value;
  const formatter = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' });
  return `${formatter.format(parse(range.value.from))} – ${formatter.format(parse(addDays(range.value.to, -1)))}`;
});
const selectedDays = computed(() => byDate.value.get(selected.value) || []);
const agendaDays = computed(() => days.value);
const activeCycleId = ref('');
// A day inside a cycle but without a session is a rest day; a day no cycle spans is blank.
const spans = computed(() => payload.value?.cycles || []);
function inSpan(date) {
  return spans.value.some(span => span.start <= date && date <= span.end);
}

async function loadCycles() {
  try {
    const response = await fetch('/api/cycle');
    if (response.ok) activeCycleId.value = (await response.json()).active_cycle_id || '';
  } catch { /* the calendar still renders; archived/open links fall back to VAULT */ }
}

function shift(step) {
  if (view.value === 'month') anchor.value = addDays(monthStart(anchor.value), step * 31).slice(0, 8) + '01';
  else if (view.value === 'agenda') anchor.value = addDays(anchor.value, step * 14);
  else anchor.value = addDays(anchor.value, step * 7);
}
async function load() {
  loading.value = true;
  error.value = '';
  controller?.abort();
  controller = new AbortController();
  try {
    const query = new URLSearchParams(range.value);
    const response = await fetch(`/api/calendar?${query}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`Calendar answered ${response.status}`);
    payload.value = await response.json();
    today.value = payload.value.today || today.value;
    if (!primed && payload.value.today) {
      // The server owns the Beijing date: start the calendar there, not on the browser clock.
      primed = true;
      if (payload.value.today !== anchor.value) { anchor.value = payload.value.today; selected.value = payload.value.today; return; }
    }
    primed = true;
    if (!payload.value.days.some(day => day.date === selected.value)) {
      const nearest = payload.value.days
        .map(day => day.date)
        .sort((a, b) => Math.abs(parse(a) - parse(today.value)) - Math.abs(parse(b) - parse(today.value)))[0];
      selected.value = nearest || today.value;
    }
  } catch (cause) {
    if (cause.name !== 'AbortError') { error.value = 'The calendar could not be loaded. Check the connection and try again.'; payload.value = null; }
  } finally { loading.value = false; }
}
function openDay(date) { selected.value = date; }
function statusLabel(day) {
  return { planned: 'Planned', completed: 'Completed', skipped: 'Skipped', missed: 'Missed' }[day.status] || day.status;
}
function mainNames(day, limit = 2) {
  return (day.rows || []).filter(row => row.bucket === 'main').slice(0, limit).map(row => row.movement);
}
onMounted(() => { loadCycles(); load(); });
watch([anchor, view], load);
onBeforeUnmount(() => controller?.abort());
</script>

<template>
  <section class="cal" data-testid="calendar" aria-label="Training calendar">
    <header class="cal-head">
      <div>
        <div class="eyebrow">RR / 05 · CALENDAR — EVERY CYCLE, ONE PROJECTION</div>
        <h1>Training calendar.</h1>
        <p class="cal-deck">Every session the ledger holds, in one date range. Read-only here: open a session to log or review it.</p>
      </div>
      <div class="cal-controls">
        <div class="cal-nav">
          <button type="button" class="quiet-button" :aria-label="`Previous ${view}`" @click="shift(-1)">‹</button>
          <button type="button" class="quiet-button" data-testid="cal-today" @click="anchor = today; selected = today; load()">Today</button>
          <button type="button" class="quiet-button" :aria-label="`Next ${view}`" @click="shift(1)">›</button>
        </div>
        <div class="cal-views" role="tablist" aria-label="Calendar view">
          <button v-for="entry in VIEWS" :key="entry.id" type="button" role="tab" :aria-selected="view === entry.id" :class="{ on: view === entry.id }" :data-testid="`cal-view-${entry.id}`" @click="view = entry.id">{{ entry.label }}</button>
        </div>
        <p class="cal-range" data-testid="cal-range">{{ rangeLabel }}</p>
      </div>
    </header>

    <p v-if="error" class="cal-error" role="alert" data-testid="cal-error">{{ error }} <button type="button" class="quiet-button" @click="load">Retry</button></p>
    <p v-else-if="loading" class="cal-loading" role="status">Loading the range…</p>

    <!-- Week: seven columns on a desk, one column per day on a phone. -->
    <div v-if="!error && view === 'week'" class="cal-week" data-testid="cal-week">
      <article v-for="date in weekDays" :key="date" class="cal-col" :class="{ 'is-today': date === today, 'is-selected': date === selected }">
        <header>
          <span>{{ WEEKDAYS[(parse(date).getUTCDay() + 6) % 7] }}</span>
          <b>{{ date.slice(8) }}</b>
        </header>
        <p v-if="!byDate.get(date)" class="cal-rest" :class="{ blank: !inSpan(date) }">{{ inSpan(date) ? 'Rest' : '' }}</p>
        <button v-for="day in byDate.get(date)" :key="`${day.cycleId}-${day.day}`" type="button" class="cal-card" :data-status="day.status" @click="openDay(date)">
          <small>{{ day.day }} · W{{ String(day.week).padStart(2, '0') }}<template v-if="day.block"> · {{ day.block }}</template></small>
          <strong>{{ mainNames(day).join(' · ') || day.lifts.join(' · ') || 'SESSION' }}</strong>
          <span>{{ day.prescribedSets }} sets · {{ day.rowCount }} rows</span>
          <em class="cal-status" :class="day.status">{{ statusLabel(day) }}</em>
        </button>
      </article>
    </div>

    <!-- Month: an orientation grid with short titles, details stay below. -->
    <div v-else-if="!error && view === 'month'" class="cal-month" data-testid="cal-month">
      <div class="cal-month-head" aria-hidden="true"><span v-for="name in WEEKDAYS" :key="name">{{ name }}</span></div>
      <div class="cal-month-grid">
        <button
          v-for="date in monthCells" :key="date" type="button" class="cal-cell"
          :class="{ 'is-today': date === today, 'is-selected': date === selected, 'is-other': date.slice(0, 7) !== anchor.slice(0, 7) }"
          :aria-label="`${date}, ${byDate.get(date)?.length || 0} sessions`"
          @click="openDay(date)"
        >
          <span class="cal-cell-n">{{ date.slice(8) }}</span>
          <i v-for="day in (byDate.get(date) || []).slice(0, 2)" :key="day.cycleId + day.day" class="cal-cell-bar" :class="day.status" :title="day.title">{{ mainNames(day, 1).join('') || day.day }}</i>
          <small v-if="(byDate.get(date) || []).length > 2">+{{ byDate.get(date).length - 2 }} more</small>
          <small v-else-if="!byDate.get(date)?.length && inSpan(date)" class="cal-cell-rest">REST</small>
        </button>
      </div>
    </div>

    <!-- Agenda: the chronological read, best on a phone. -->
    <ol v-else-if="!error" class="cal-agenda" data-testid="cal-agenda">
      <li v-if="!agendaDays.length" class="cal-empty">No sessions in this range. The plan may not cover these dates yet.</li>
      <li v-for="day in agendaDays" :key="`${day.cycleId}-${day.date}-${day.day}`" :class="{ 'is-today': day.date === today }">
        <time :datetime="day.date">{{ day.date }}</time>
        <div>
          <b>{{ day.title }}</b>
          <p>W{{ String(day.week).padStart(2, '0') }} · DAY {{ day.day }} · {{ mainNames(day).join(' · ') || day.lifts.join(' · ') }}</p>
        </div>
        <em class="cal-status" :class="day.status">{{ statusLabel(day) }}</em>
        <RouterLink class="cal-open" :to="`/cycle/week/${day.week}/day/${day.day}`" v-if="day.cycleId === activeCycleId">Open →</RouterLink>
        <RouterLink class="cal-open" :to="`/archive/${day.cycleId}`" v-else>Archive →</RouterLink>
      </li>
    </ol>

    <!-- Selected day: a read-only drawer, never an editor. -->
    <section v-if="!error" class="cal-detail" data-testid="cal-detail">
      <header>
        <span class="eyebrow">SELECTED DAY</span>
        <h2>{{ selected }}</h2>
        <p v-if="!selectedDays.length">No session planned on this date.</p>
      </header>
      <article v-for="day in selectedDays" :key="`${day.cycleId}-${day.day}`" class="cal-detail-card">
        <div class="cal-detail-head">
          <b>{{ day.lifts.join(' · ') || day.day }}</b>
          <em class="cal-status" :class="day.status">{{ statusLabel(day) }}</em>
        </div>
        <p class="cal-detail-meta">{{ day.title }} · {{ day.block }} · {{ day.prescribedSets }} sets recorded as {{ day.loggedSets }}</p>
        <ul>
          <li v-for="row in day.rows" :key="row.seq">
            <span>{{ row.movement }}</span>
            <small>{{ row.sets }}×{{ row.reps }}<template v-if="row.loadKg"> · {{ row.loadKg }} kg</template></small>
          </li>
        </ul>
        <RouterLink v-if="day.cycleId === activeCycleId" class="quiet-button" :to="`/cycle/week/${day.week}/day/${day.day}`">Open the session →</RouterLink>
        <RouterLink v-else class="quiet-button" :to="`/archive/${day.cycleId}`">Open the archived cycle →</RouterLink>
      </article>
    </section>
  </section>
</template>

<style scoped>
.cal { display: grid; gap: 18px; padding-bottom: 40px; }
.cal-head { display: flex; justify-content: space-between; gap: 20px; flex-wrap: wrap; align-items: flex-end; }
.cal h1 { font-size: clamp(30px, 4vw, 46px); margin-top: 6px; }
.cal-deck { max-width: 46em; margin-top: 8px; font-size: 12.5px; line-height: 1.7; color: var(--muted); }
.cal-controls { display: grid; gap: 8px; justify-items: end; }
.cal-nav { display: flex; gap: 6px; }
.cal-views { display: flex; border: 1px solid var(--line2); }
.cal-views button { min-height: 44px; min-width: 64px; padding: 0 12px; border: 0; background: transparent; font: 700 9px var(--mono); letter-spacing: .1em; text-transform: uppercase; cursor: pointer; }
.cal-views button.on { background: var(--ink); color: var(--bg); }
.cal-range { font: 9px var(--mono); letter-spacing: .1em; color: var(--muted); text-transform: uppercase; }
.cal-error { border: 1px solid var(--accent); padding: 12px; font-size: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.cal-loading { font: 10px var(--mono); color: var(--muted); }
.cal-week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 1px; background: var(--soft); border: 1px solid var(--soft); }
.cal-col { background: var(--panel); padding: 10px; display: grid; gap: 8px; align-content: start; min-height: 150px; }
.cal-col.is-today { background: var(--accent-soft); }
.cal-col.is-selected { box-shadow: inset 0 0 0 1px var(--ink); }
.cal-col header { display: flex; align-items: baseline; justify-content: space-between; font: 8.5px var(--mono); letter-spacing: .1em; color: var(--muted); text-transform: uppercase; }
.cal-col header b { font-size: 15px; color: var(--ink); }
.cal-rest { font: 9px var(--mono); color: var(--muted); letter-spacing: .1em; }
.cal-rest.blank { visibility: hidden; }
.cal-cell-rest { font: 8px var(--mono); letter-spacing: .1em; color: var(--muted); }
.cal-card { display: grid; gap: 3px; min-height: 44px; padding: 8px; border: 1px solid var(--line2); background: var(--panel2); text-align: left; cursor: pointer; }
.cal-card:hover { border-color: var(--ink); }
.cal-card small { font: 8px var(--mono); letter-spacing: .1em; color: var(--muted); line-height: 1.5; }
.cal-card strong { font: 700 11px var(--mono); letter-spacing: .04em; line-height: 1.45; }
.cal-card span { font: 8.5px var(--mono); color: var(--muted); }
.cal-status { font: 700 8px var(--mono); letter-spacing: .12em; text-transform: uppercase; padding: 2px 5px; border: 1px solid var(--line2); width: fit-content; }
.cal-status.completed { color: var(--ink); border-color: var(--ink); }
.cal-status.missed { color: var(--accent); border-color: var(--accent); text-decoration: line-through; }
.cal-status.skipped { color: var(--muted); border-style: dashed; }
.cal-month { border: 1px solid var(--soft); background: var(--soft); }
.cal-month-head { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); background: var(--panel); padding: 8px 10px; font: 8px var(--mono); letter-spacing: .1em; color: var(--muted); text-transform: uppercase; }
.cal-month-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 1px; }
.cal-cell { min-height: 74px; padding: 6px 8px; border: 0; background: var(--panel); display: grid; gap: 3px; align-content: start; text-align: left; cursor: pointer; }
.cal-cell.is-other { background: var(--panel2); color: var(--muted); }
.cal-cell.is-today { background: var(--accent-soft); }
.cal-cell.is-selected { box-shadow: inset 0 0 0 1px var(--ink); }
.cal-cell-n { font: 500 13px var(--mono); }
.cal-cell-bar { display: flex; align-items: center; gap: 4px; font: 8px var(--mono); letter-spacing: .02em; color: var(--ink); line-height: 1.4; }
.cal-cell-bar::before { content: ''; width: 5px; height: 5px; border-radius: 50%; background: var(--line2); flex: none; }
.cal-cell-bar.completed::before { background: var(--ink); }
.cal-cell-bar.missed { color: var(--accent); }
.cal-cell-bar.missed::before { background: var(--accent); }
.cal-cell-bar.skipped { color: var(--muted); }
.cal-cell-bar.skipped::before { background: var(--muted); }
.cal-cell small { font: 8px var(--mono); color: var(--muted); }
.cal-agenda { display: grid; gap: 1px; background: var(--soft); border: 1px solid var(--soft); }
.cal-agenda li { display: grid; grid-template-columns: 92px minmax(0, 1fr) auto auto; gap: 12px; align-items: center; padding: 10px 12px; background: var(--panel); }
.cal-agenda li.is-today { background: var(--accent-soft); }
.cal-agenda time { font: 10px var(--mono); letter-spacing: .04em; }
.cal-agenda b { font: 700 10px var(--mono); letter-spacing: .06em; line-height: 1.5; }
.cal-agenda p { margin-top: 3px; font-size: 11px; color: var(--muted); }
.cal-open { font: 700 9px var(--mono); letter-spacing: .08em; border-bottom: 1px solid var(--hair); color: var(--ink); }
.cal-empty { padding: 18px; background: var(--panel); font-size: 12px; color: var(--muted); }
.cal-detail { border-top: 1px solid var(--hair); padding-top: 16px; display: grid; gap: 12px; }
.cal-detail h2 { font-size: 22px; margin-top: 4px; }
.cal-detail-card { border: 1px solid var(--line2); background: var(--panel); padding: 14px; display: grid; gap: 8px; }
.cal-detail-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.cal-detail-head b { font: 700 11px var(--mono); letter-spacing: .08em; }
.cal-detail-meta { font-size: 11px; color: var(--muted); }
.cal-detail ul { display: grid; gap: 4px; }
.cal-detail li { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; border-bottom: 1px dotted var(--hair); padding-bottom: 3px; }
.cal-detail li small { font: 10px var(--mono); color: var(--muted); }
@media (max-width: 860px) {
  .cal-week { grid-template-columns: 1fr; gap: 1px; }
  .cal-col { min-height: 0; grid-template-columns: 54px minmax(0, 1fr); align-items: center; }
  .cal-col header { flex-direction: column; align-items: flex-start; gap: 2px; }
  .cal-col .cal-card, .cal-col .cal-rest { grid-column: 2; }
  .cal-month-grid, .cal-month-head { grid-template-columns: repeat(7, minmax(0, 1fr)); }
  .cal-cell { min-height: 60px; padding: 4px; }
  .cal-agenda li { grid-template-columns: 80px minmax(0, 1fr); }
  .cal-agenda .cal-status, .cal-open { grid-column: 2; }
  .cal-controls { justify-items: stretch; width: 100%; }
  .cal-views button { flex: 1; }
}
</style>
