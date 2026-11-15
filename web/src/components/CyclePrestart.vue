<script setup>
import { computed, onMounted, ref } from 'vue';
import { solvePlates } from '../share.js';
import { collarPairOf, useCollars } from '../gear-settings.js';
const props = defineProps({ plan: Object, date: String });
const go = ref(false);
onMounted(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) go.value = true;
  else requestAnimationFrame(() => { go.value = true; });
});
const utcDay = iso => { const [y, m, d] = iso.split('-').map(Number); return Date.UTC(y, m - 1, d); };
const days = computed(() => Math.round((utcDay(props.plan.meta.startDate) - utcDay(props.date)) / 86400000));
const ring = computed(() => {
  if (days.value > 1) return { pct: 0, num: String(days.value), lbl: 'DAYS TO START' };
  if (days.value === 1) return { pct: 0, num: '1', lbl: 'DAY TO START' };
  return { pct: 1, num: '0', lbl: 'STARTS TODAY' };
});
const off = computed(() => (326.73 * (1 - Math.max(0.02, ring.value.pct))).toFixed(2));
const at = iso => new Date(`${iso}T00:00:00+08:00`);
const longDate = iso => new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', timeZone: 'Asia/Shanghai' }).format(at(iso));
const shortDate = iso => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(at(iso));
const weekday = iso => new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: 'Asia/Shanghai' }).format(at(iso)).toUpperCase();
const testDate = computed(() => props.plan.testPlan?.dates?.sbd || null);
const firstSession = computed(() => {
  const row = props.plan.workouts.find(item => item.week === 1);
  return row ? `/cycle/week/1/day/${row.day}` : '/cycle/week/1';
});
const openingSessions = computed(() => props.plan.weeks[0]?.sessions ?? Math.round(props.plan.meta.sessions / props.plan.meta.weeks));
const fmtKg = value => Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 });
// Block 2 — the first session, read from the plan. Plate chips reuse the share-card
// solver so preview and real logs cannot disagree about what is on the bar.
const firstRows = computed(() => {
  const first = props.plan.workouts.find(row => row.week === 1);
  if (!first) return { date: null, day: null, rows: [] };
  const rows = props.plan.workouts
    .filter(row => row.week === first.week && row.day === first.day && row.loadKg !== null && row.bucket !== 'accessory');
  // One line per movement: the calibration single and its back-off set read as one lift.
  const picked = [];
  rows.forEach(row => {
    const seen = picked.find(item => item.nameEn === row.nameEn);
    if (!seen) picked.push(row);
    else if (row.sets > seen.sets) picked[picked.indexOf(seen)] = row;
  });
  const lines = picked
    .slice(0, 4)
    .map(row => ({
      id: `${row.week}-${row.day}-${row.seq}`,
      movement: row.nameEn,
      rx: row.rxEn || `${row.sets}×${row.reps}`,
      load: row.loadKg,
      pct: row.pct === null || row.pct === undefined ? null : Math.round(row.pct * 1000) / 10,
      plates: solvePlates(row.loadKg, props.plan.meta.profile?.bar_kg ?? 20, collarPairOf(useCollars.value)),
    }));
  return { date: first.date, day: first.day, rows: lines };
});
// Block 3 — the warm-up ladder that ships with that date; empty stays visibly empty.
const warmupLadder = computed(() => {
  const date = firstRows.value.date;
  const first = props.plan.workouts.find(row => row.week === 1);
  const mains = new Set((props.plan.workouts || [])
    .filter(row => first && row.week === first.week && row.day === first.day && row.bucket === 'main')
    .map(row => row.nameEn));
  const lifts = ((date && props.plan.warmups?.[date]) || []).filter(lift => mains.has(lift.movement));
  return lifts.map(lift => ({
    movement: lift.movement,
    steps: lift.steps.map(step => `${fmtKg(step.kg)} kg × ${step.reps}`).join(' · '),
  }));
});
// Block 4 — what to record this week. No thresholds before a baseline exists.
const RECOVERY_ITEMS = ['Morning resting heart rate', 'Sleep hours', 'HRV if tracked', 'Bodyweight', 'Session RPE', 'Joint pain'];
</script>

<template>
  <section class="prestart" data-testid="cycle-prestart" aria-label="Cycle pre-start">
    <div class="pre-top">
      <section class="card hero">
        <div class="hero-row">
          <div class="ring" :class="{ go }" role="img" :aria-label="`${ring.lbl} ${ring.num}`">
            <svg viewBox="0 0 120 120" aria-hidden="true"><circle class="track" cx="60" cy="60" r="52" /><circle class="arc" cx="60" cy="60" r="52" :style="{ strokeDashoffset: go ? `${off}px` : '326.73px' }" /></svg>
            <div class="core"><div class="num">{{ ring.num }}</div><div class="lbl">{{ ring.lbl }}</div></div>
          </div>
          <div class="hero-copy">
            <div class="eyebrow">CYCLE · PRE-START</div>
            <div class="hero-date">{{ longDate(plan.meta.startDate) }}</div>
            <div class="hero-meta"><span class="hm-a">Week 1 of {{ plan.meta.weeks }}</span><span class="hm-dot"> · </span><span class="hm-b">{{ openingSessions }} sessions</span></div>
          </div>
        </div>
        <div class="hero-note">The calendar is fixed — starting early never moves a date. Preview the opening session below, or rebuild the plan in Outlook before it begins.</div>
        <div class="actions">
          <RouterLink :to="firstSession" class="btn primary">Start training</RouterLink>
          <RouterLink to="/questionnaire" class="btn ghost">Adjust start date</RouterLink>
        </div>
      </section>
      <section class="card facts" aria-label="Cycle facts">
        <div class="fact"><div class="k">WEEKS</div><div class="v">{{ plan.meta.weeks }}</div></div>
        <div class="fact"><div class="k">SESSIONS</div><div class="v">{{ plan.meta.sessions }}</div></div>
        <div class="fact"><div class="k">TEST DAY</div><div class="v">{{ testDate ? shortDate(testDate) : '—' }}</div><div v-if="testDate" class="s">{{ weekday(testDate) }} · {{ testDate.slice(0, 4) }}</div></div>
      </section>
    </div>
    <section class="card first-session" data-testid="prestart-firstsession" aria-label="First session preview">
      <div class="sec-head"><span class="eyebrow">FIRST SESSION · DAY {{ firstRows.day || "—" }}</span><span class="sec-meta">{{ firstRows.date ? longDate(firstRows.date) : "Not sampled" }}</span></div>
      <div v-if="firstRows.rows.length" class="fs-list">
        <div v-for="row in firstRows.rows" :key="row.id" class="fs-row">
          <span class="fs-copy"><b>{{ row.movement }}</b><em>{{ row.rx }}<span v-if="row.pct !== null"> · {{ row.pct }}%</span></em></span>
          <span class="fs-load">{{ fmtKg(row.load) }}<small>kg</small></span>
          <span class="fs-plates">
            <i v-for="(plate, index) in row.plates" :key="index" class="plate" :style="{ '--h': `${plate.h}px`, '--w': `${plate.w}px`, background: plate.color }" :title="`${plate.kg} kg`"></i>
            <em v-if="!row.plates.length">bar only</em>
          </span>
        </div>
      </div>
      <p v-else class="empty">Not sampled — the plan carries no loaded row for this session.</p>
    </section>
    <section class="card warmups" data-testid="prestart-warmups" aria-label="Warm-up ladder">
      <div class="sec-head"><span class="eyebrow">WARM-UP LADDER</span><span class="sec-meta">As prescribed on that date</span></div>
      <div v-if="warmupLadder.length" class="wu-list">
        <div v-for="lift in warmupLadder" :key="lift.movement" class="wu-row"><b>{{ lift.movement }}</b><span>{{ lift.steps }}</span></div>
      </div>
      <p v-else class="empty">Not sampled — no warm-up rows are attached to this date.</p>
    </section>
    <section class="card recovery" data-testid="prestart-recovery" aria-label="Recovery baseline">
      <div class="sec-head"><span class="eyebrow">RECOVERY BASELINE</span><span class="sec-meta">Measure this week</span></div>
      <div class="rb-chips"><span v-for="item in RECOVERY_ITEMS" :key="item">{{ item }}</span></div>
      <p class="empty rb-note">No baseline yet — thresholds unlock once the first week is logged. Values are not shown before there is data.</p>
    </section>
  </section>
</template>

<style scoped>
.prestart { --dur-slow: .5s; --dur-live: .6s; margin: 14px 0; }
.card { background: var(--card-grad); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--card-shadow); padding: 16px; min-width: 0; }
.pre-top { display: grid; gap: 12px; }
.eyebrow { font-family: var(--mono); font-size: 8.5px; font-weight: 500; letter-spacing: .18em; text-transform: uppercase; color: var(--muted); }
.hero { position: relative; overflow: hidden; }
.hero::after { content: ''; position: absolute; right: -40px; top: -60px; width: 180px; height: 180px; border-radius: 50%; background: var(--accent-soft); opacity: .9; pointer-events: none; }
.hero-row { display: flex; align-items: center; gap: 14px; position: relative; z-index: 1; }
.ring { flex: 0 0 auto; width: clamp(96px, 30vw, 116px); height: clamp(96px, 30vw, 116px); position: relative; }
.ring svg { display: block; width: 100%; height: 100%; transform: rotate(-90deg); }
.ring .track { fill: none; stroke: var(--line2); stroke-width: 7; }
.ring .arc { fill: none; stroke: var(--t1); stroke-width: 7; stroke-linecap: round; stroke-dasharray: 326.73; transition: stroke-dashoffset var(--dur-live) var(--ease-out); }
.ring .core { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; padding: 0 10px; }
.ring .num { font-family: var(--mono); font-size: clamp(30px, 11vw, 42px); font-weight: 700; line-height: 1; letter-spacing: -.04em; white-space: nowrap; }
.ring .lbl { margin-top: 7px; font-family: var(--mono); font-size: 7.5px; letter-spacing: .1em; line-height: 1.35; color: var(--muted); text-transform: uppercase; }
.hero-copy { min-width: 0; flex: 1 1 auto; }
.hero-date { margin-top: 3px; font-family: var(--serif); font-size: clamp(19px, 5.4vw, 27px); font-weight: 700; line-height: 1.1; letter-spacing: -.01em; }
.hero-meta { margin-top: 5px; font-size: 11.5px; line-height: 1.45; color: var(--muted); }
.hero-note { margin-top: 9px; font-size: 10px; line-height: 1.5; color: var(--muted); position: relative; z-index: 1; }
.actions { display: grid; grid-template-columns: 1fr; gap: 8px; margin-top: 14px; position: relative; z-index: 1; }
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 46px; padding: 0 15px; border-radius: 11px; border: 1px solid transparent; font-family: var(--display); font-size: 14.5px; font-weight: 700; letter-spacing: .02em; text-decoration: none; transition: transform var(--dur-fast), background var(--dur-fast), border-color var(--dur-fast); }
.btn:active { transform: scale(.985); }
.btn.primary { background: var(--t1); border-color: var(--t1); color: var(--on-accent); box-shadow: 0 8px 20px -12px var(--t1); }
.btn.primary:hover { background: var(--accent); border-color: var(--accent); }
.btn.ghost { background: var(--inset); border-color: var(--line); color: var(--ink); }
.btn.ghost:hover { background: var(--accent-soft); }
.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; align-content: start; }
.fact { background: var(--inset); border: 1px solid var(--line-soft); border-radius: 11px; padding: 9px 10px; min-width: 0; }
.fact .k { font-family: var(--mono); font-size: 8px; letter-spacing: .12em; color: var(--ink); text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fact .v { margin-top: 2px; font-family: var(--mono); font-size: 13.5px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fact .s { margin-top: 1px; font-family: var(--mono); font-size: 8px; color: var(--ink); letter-spacing: .06em; }
.sec-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.sec-meta { font-family: var(--mono); font-size: 8.5px; letter-spacing: .1em; color: var(--muted); text-transform: uppercase; }
.first-session, .warmups, .recovery { margin-top: 12px; }
.empty { margin: 10px 0 0; font-size: 10.5px; line-height: 1.5; color: var(--muted); }
.fs-list { display: grid; gap: 6px; margin-top: 10px; }
.fs-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: 'copy load' 'plates plates'; gap: 5px 10px; align-items: center; padding: 9px 10px; border: 1px solid var(--line-soft); border-radius: 11px; background: var(--inset); }
.fs-copy { grid-area: copy; display: grid; gap: 2px; min-width: 0; }
.fs-copy b { font-family: var(--display); font-size: 12.5px; font-weight: 700; letter-spacing: .01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fs-copy em { font-style: normal; font-family: var(--mono); font-size: 9px; letter-spacing: .04em; color: var(--muted); }
.fs-load { grid-area: load; font-family: var(--mono); font-size: 14px; font-weight: 700; text-align: right; white-space: nowrap; }
.fs-load small { font-size: 9px; font-weight: 500; color: var(--muted); margin-left: 2px; }
.fs-plates { grid-area: plates; display: flex; align-items: center; gap: 3px; height: 16px; min-width: 0; overflow: hidden; }
.fs-plates .plate { display: block; flex: 0 0 auto; height: var(--h); width: var(--w); border-radius: 2px; box-shadow: inset 0 0 0 1px rgba(0,0,0,.12); }
.fs-plates em { font-style: normal; font-family: var(--mono); font-size: 8.5px; color: var(--muted); }
.wu-list { display: grid; gap: 7px; margin-top: 10px; }
.wu-row { display: grid; gap: 2px; }
.wu-row b { font-family: var(--display); font-size: 11.5px; font-weight: 700; letter-spacing: .01em; }
.wu-row span { font-family: var(--mono); font-size: 9.5px; line-height: 1.5; color: var(--muted); }
.rb-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.rb-chips span { padding: 4px 9px; border: 1px solid var(--line-soft); border-radius: 999px; background: var(--inset); font-family: var(--mono); font-size: 8.5px; letter-spacing: .05em; text-transform: uppercase; color: var(--ink); }
.rb-note { margin-top: 10px; }
@media (max-width: 359px) {
  .hero-meta .hm-a, .hero-meta .hm-b { display: block; }
  .hero-meta .hm-dot { display: none; }
}
@media (min-width: 400px) {
  .actions { grid-template-columns: 1.35fr 1fr; }
}
@media (min-width: 900px) {
  .pre-top { grid-template-columns: 1.55fr 1fr; gap: 14px; align-items: stretch; }
  .hero { display: flex; flex-direction: column; justify-content: center; }
  .hero-row { gap: 20px; }
  .ring { width: 132px; height: 132px; }
  .ring .num { font-size: 46px; }
  .actions { grid-template-columns: 1fr; max-width: 260px; }
  .facts { grid-template-columns: 1fr; gap: 0; padding: 6px 16px; align-content: center; }
  .fact { background: none; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; padding: 11px 0; }
  .fact:last-child { border-bottom: 0; }
  .fs-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .wu-list { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 18px; }
}
@media (prefers-reduced-motion: reduce) {
  .ring .arc, .btn { transition: none; }
}
</style>