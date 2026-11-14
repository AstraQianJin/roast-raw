<script setup>
import { computed, onMounted, ref } from 'vue';
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
  .actions { max-width: 420px; }
  .facts { grid-template-columns: 1fr; gap: 0; padding: 6px 16px; align-content: center; }
  .fact { background: none; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; padding: 11px 0; }
  .fact:last-child { border-bottom: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .ring .arc, .btn { transition: none; }
}
</style>