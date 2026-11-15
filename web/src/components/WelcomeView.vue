<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import packageInfo from '../../package.json';
import BeanMark from './BeanMark.vue';
import landingFacts from '../landing-facts.json';
const [major, , patch] = packageInfo.version.split('.');
const releaseVersion = `${major}.${patch.padStart(2, '0')}`;

// Every landing number comes from web/src/landing-facts.json, which is written by
// server/tools/landing_facts.py from data/plan.json. Never type a number here.
const sample = landingFacts;
const SAMPLE_LABELS = { S: 'SQUAT', B: 'BENCH', D: 'DEADLIFT' };
const liftLabel = lift => SAMPLE_LABELS[lift.lift] || lift.lift;
const fmtKg = value => Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 });
const sampleDate = (() => {
  const date = new Date(`${sample.date}T00:00:00+08:00`);
  const parts = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Shanghai' }).formatToParts(date);
  const pick = type => parts.find(part => part.type === type)?.value || '';
  return `${pick('day')} ${pick('month').toUpperCase()} ${pick('year')}`;
})();

const root = ref(null);
const index = ref(0);
const track = ref(null);
const dragX = ref(0);
const dragging = ref(false);
let cleanup = () => {};
let startX = 0;
let startY = 0;
let activePointer = null;
let axis = null;

const shots = [
  { src: '/shots/today-390-light.png', k: 'TODAY', title: 'Prescribed loads, recorded sets and the working body on one page.' },
  { src: '/shots/plan-390-light.png', k: 'CYCLE', title: 'A fixed calendar: every week is a square, every block a colour.' },
  { src: '/shots/analysis-390-light.png', k: 'ANALYSIS', title: 'Weekly working sets, SBD equivalents and reference bands.' },
  { src: '/shots/archive-390-light.png', k: 'ARCHIVE', title: 'Past cycles stay readable, exportable and comparable.' },
];
function step(delta) { index.value = (index.value + delta + shots.length) % shots.length; }
function offset(i) { const n = shots.length; let d = (i - index.value + n) % n; if (d > n / 2) d -= n; return d; }
function cardStyle(i) {
  const o = offset(i); const a = Math.abs(o);
  return {
    transform: `translateX(${o * 58}%) scale(${1 - Math.min(a, 3) * .06}) rotate(${o * 1.8}deg)`,
    opacity: a > 2 ? 0 : 1 - a * .3,
    zIndex: 20 - a,
  };
}
function onDown(event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return;
  activePointer = event.pointerId; startX = event.clientX; startY = event.clientY; axis = null; dragging.value = true; dragX.value = 0;
}
function onMove(event) {
  if (!dragging.value || event.pointerId !== activePointer) return;
  const dx = event.clientX - startX; const dy = event.clientY - startY;
  if (!axis) {
    if (Math.abs(dx) < 7 && Math.abs(dy) < 7) return;
    axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
    if (axis === 'x') track.value?.setPointerCapture?.(activePointer);
  }
  if (axis !== 'x') return;
  dragX.value = dx;
}
function onUp(event) {
  if (!dragging.value || (event && event.pointerId !== activePointer)) return;
  const dx = dragX.value; const width = track.value?.clientWidth || 390;
  if (Math.abs(dx) > Math.max(44, width * 0.16)) step(dx < 0 ? 1 : -1);
  dragging.value = false; dragX.value = 0; activePointer = null; axis = null;
}
function onKey(event) {
  if (event.key === 'ArrowLeft') { event.preventDefault(); step(-1); }
  if (event.key === 'ArrowRight') { event.preventDefault(); step(1); }
}

const phases = ['hyper', 'hyper', 'hyper', 'deload', 'strength', 'strength', 'strength', 'deload', 'transmute', 'transmute', 'peak', 'deload', 'test'];
const capSets = [27, 28, 30, 12, 28, 28, 30, 12, 23, 23, 18, 13, 17];
const capTop = [70, 72, 74, 60, 78, 80, 82, 62, 86, 88, 92, 70, 100];
const condMin = [60, 60, 60, 20, 60, 25, 40, 20, 45, 50, 55, 30, 20];
const capMax = 32;
const capBars = computed(() => capSets.map((sets, i) => ({
  n: i + 1,
  sets,
  phase: phases[i],
  h: Math.max(4, sets / capMax * 100),
  x: ((i + .5) / capSets.length * 100),
  top: capTop[i],
  y: 100 - (capTop[i] - 50) / 60 * 100,
})));
const capPoints = computed(() => capBars.value.map(bar => `${bar.x},${bar.y}`).join(' '));
const condMax = 90;
const condBars = computed(() => condMin.map((minutes, i) => ({
  n: i + 1,
  minutes,
  h: Math.max(3, minutes / condMax * 100),
  phase: phases[i],
})));
const condRange = computed(() => `${Math.min(...condMin)}–${Math.max(...condMin)}`);

const facts = [
  { k: 'SBD', t: 'Analysis by lift', d: 'Top sets, working sets and e1RM, per lift and per week.' },
  { k: 'MUSCLE', t: '16-leaf weekly map', d: 'Weighted contributions, front and back, week by week.' },
  { k: 'AI', t: 'Block outlook', d: 'Reads completion, intensity and volume, then proposes the next block.' },
  { k: 'CLOUD', t: 'Same ledger, two devices', d: 'Phone and browser read one cycle. Backup is optional.' },
];

const chain = [
  { n: '01', k: 'CYCLE PLAN', d: 'Fixed weeks, phase-coloured blocks, deload and test marked. Import or export the whole cycle.' },
  { n: '02', k: 'DAILY PRESCRIPTION', d: 'Main lifts, variations and accessories list sets, intensity and load row by row.' },
  { n: '03', k: 'PLATE MATH', d: 'Barbells, pin machines, loaded plates, dumbbells and bodyweight land on a load you can pick up.' },
  { n: '04', k: 'SET-BY-SET LOG', d: 'Check-offs and the day summary share one screen. No upload step.' },
  { n: '05', k: 'CAPACITY', d: 'Working sets, SBD equivalents and reference bands on one track.' },
  { n: '06', k: 'EXPORT & SHARE', d: 'JSON export and a 1080 × 1440 session card, with no watermark.' },
];

const personas = [
  { n: '01', k: 'ATHLETE', title: 'Powerlifters', d: 'The three SBD lifts, cycles and meet peaks. You need your cycle plan connected to each day’s prescription — not another social app.', tags: ['Cycle & sessions', 'Today', 'Meet peak'] },
  { n: '02', k: 'COACH', title: 'Coaches', d: 'Running several lifters makes mismatched spreadsheets the biggest risk. One shared plan keeps copies, edits and exports on the same numbers.', tags: ['Plan reuse', 'Cell edits', 'Export check'] },
  { n: '03', k: 'SELF-COACHED', title: 'Self-coached lifters', d: 'No cloud coach and no vendor lock-in. The ledger lives on your own server and leaves whenever you export it.', tags: ['Own server', 'Open export', 'No vendor lock-in'] },
];

const demoWeeks = ['hyper', 'hyper', 'hyper', 'hyper', 'strength', 'strength', 'strength', 'deload', 'transmute', 'transmute', 'peak', 'deload', 'test'];

onMounted(() => {
  const el = root.value;
  if (!el || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  el.classList.add('js');
  const targets = [...el.querySelectorAll('.rv')];
  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('in'); io.unobserve(entry.target); } });
  }, { rootMargin: '0px 0px -8% 0px' });
  targets.forEach(node => io.observe(node));
  cleanup = () => { io.disconnect(); document.documentElement.classList.remove('wl-open'); };
});
onBeforeUnmount(() => cleanup());
</script>

<template>
  <div ref="root" class="welcome" data-testid="welcome">
    <section class="wl-hero">
      <div class="wl-hero-grid">
        <div class="wl-copy">
          <p class="wl-kicker">ROAST RAW <span>·</span> POWERLIFTING TRAINING JOURNAL</p>
          <h1>Every set,<br><em>accounted for.</em></h1>
          <p class="wl-lede">Cycle plan, daily prescription, set-by-set log and the analysis that follows — one chain. No feed, no gamified score, nothing inferred from a session you skipped.</p>
        </div>
        <div class="wl-visual">
          <div class="hv" aria-label="Illustrative product preview">
            <div class="hv-bar"><span>ROAST RAW · <b>{{ sample.label }}</b></span><span>PREVIEW</span></div>
            <div class="hv-stack">
              <div v-for="lift in sample.lifts" :key="`hero-${lift.lift}`" class="hv-card"><span class="hv-k">{{ liftLabel(lift) }} · TOP</span><div class="hv-h"><b>{{ fmtKg(lift.top_kg) }}<small>kg</small></b><span v-if="lift.pct !== undefined">{{ lift.pct }}%</span></div><div class="hv-sets"><i class="ok">{{ lift.sets }}×{{ lift.reps }}</i></div></div>
              <div class="hv-card wide"><span class="hv-k">CYCLE · {{ demoWeeks.length }} WEEKS</span><div class="hv-weeks"><i v-for="(phase, i) in demoWeeks" :key="i" :class="['ct', phase, { on: i === sample.week - 1 }]"></i></div><div class="hv-meta"><span>HYPER → STRENGTH → PEAK</span><b>W{{ String(sample.week).padStart(2, '0') }}</b></div></div>
              <div class="hv-card wide"><span class="hv-k">TOTAL LOAD · MAIN + VARIATIONS</span><div class="hv-h"><b>{{ fmtKg(sample.day_total_kg) }}<small>kg</small></b><span>{{ sample.set_count }} SETS</span></div></div>
            </div>
          </div>
        </div>
      </div>
      <div class="wl-facts rv">
        <div v-for="fact in facts" :key="fact.k" class="wl-fact"><b>{{ fact.k }}</b><span>{{ fact.t }}</span><em>{{ fact.d }}</em></div>
      </div>
      <p class="wl-fine">Single-user release {{ releaseVersion }} · Records live on your server · No offline cache, no sync service unless you turn backup on.</p>
    </section>

    <section class="wl-sec" id="capacity">
      <div class="wl-sec-head rv"><span class="wl-num">01 /</span><h2>Working sets, week by week.</h2><p class="wl-deck">Main, SBD variations and accessory work are counted separately. The line is the top set as a share of 1RM. A skipped set never becomes tonnage.</p></div>
      <div class="wl-two rv">
        <figure class="wl-figure">
          <div class="wl-figure-head"><span>CAPACITY / ANALYSIS</span><span>{{ capSets.length }} WEEKS</span></div>
          <div class="wl-chart">
            <div class="wl-yax"><span>100%</span><span>75%</span><span>50%</span></div>
            <div class="wl-plot">
              <div class="wl-grid"><i style="bottom:0"></i><i style="bottom:41.7%"></i><i style="bottom:83.3%"></i></div>
              <div class="wl-bars"><div v-for="bar in capBars" :key="bar.n" class="wl-bar" :class="bar.phase" :style="{ height: `${bar.h}%` }" :title="`Week ${bar.n}: ${bar.sets} sets, top ${bar.top}%`"></div></div>
              <svg class="wl-line" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline :points="capPoints"></polyline></svg>
            </div>
          </div>
          <div class="wl-xaxis" aria-hidden="true"><span v-for="bar in capBars" :key="bar.n">{{ bar.n }}</span></div><figcaption>WEEKLY WORKING SETS · TOP SET %1RM</figcaption>
        </figure>
        <figure class="wl-figure cond">
          <div class="wl-figure-head"><span>CONDITIONING</span><span>ESTIMATE</span></div>
          <div class="cond-num"><b>{{ condRange }}</b><i>moderate-intensity equivalent, min/week</i></div>
          <div class="cond-band">
            <div class="cond-zone"></div>
            <div class="cond-bars"><i v-for="bar in condBars" :key="bar.n" :class="bar.phase" :style="{ height: `${bar.h}%` }" :title="`Week ${bar.n}: ${bar.minutes} min`"></i></div>
          </div>
          <figcaption>Planned cardio is converted to moderate-intensity minutes. It is an estimate, not a measured load.</figcaption>
        </figure>
      </div>
    </section>

    <section class="wl-sec" id="session">
      <div class="wl-sec-head rv"><span class="wl-num">02 /</span><h2>A session, on paper.</h2><p class="wl-deck">The day page reads like a page: main lifts and their top intensity, the total load, then the sets. Nothing is a card you have to open twice.</p></div>
      <div class="wl-two rv">
        <div class="wl-session">
          <div class="wl-session-head"><span>MAIN LIFTS · TOP INTENSITY</span><span>{{ sample.label }}</span></div>
          <div v-for="lift in sample.lifts" :key="`row-${lift.lift}`" class="wl-lift"><div><b>{{ liftLabel(lift) }}</b><em>Main · {{ lift.sets }}×{{ lift.reps }}</em></div><strong>{{ fmtKg(lift.top_kg) }}<small>kg</small></strong><i v-if="lift.pct !== undefined">{{ lift.pct }}%</i><i v-else>—</i></div>
          <div class="wl-total"><span>TOTAL LOAD<br><small>main work + variations</small></span><b>{{ fmtKg(sample.day_total_kg) }}<small>kg</small></b></div>
        </div>
        <div class="wl-note">
          <span class="wl-note-k">WHY IT MATTERS</span>
          <p>Top intensity sits next to the load, not in a separate table. The total is the work you will actually move, not a percentage of a theoretical max.</p>
          <ul><li>Top set, back-off and AMRAP labelled</li><li>Gear, plates and warm-ups on the same page</li><li>Log folded into the row it belongs to</li></ul>
        </div>
      </div>
    </section>

    <section class="wl-sec" id="share">
      <div class="wl-sec-head rv"><span class="wl-num">03 /</span><h2>A session is already a card.</h2><p class="wl-deck">One tap on a day page renders the session as a 1080 × 1440 card: one print finish, no watermark.</p></div>
      <div class="wl-two rv">
        <div class="wl-share-wrap"><div class="wl-share-card">
          <p class="wl-share-k">ROAST RAW · {{ sample.label }}</p>
          <div v-for="lift in sample.lifts" :key="`card-${lift.lift}`" class="wl-share-lift"><span>{{ liftLabel(lift) }}</span><b>{{ fmtKg(lift.top_kg) }}</b><i v-if="lift.pct !== undefined">{{ lift.pct }}%</i></div>
          <div class="wl-share-total"><span>TOTAL LOAD</span><b>{{ fmtKg(sample.day_total_kg) }} kg</b></div>
          <p class="wl-share-f">{{ sample.set_count }} SETS · {{ sampleDate }} · NO WATERMARK</p>
        </div></div>
        <div class="wl-note">
          <span class="wl-note-k">EXPORT, NOT A FEED</span>
          <p>The card reads the block you ran, not the block you planned. Share it, keep it, or ignore it — the ledger does not change either way.</p>
          <ul><li>1080 × 1440 PNG</li><li>No watermark</li><li>Same numbers as the day page</li></ul>
        </div>
      </div>
    </section>

    <section class="wl-sec" id="outlook">
      <div class="wl-sec-head rv"><span class="wl-num">04 /</span><h2>It reads the block you ran, then proposes the next one.</h2><p class="wl-deck">Optional AI reads completion, intensity and volume from the block you actually ran, then proposes the next. Every line arrives as a comparison; nothing you do not accept reaches the ledger.</p></div>
      <div class="wl-ai rv">
        <div class="wl-ai-row"><span class="wl-ai-k">BLOCK B2 · REVIEW</span><span class="wl-ai-state">COMPLETION 92%</span><p>Top-set intensity held; bench volume fell 3% short across two sessions.</p></div>
        <div class="wl-ai-row"><span class="wl-ai-k">PROPOSAL · B3</span><span class="wl-ai-state">AWAITING ACCEPT</span><p>Raise squat top set 2.5 kg; keep bench volume, add one back-off set.</p></div>
        <div class="wl-ai-row muted"><span class="wl-ai-k">LEDGER</span><span class="wl-ai-state">UNCHANGED</span><p>Nothing is written until you accept it. Decline and the plan stays as it is.</p></div>
        <p class="wl-ai-f">AI is optional. Turn it off and every other screen still works.</p>
      </div>
    </section>

    <section class="wl-sec" id="cloud">
      <div class="wl-sec-head rv"><span class="wl-num">05 /</span><h2>Finish on the phone, open the same ledger on the web.</h2><p class="wl-deck">The same cycle and the same set log render in a browser — no export, no re-entry. Turn cloud backup on and a new phone picks it up; turn it off and only that device is affected.</p></div>
      <div class="wl-browser rv">
        <div class="wl-browser-bar"><i></i><i></i><i></i><span>82.157.146.30/cycle</span></div>
        <div class="wl-browser-body">
          <div class="wl-browser-side"><b>W05</b><span>STRENGTH BASE</span><span>S 80 · B 82.5 · D 85</span></div>
          <div class="wl-browser-rows"><div v-for="week in 5" :key="week"><span>W{{ String(week).padStart(2, '0') }}</span><i :style="{ width: `${30 + week * 9}%` }"></i><b>{{ 12 + week }}</b></div></div>
        </div>
      </div>
    </section>

    <section class="wl-sec" id="screens">
      <div class="wl-sec-head rv"><span class="wl-num">06 /</span><h2>The journal, on the record.</h2><p class="wl-deck">Captured at phone width from the current build. Drag the deck, or use the slider, to move through the set.</p></div>
      <div ref="track" class="wl-shots rv" :class="{ grabbing: dragging }" :style="dragX ? { transform: `translate3d(${dragX}px,0,0)` } : null" tabindex="0" role="region" aria-roledescription="carousel" aria-label="Product screenshots" @pointerdown="onDown" @pointermove="onMove" @pointerup="onUp" @pointercancel="onUp" @keydown="onKey">
        <figure v-for="(shot, i) in shots" :key="shot.src" class="wl-card" :class="{ front: offset(i) === 0 }" :style="cardStyle(i)" :aria-hidden="offset(i) !== 0">
          <img :src="shot.src" :alt="`${shot.k} page screenshot`" loading="lazy" draggable="false">
        </figure>
      </div>
      <div class="wl-slider" aria-label="Screenshot position">
        <i class="wl-slider-rail" aria-hidden="true"></i>
        <i class="wl-slider-thumb" aria-hidden="true" :style="{ left: `${index / shots.length * 100}%`, width: `${100 / shots.length}%` }"></i>
        <button v-for="(shot, i) in shots" :key="`t-${shot.src}`" type="button" :aria-label="`Show ${shot.k}`" :aria-current="index === i ? 'true' : 'false'" @click="index = i"></button>
      </div>
      <div class="wl-caption" aria-live="polite"><p class="wl-cap-name">Figure {{ index + 1 }} · {{ shots[index].k }}</p><p class="wl-cap-desc">{{ shots[index].title }}</p></div>
    </section>

    <section class="wl-sec" id="who">
      <div class="wl-sec-head rv"><span class="wl-num">07 /</span><h2>One journal, three ways to use it.</h2><p class="wl-deck">Plan, prescription, logging and export are one chain. It does not replace a coach and it is not a content community. It just keeps the day-to-day record accurate.</p></div>
      <div class="wl-people rv">
        <article v-for="person in personas" :key="person.n" class="wl-person">
          <span class="wl-person-n">{{ person.n }} / {{ person.k }}</span>
          <h3>{{ person.title }}</h3>
          <p>{{ person.d }}</p>
          <ul><li v-for="tag in person.tags" :key="tag">{{ tag }}</li></ul>
        </article>
      </div>
    </section>

    <section class="wl-sec" id="chain">
      <div class="wl-sec-head rv"><span class="wl-num">08 /</span><h2>Six links, plan to review.</h2><p class="wl-deck">Six routes served by one FastAPI process. The network is used only by the optional AI you turn on.</p></div>
      <div class="wl-chain rv">
        <div v-for="item in chain" :key="item.n" class="wl-link"><span>{{ item.n }}</span><div><b>{{ item.k }}</b><p>{{ item.d }}</p></div></div>
      </div>
    </section>

    <section class="wl-sec wl-enter rv" id="download">
      <span class="wl-num">09 /</span>
      <h2>Get it now.</h2>
      <p class="wl-deck">The web ledger is live. There are no phone apps to download: the buttons below stay closed until an app actually ships.</p>
      <div class="wl-enter-grid">
        <a class="wl-cta" href="/login?next=/cycle">Open the journal →</a>
        <span class="wl-cta ghost disabled">Android APK<br><small>COMING SOON</small></span>
        <span class="wl-cta ghost disabled">iOS<br><small>COMING SOON</small></span>
      </div>
      <p class="wl-enter-f">GitHub repository: <a href="https://github.com/AstraQianJin/roast-raw" rel="noopener">AstraQianJin/roast-raw</a> · License: single-user release, no tiers.</p>
    </section>

    <footer class="wl-foot">
      <div class="wl-foot-brand"><BeanMark class="wl-bean" /> <b>Roast Raw</b><span>Training journal</span></div>
      <div class="wl-foot-links"><RouterLink to="/plan">Cycle</RouterLink><a href="https://github.com/AstraQianJin/roast-raw" rel="noopener">GitHub</a><a href="#download">Download</a><span>{{ releaseVersion }}</span></div>
    </footer>
  </div>
</template>

<style scoped>
.welcome {
  --ease: cubic-bezier(.22, 1, .36, 1);
  --hair: rgba(17, 17, 17, .28);
  --soft: rgba(17, 17, 17, .10);
  position: relative;
  background-image: radial-gradient(rgba(20, 19, 17, .055) .6px, transparent .7px);
  background-size: 3px 3px;
}
.welcome h1, .welcome h2, .welcome h3 { font-family: var(--serif); font-weight: 400; text-transform: none; letter-spacing: -.035em; line-height: 1.03; }
.welcome h1 { font-size: clamp(44px, 8.4vw, 76px); margin-top: 12px; }
.welcome h1 em { font-style: normal; color: var(--accent); }
.wl-kicker { font: 10px var(--mono); letter-spacing: .16em; color: var(--muted); }
.wl-kicker span { color: var(--accent); }
.wl-hero { padding-top: clamp(22px, 5vh, 52px); }
.wl-hero-grid { display: grid; grid-template-columns: minmax(0, 1.06fr) minmax(0, .94fr); gap: clamp(24px, 4vw, 56px); align-items: center; }
.wl-copy { min-width: 0; }
.wl-lede { margin-top: 20px; max-width: 34em; color: var(--muted); font-size: clamp(14px, 1.25vw, 16px); line-height: 1.85; }
.wl-visual { min-width: 0; }
.hv { border: 1px solid var(--line); border-radius: 16px; background: var(--panel); padding: 14px; box-shadow: 0 18px 44px rgba(17, 17, 17, .12); }
.hv-bar { display: flex; justify-content: space-between; gap: 10px; padding: 0 2px 10px; font: 9px var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.hv-bar b { color: var(--accent); }
.hv-stack { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.hv-card { border: 1px solid var(--soft); border-radius: 11px; background: var(--panel2); padding: 11px 12px; min-width: 0; }
.hv-card.wide { grid-column: 1 / -1; }
.hv-k { font: 8.5px var(--mono); letter-spacing: .14em; color: var(--muted); }
.hv-h { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-top: 7px; font-size: 11.5px; color: var(--muted); }
.hv-h b { font-family: var(--mono); font-size: 17px; color: var(--ink); }
.hv-h small { font-size: 9px; margin-left: 2px; color: var(--muted); }
.hv-sets { display: flex; gap: 5px; margin-top: 8px; }
.hv-sets i { flex: 1; height: 22px; display: grid; place-items: center; border: 1px solid var(--soft); border-radius: 6px; font: 10px var(--mono); font-style: normal; color: var(--muted); }
.hv-sets i.ok { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
.hv-weeks { display: flex; gap: 3px; margin-top: 9px; }
.hv-weeks i { flex: 1; height: 16px; border-radius: 3px; background: var(--soft); }
.hv-weeks i.ct.hyper { background: var(--ct-hyper); }
.hv-weeks i.ct.strength { background: var(--ct-strength); }
.hv-weeks i.ct.transmute { background: var(--ct-transmute); }
.hv-weeks i.ct.peak, .hv-weeks i.ct.test { background: var(--ct-peak); }
.hv-weeks i.ct.deload { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 3px, var(--ct-deload-s) 3px 6px); }
.hv-weeks i.on { outline: 2px solid var(--ink); outline-offset: 1px; }
.hv-meta { display: flex; justify-content: space-between; gap: 8px; margin-top: 8px; font: 8.5px var(--mono); letter-spacing: .05em; color: var(--muted); }
.hv-meta b { color: var(--ink); }
.wl-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; background: var(--soft); border: 1px solid var(--soft); border-radius: 14px; overflow: hidden; margin-top: clamp(28px, 5vh, 48px); }
.wl-fact { position: relative; background: var(--panel); padding: 18px 16px 18px; min-width: 0; }
.wl-fact::before { content: ''; position: absolute; inset: 0 0 auto; height: 3px; background: var(--f, var(--accent)); }
.wl-fact:nth-child(1) { --f: var(--accent); }
.wl-fact:nth-child(2) { --f: var(--ct-strength); }
.wl-fact:nth-child(3) { --f: var(--ct-transmute); }
.wl-fact:nth-child(4) { --f: var(--ct-deload); }
.wl-fact b { display: block; font: 700 15px var(--mono); letter-spacing: -.02em; color: var(--f, var(--accent)); }
.wl-fact span { display: block; margin-top: 5px; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; color: var(--ink); }
.wl-fact em { display: block; margin-top: 4px; font-style: normal; font-size: 11px; line-height: 1.55; color: var(--muted); }
.wl-fine { margin-top: 14px; font-size: 11px; line-height: 1.75; color: var(--muted); }
.wl-sec { padding-top: clamp(46px, 8vh, 88px); border-top: 1px solid var(--hair); margin-top: clamp(34px, 6vh, 64px); }
.wl-sec-head { max-width: 46em; }
.wl-num { display: block; font: 700 10px var(--mono); letter-spacing: .16em; color: var(--accent); margin-bottom: 10px; }
.wl-sec-head h2 { font-size: clamp(26px, 3.6vw, 40px); letter-spacing: -.03em; }
.wl-deck { margin-top: 10px; color: var(--muted); font-size: clamp(13px, 1.2vw, 15px); line-height: 1.85; max-width: 62ch; }
.wl-two { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, .85fr); gap: clamp(18px, 3vw, 40px); margin-top: 26px; align-items: start; }
.wl-figure { border: 1px solid var(--hair); border-radius: 14px; background: var(--panel); padding: 16px; min-width: 0; }
.wl-figure-head { display: flex; justify-content: space-between; gap: 10px; font: 8.5px var(--mono); letter-spacing: .12em; color: var(--muted); }
.wl-chart { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 6px; margin-top: 18px; }
.wl-yax { position: relative; height: 124px; font: 8px var(--mono); color: var(--muted); }
.wl-yax span { position: absolute; right: 0; transform: translateY(50%); }
.wl-yax span:nth-child(1) { bottom: 83.3%; } .wl-yax span:nth-child(2) { bottom: 41.7%; } .wl-yax span:nth-child(3) { bottom: 0; }
.wl-plot { position: relative; height: 124px; }
.wl-grid { position: absolute; inset: 0; }
.wl-grid i { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--soft); }
.wl-bars { position: relative; z-index: 1; display: flex; align-items: flex-end; gap: 2px; height: 100%; padding: 0 3px; }
.wl-bar { flex: 1; min-width: 0; border-radius: 3px 3px 1px 1px; background: var(--ct-hyper); }
.wl-bar.strength { background: var(--ct-strength); } .wl-bar.transmute { background: var(--ct-transmute); }
.wl-bar.peak, .wl-bar.test { background: var(--ct-peak); }
.wl-bar.deload { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 3px, var(--ct-deload-s) 3px 6px); }
.wl-line { position: absolute; inset: 0 3px; width: calc(100% - 6px); height: 100%; pointer-events: none; z-index: 2; }
.wl-line polyline { fill: none; stroke: var(--gold, #8A5F0B); stroke-width: 1.4; vector-effect: non-scaling-stroke; }
.wl-figure figcaption { margin-top: 10px; font: 8.5px var(--mono); letter-spacing: .06em; color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px; }
.wl-xaxis { display: grid; grid-template-columns: repeat(13, minmax(0, 1fr)); gap: 2px; margin-top: 6px; padding: 0 3px; font: 8px var(--mono); color: var(--muted); text-align: center; }
.cond-num { display: flex; align-items: baseline; gap: 8px; margin-top: 18px; }
.cond-num b { font: 700 clamp(26px, 3vw, 34px) var(--mono); letter-spacing: -.03em; }
.cond-num i { font-style: normal; font-size: 9px; color: var(--muted); letter-spacing: .04em; }
.cond-band { position: relative; height: 96px; margin-top: 14px; border-bottom: 1px solid var(--hair); }
.cond-zone { position: absolute; left: 0; right: 0; bottom: 22.2%; height: 44.4%; background: color-mix(in srgb, var(--accent) 8%, transparent); border-top: 1px dashed color-mix(in srgb, var(--accent) 45%, transparent); border-bottom: 1px dashed color-mix(in srgb, var(--accent) 45%, transparent); }
.cond-bars { position: relative; display: flex; align-items: flex-end; gap: 2px; height: 100%; padding: 0 3px; }
.cond-bars i { flex: 1; border-radius: 3px 3px 0 0; background: var(--ct-hyper); opacity: .55; }
.cond-bars i.strength { background: var(--ct-strength); } .cond-bars i.transmute { background: var(--ct-transmute); }
.cond-bars i.peak, .cond-bars i.test { background: var(--ct-peak); } .cond-bars i.deload { background: var(--ct-deload); }
.cond-scale { display: flex; justify-content: space-between; margin-top: 4px; font: 8px var(--mono); color: var(--muted); }
.cond figcaption { display: block; line-height: 1.6; }
.wl-session { border: 1px solid var(--hair); border-radius: 14px; background: var(--panel); padding: 16px; }
.wl-session-head { display: flex; justify-content: space-between; gap: 8px; font: 8.5px var(--mono); letter-spacing: .1em; color: var(--muted); padding-bottom: 10px; border-bottom: 1px solid var(--hair); }
.wl-lift { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: baseline; gap: 10px; padding: 14px 0; border-bottom: 1px solid var(--soft); }
.wl-lift b { font: 700 13px var(--mono); letter-spacing: .04em; }
.wl-lift em { display: block; font-style: normal; font-size: 10px; color: var(--muted); margin-top: 3px; }
.wl-lift strong { font: 700 25px var(--mono); letter-spacing: -.03em; }
.wl-lift strong small { font-size: 10px; color: var(--muted); margin-left: 2px; }
.wl-lift i { font-style: normal; font: 10px var(--mono); color: var(--accent); }
.wl-total { display: flex; justify-content: space-between; align-items: baseline; padding-top: 14px; }
.wl-total span { font: 9px var(--mono); letter-spacing: .08em; color: var(--muted); }
.wl-total b { font: 700 28px var(--mono); letter-spacing: -.04em; }
.wl-total b small { font-size: 10px; color: var(--muted); }
.wl-note { padding-top: 6px; }
.wl-note-k { font: 8.5px var(--mono); letter-spacing: .14em; color: var(--accent); }
.wl-note p { margin-top: 8px; font-size: 13.5px; line-height: 1.8; color: var(--muted); max-width: 34em; }
.wl-note ul { margin-top: 12px; display: grid; gap: 6px; }
.wl-note li { font-size: 11px; color: var(--ink); padding-left: 14px; position: relative; }
.wl-note li::before { content: ''; position: absolute; left: 0; top: .55em; width: 5px; height: 5px; background: var(--accent); }
.wl-share-wrap { display: grid; place-items: center; padding: 10px 0; }
.wl-share-card { width: min(260px, 72%); aspect-ratio: 3 / 4; border-radius: 16px; background: var(--panel); border: 1px solid var(--hair); box-shadow: 0 22px 50px rgba(17, 17, 17, .16); padding: clamp(14px, 3.4vw, 20px); display: flex; flex-direction: column; }
.wl-share-k { font: 8px var(--mono); letter-spacing: .12em; color: var(--muted); }
.wl-share-lift { display: flex; justify-content: space-between; align-items: baseline; margin-top: clamp(12px, 3vh, 22px); }
.wl-share-lift span { font: 700 11px var(--mono); letter-spacing: .08em; }
.wl-share-lift b { font: 700 clamp(22px, 5.4vw, 30px) var(--mono); }
.wl-share-lift i { font-style: normal; font: 9px var(--mono); color: var(--accent); margin-left: 8px; }
.wl-share-total { margin-top: auto; padding-top: 12px; border-top: 1px solid var(--hair); display: flex; justify-content: space-between; align-items: baseline; }
.wl-share-total span { font: 8px var(--mono); letter-spacing: .1em; color: var(--muted); }
.wl-share-total b { font: 700 18px var(--mono); }
.wl-share-f { margin-top: 10px; font: 7.5px var(--mono); letter-spacing: .08em; color: var(--muted); }
.wl-ai { margin-top: 26px; border: 1px solid var(--hair); border-radius: 14px; overflow: hidden; }
.wl-ai-row { display: grid; grid-template-columns: 170px 160px minmax(0, 1fr); gap: 12px; padding: 16px; border-bottom: 1px solid var(--soft); align-items: baseline; }
.wl-ai-k { font: 8.5px var(--mono); letter-spacing: .12em; color: var(--accent); }
.wl-ai-state { font: 8.5px var(--mono); letter-spacing: .1em; color: var(--muted); }
.wl-ai-row p { font-size: 13px; line-height: 1.7; color: var(--ink); }
.wl-ai-row.muted p { color: var(--muted); }
.wl-ai-f { padding: 14px 16px; font: 10px var(--mono); color: var(--muted); }
.wl-browser { margin-top: 26px; border: 1px solid var(--hair); border-radius: 16px; overflow: hidden; background: var(--panel); box-shadow: 0 18px 44px rgba(17, 17, 17, .10); }
.wl-browser-bar { display: flex; align-items: center; gap: 6px; padding: 10px 12px; border-bottom: 1px solid var(--soft); background: var(--panel2); }
.wl-browser-bar i { width: 8px; height: 8px; border-radius: 50%; background: var(--soft); }
.wl-browser-bar span { margin-left: 8px; font: 9px var(--mono); color: var(--muted); }
.wl-browser-body { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 18px; padding: 18px; }
.wl-browser-side { border-right: 1px solid var(--soft); padding-right: 18px; }
.wl-browser-side b { font: 700 30px var(--mono); display: block; }
.wl-browser-side span { display: block; font: 9px var(--mono); letter-spacing: .1em; color: var(--muted); margin-top: 5px; }
.wl-browser-rows { display: grid; gap: 10px; }
.wl-browser-rows div { display: grid; grid-template-columns: 30px minmax(0, 1fr) 28px; align-items: center; gap: 8px; font: 9px var(--mono); color: var(--muted); }
.wl-browser-rows i { height: 10px; border-radius: 3px; background: var(--ct-strength); opacity: .7; }
.wl-browser-rows b { text-align: right; color: var(--ink); }
.wl-shots { position: relative; overflow: hidden; height: clamp(420px, 64vh, 640px); max-width: 860px; margin: 26px auto 0; touch-action: pan-y; cursor: grab; transition: transform .5s var(--ease); user-select: none; }
.wl-shots.grabbing { cursor: grabbing; transition: none; }
.wl-card { position: absolute; inset: 0; margin: auto; height: 100%; width: auto; aspect-ratio: 390 / 844; overflow: hidden; border: 1px solid var(--hair); border-radius: 18px; background: var(--panel2); box-shadow: 0 24px 60px rgba(17, 17, 17, .18); transition: transform .68s var(--ease), opacity .6s var(--ease); will-change: transform, opacity; pointer-events: none; }
.wl-card.front { box-shadow: 0 34px 80px rgba(17, 17, 17, .24); }
.wl-card img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: top center; -webkit-user-drag: none; }
.wl-slider { position: relative; display: flex; width: min(184px, 48vw); height: 22px; margin: 18px auto 0; }
.wl-slider-rail { position: absolute; left: 0; right: 0; top: 10px; height: 1px; background: var(--hair); }
.wl-slider-thumb { position: absolute; top: 8px; height: 5px; background: var(--ink); transition: left .38s var(--ease), width .38s var(--ease); }
.wl-slider button { position: relative; z-index: 2; flex: 1; min-width: 0; height: 22px; min-height: 22px; padding: 0; border: 0; border-radius: 0; background: none; }
.wl-caption { text-align: center; margin: 14px auto 0; max-width: 34em; }
.wl-cap-name { font: 9.5px var(--mono); letter-spacing: .13em; text-transform: uppercase; color: var(--ink); }
.wl-cap-desc { margin: 5px auto 0; font-family: var(--serif); font-size: 13px; line-height: 1.7; color: var(--muted); max-width: 38ch; }
.wl-people { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--soft); border: 1px solid var(--soft); border-radius: 14px; overflow: hidden; margin-top: 26px; }
.wl-person { background: var(--panel); padding: clamp(16px, 2.4vw, 24px); }
.wl-person-n { font: 8.5px var(--mono); letter-spacing: .14em; color: var(--accent); }
.wl-person h3 { font-size: clamp(20px, 2vw, 24px); margin-top: 8px; }
.wl-person p { margin-top: 8px; font-size: 12px; line-height: 1.8; color: var(--muted); }
.wl-person ul { margin-top: 14px; display: grid; gap: 5px; }
.wl-person li { font: 9px var(--mono); letter-spacing: .05em; color: var(--ink); padding-left: 12px; position: relative; }
.wl-person li::before { content: ''; position: absolute; left: 0; top: .5em; width: 4px; height: 4px; background: var(--accent); }
.wl-chain { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--soft); border: 1px solid var(--soft); border-radius: 14px; overflow: hidden; margin-top: 26px; }
.wl-link { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 12px; background: var(--panel); padding: 18px; }
.wl-link > span { font: 9px var(--mono); color: var(--accent); }
.wl-link b { font: 700 10px var(--mono); letter-spacing: .1em; }
.wl-link p { margin-top: 6px; font-size: 12px; line-height: 1.7; color: var(--muted); }
.wl-enter { padding-bottom: clamp(30px, 5vh, 54px); }
.wl-enter h2 { font-size: clamp(30px, 4vw, 46px); }
.wl-enter-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
.wl-cta { display: inline-flex; flex-direction: column; justify-content: center; min-height: 52px; padding: 0 20px; border: 1px solid var(--ink); border-radius: 2px; background: var(--ink); color: var(--bg); font: 700 11px var(--mono); letter-spacing: .06em; text-decoration: none; }
.wl-cta:hover { background: var(--accent); border-color: var(--accent); }
.wl-cta.ghost { background: transparent; color: var(--muted); border-color: var(--soft); cursor: default; }
.wl-cta.ghost small { font-size: 8px; letter-spacing: .12em; margin-top: 2px; }
.wl-enter-f { margin-top: 16px; font: 10px var(--mono); color: var(--muted); }
.wl-enter-f a { border-bottom: 1px solid var(--hair); color: var(--ink); }
.wl-foot { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; border-top: 1px solid var(--hair); padding: 26px 0 40px; }
.wl-foot-brand { display: flex; align-items: baseline; gap: 8px; }
.wl-bean { width: 18px; height: 18px; color: var(--accent); }
.wl-foot-brand b { font-family: var(--serif); font-style: italic; font-size: 18px; }
.wl-foot-brand span { font: 8.5px var(--mono); letter-spacing: .14em; color: var(--muted); text-transform: uppercase; }
.wl-foot-links { display: flex; flex-wrap: wrap; gap: 16px; font: 9px var(--mono); letter-spacing: .08em; color: var(--muted); }
.wl-foot-links a { border-bottom: 1px solid var(--soft); }
.js .rv { opacity: 0; transform: translateY(14px); }
.js .rv.in { opacity: 1; transform: none; transition: opacity .6s var(--ease), transform .7s var(--ease); }
@media (max-width: 880px) {
  .wl-hero-grid, .wl-two, .wl-people, .wl-chain, .wl-ai-row, .wl-browser-body { grid-template-columns: minmax(0, 1fr); }
  .wl-hero-grid { gap: 22px; }
  .wl-browser-side { border-right: 0; border-bottom: 1px solid var(--soft); padding: 0 0 14px; }
  .wl-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
  .wl-shots { height: clamp(360px, 62vh, 540px); }
  .wl-note p { font-size: 12.5px; }
  .wl-ai-row { gap: 6px; }
}
@media (prefers-reduced-motion: reduce) {
  .wl-shots, .wl-card, .wl-slider-thumb, .js .rv, .js .rv.in { transition: none; opacity: 1; transform: none; }
}
</style>
