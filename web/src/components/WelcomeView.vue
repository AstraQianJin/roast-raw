<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';
import packageInfo from '../../package.json';
const [major, , patch] = packageInfo.version.split('.');
const releaseVersion = `${major}.${patch.padStart(2, '0')}`;

const root = ref(null);
const index = ref(0);
let cleanup = () => {};

const shots = [
  { src: '/shots/today-390-light.png', k: 'TODAY', title: 'Loads, capacity and the working body.' },
  { src: '/shots/analysis-390-light.png', k: 'ANALYSIS', title: 'Every contribution, weighted and mapped.' },
];
function step(delta) { index.value = (index.value + delta + shots.length) % shots.length; }
function offset(i) { const n = shots.length; let d = (i - index.value + n) % n; if (d > n / 2) d -= n; return d; }
function cardStyle(i) {
  const o = offset(i); const a = Math.abs(o);
  return {
    transform: `translateX(${o * 56}%) scale(${1 - Math.min(a, 3) * .07}) rotate(${o * 2.2}deg)`,
    opacity: a > 2 ? 0 : 1 - a * .26,
    zIndex: 20 - a,
    filter: a ? `blur(${(a * 1.1).toFixed(1)}px)` : 'none',
  };
}

const features = [
  { n: '01', k: 'THE PLAN', title: 'A calendar that does not move.', copy: 'Fixed weeks in Asia/Shanghai. Phase-colored blocks, deload and test weeks marked. Missed sessions stay missed — nothing slides.' },
  { n: '02', k: 'THE LOG', title: 'Actual sets, kept separate.', copy: 'Recorded sets replace their planned rows. Explicit zero sets count as skipped. Prescribed and actual never blur into one number.' },
  { n: '03', k: 'CAPACITY', title: 'MEV–MRV you can see.', copy: 'Working sets, SBD equivalents and reference bands on one track. Bands inform; they never hand down red-green verdicts.' },
  { n: '04', k: 'MUSCLE MAP', title: 'Sixteen leaves, one body.', copy: 'Weighted contributions per muscle, front and back. Tap any leaf to inspect its sets, range and share of the week.' },
  { n: '05', k: 'ARCHIVE', title: 'Every cycle recoverable.', copy: 'Past plans and logs stay readable. Review exports carry the questionnaire, the prompt and the numbers behind them.' },
  { n: '06', k: 'OUTLOOK', title: 'Readiness into prescription.', copy: 'A seven-step questionnaire scores recovery, arousal and fuel. The coefficient adjusts the next prescription — with your consent.' },
];
const demoWeeks = ['hyper', 'hyper', 'hyper', 'hyper', 'strength', 'strength', 'strength', 'deload', 'transmute', 'transmute', 'peak', 'deload', 'test'];

onMounted(() => {
  const el = root.value;
  if (!el || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  el.classList.add('js');
  const ease = 'cubic-bezier(.22,1,.36,1)';
  const rv = [...el.querySelectorAll('.rv')];
  const groups = [...el.querySelectorAll('[data-stagger]')];
  const hero = el.querySelector('.wl-hero');
  const deck = el.querySelector('.wl-grid');
  const cards = deck ? [...deck.children] : [];
  const seq = {};
  rv.forEach(node => {
    const section = node.closest('section');
    const key = section ? section.id || 's' : 'x';
    seq[key] = seq[key] || 0;
    node.dataset.d = `${Math.min(seq[key], 3) * 90}ms`;
    seq[key] += 1;
  });
  groups.forEach(group => [...group.children].forEach((child, index) => child.style.setProperty('--d', `${index * 70}ms`)));
  let raf = 0;
  let ticking = false;
  const frame = () => {
    ticking = false;
    const vh = window.innerHeight;
    for (let i = rv.length - 1; i >= 0; i -= 1) {
      const rect = rv[i].getBoundingClientRect();
      if (rect.top < vh * 0.92 && rect.bottom > -40) {
        rv[i].style.transitionDelay = rv[i].dataset.d || '0ms';
        rv[i].classList.add('in');
        rv.splice(i, 1);
      }
    }
    for (let i = groups.length - 1; i >= 0; i -= 1) {
      const rect = groups[i].getBoundingClientRect();
      if (rect.top < vh * 0.92 && rect.bottom > -40) {
        groups[i].classList.add('in');
        groups.splice(i, 1);
      }
    }
    if (deck && cards.length && matchMedia('(max-width:760px)').matches) {
      deck.classList.add('deck');
      const tops = [];
      const bots = [];
      cards.forEach(card => { const rect = card.getBoundingClientRect(); tops.push(rect.top); bots.push(rect.bottom); });
      let depth = 0;
      for (let i = cards.length - 1; i >= 0; i -= 1) {
        const cov = i < cards.length - 1 ? Math.max(0, Math.min(1, (bots[i] - tops[i + 1]) / Math.max(1, bots[i] - tops[i]))) : 0;
        const fade = cov * cov * (3 - 2 * cov);
        const inner = cards[i].firstElementChild;
        if (inner) {
          inner.style.setProperty('--sc', (1 - Math.min(.09, .022 * depth)).toFixed(3));
          inner.style.setProperty('--ty', `${(-Math.min(9, 2 * depth)).toFixed(2)}px`);
          inner.style.setProperty('--dim', Math.min(.24, .4 * cov).toFixed(3));
          inner.style.setProperty('--op', Math.max(.12, 1 - .85 * fade).toFixed(3));
        }
        const pin = 86 + i * 16;
        let p = 1 - (tops[i] - pin) / 220;
        p = p < 0 ? 0 : p > 1 ? 1 : p;
        depth += p;
      }
    } else if (deck) deck.classList.remove('deck');
    const max = document.documentElement.scrollHeight - vh;
    el.style.setProperty('--prog', max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)).toFixed(4) : '0');
  };
  const onScroll = () => { if (!ticking) { ticking = true; raf = requestAnimationFrame(frame); } };
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  requestAnimationFrame(() => requestAnimationFrame(() => hero && hero.classList.add('in')));
  onScroll();

  cleanup = () => {
    cancelAnimationFrame(raf);
    window.removeEventListener('scroll', onScroll);
    window.removeEventListener('resize', onScroll);
    document.documentElement.classList.remove('wl-open');
  };
});
onBeforeUnmount(() => cleanup());
</script>

<template>
  <div ref="root" class="welcome" data-testid="welcome">
    <div class="wl-progress" aria-hidden="true"></div>
    <section id="wl-top" class="wl-hero">
      <div class="wl-hero-grid">
        <div class="wl-copy">
          <p class="eyebrow">ROAST RAW · POWERLIFTING TRAINING JOURNAL</p>
          <h1><span class="l"><span class="li">Every set,</span></span><span class="l"><span class="li"><em>accounted for.</em></span></span></h1>
        </div>
        <div class="wl-visual">
          <div class="hv" aria-label="Illustrative product preview">
            <div class="hv-bar"><span>ROAST RAW · <b>W05 · DAY B</b></span><span>PREVIEW</span></div>
            <div class="hv-stack">
              <div class="hv-card" style="--i:0"><span class="hv-k">SQUAT · TOP</span><div class="hv-h"><b>140<small>kg</small></b><span>85%</span></div><div class="hv-sets"><i class="ok">5</i><i class="ok">5</i><i class="ok">5</i><i>3</i></div></div>
              <div class="hv-card" style="--i:1"><span class="hv-k">BENCH · TOP</span><div class="hv-h"><b>102.5<small>kg</small></b><span>82%</span></div><div class="hv-sets"><i class="ok">4</i><i class="ok">4</i><i>4</i><i>4</i></div></div>
              <div class="hv-card wide" style="--i:2"><span class="hv-k">CYCLE · 13 WEEKS</span><div class="hv-weeks"><i v-for="(phase, index) in demoWeeks" :key="index" :class="['ct', phase, { on: index === 4 }]"></i></div><div class="hv-meta"><span>HYPER → STRENGTH → PEAK</span><b>W05</b></div></div>
              <div class="hv-card wide" style="--i:3"><span class="hv-k">READINESS · REC</span><svg class="hv-spark" viewBox="0 0 200 30" preserveAspectRatio="none" aria-hidden="true"><polyline points="0,22 25,18 50,20 75,12 100,14 125,8 150,10 175,5 200,7"/></svg><div class="hv-meta"><span>SEVEN-STEP QUESTIONNAIRE</span><b>1.04</b></div></div>
            </div>
          </div>
        </div>
        <p class="wl-lede">A fixed-calendar powerlifting journal. Prescribed loads, actual sets, readiness and working-set capacity — kept separate, kept honest, readable at a glance.</p>
        <p class="wl-fine">Single-user release {{ releaseVersion }} · Records live on your server · No offline cache, no sync service.</p>
      </div>
      <div class="wl-facts rv" data-stagger>
        <div class="wl-fact"><b>SBD</b><em>Squat · Bench · Deadlift</em></div>
        <div class="wl-fact"><b>MEV–MRV</b><em>Reference bands, not verdicts</em></div>
        <div class="wl-fact"><b>FIXED</b><em>Asia/Shanghai calendar</em></div>
        <div class="wl-fact"><b>RAW</b><em>Actual sets only</em></div>
      </div>
    </section>

    <section id="wl-features" class="wl-sec">
      <div class="wl-sec-head rv"><span class="section-kicker">THE INSTRUMENTS</span><h2>One journal. Six instruments.</h2><p class="wl-deck">Each screen does one job and shows its numbers. Nothing is gamified, nothing is hidden behind a score.</p></div>
      <div class="wl-grid">
        <article v-for="(feature, index) in features" :key="feature.n" class="wl-cap" :style="{ '--i': index }">
          <div class="wl-cap-in">
            <span class="wl-n">{{ feature.n }} · {{ feature.k }}</span>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.copy }}</p>
          </div>
        </article>
      </div>
    </section>

    <section id="wl-screens" class="wl-sec">
      <div class="wl-sec-head rv"><span class="section-kicker">AS IT RUNS</span><h2>The journal, on the record.</h2><p class="wl-deck">Captured from the automated regression at phone width. Use the arrows to move through the set.</p></div>
      <div class="wl-shots rv" data-stagger aria-roledescription="carousel" aria-label="Product screenshots">
        <button type="button" class="wl-arrow left" aria-label="Previous screenshot" @click="step(-1)">‹</button>
        <div class="wl-shots-track">
          <figure v-for="(shot, i) in shots" :key="shot.src" class="wl-card" :class="{ front: offset(i) === 0 }" :style="cardStyle(i)" :aria-hidden="offset(i) !== 0">
            <img :src="shot.src" :alt="`${shot.k} page screenshot`" loading="lazy">
          </figure>
        </div>
        <button type="button" class="wl-arrow right" aria-label="Next screenshot" @click="step(1)">›</button>
      </div>
      <p class="wl-deck-cap"><b>{{ shots[index].k }}</b><span>{{ shots[index].title }}</span></p>
      <div class="wl-dots"><button v-for="(shot, i) in shots" :key="shot.src" type="button" :aria-label="`Show ${shot.k}`" :aria-current="index === i ? 'true' : 'false'" @click="index = i"></button></div>
    </section>

    <section id="wl-enter" class="wl-sec wl-enter">
      <div class="rv">
        <span class="section-kicker">RELEASE {{ releaseVersion }}</span>
        <h2>Ready when you are.</h2>
        <p class="wl-deck">The plan is loaded, the calendar is fixed, the ledger is open.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.welcome { --ease: cubic-bezier(.22, 1, .36, 1); position: relative; }
.welcome h1, .welcome h2, .welcome h3 { font-family: var(--serif); font-weight: 400; text-transform: none; letter-spacing: -.035em; line-height: 1.03; }
.welcome h1 { font-size: clamp(42px, 8vw, 68px); }
.welcome button, .welcome .wl-btn { font-family: var(--sans); font-weight: 600; text-transform: none; letter-spacing: 0; }
.wl-progress { position: fixed; top: 0; left: 0; right: 0; height: 2px; background: var(--accent); transform-origin: 0 50%; transform: scaleX(var(--prog, 0)); z-index: 30; pointer-events: none; }
.wl-hero { padding-top: clamp(20px, 4vh, 44px); }
.wl-hero-grid { display: grid; grid-template-columns: minmax(0, 1.02fr) minmax(0, .98fr); grid-template-areas: 'copy visual' 'lede visual' 'cta visual' 'fine visual'; column-gap: clamp(24px, 4vw, 54px); align-items: center; }
.wl-copy { grid-area: copy; min-width: 0; }
.wl-visual { grid-area: visual; min-width: 0; }
.wl-lede { grid-area: lede; margin-top: 18px; max-width: 40em; color: var(--muted); font-size: clamp(14px, 1.3vw, 16px); line-height: 1.85; }
.wl-cta { grid-area: cta; display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
.wl-fine { grid-area: fine; margin-top: 14px; font-size: 11px; line-height: 1.75; color: var(--muted); }
.welcome h1 { margin-top: 14px; max-width: 18em; }
.welcome h1 .l { display: block; overflow: clip; padding-bottom: .1em; margin-bottom: -.1em; }
.welcome h1 .li { display: block; }
.welcome h1 em { font-style: normal; color: var(--accent); }
.js .wl-hero h1 .li { transform: translateY(112%); }
.js .wl-hero.in h1 .li { transform: none; transition: transform .9s var(--ease); }
.js .wl-hero.in h1 .l:nth-child(2) .li { transition-delay: .11s; }
.js .wl-hero .wl-lede, .js .wl-hero .wl-cta, .js .wl-hero .wl-fine { opacity: 0; transform: translateY(10px); }
.js .wl-hero.in .wl-lede { opacity: 1; transform: none; transition: opacity .6s var(--ease) .14s, transform .7s var(--ease) .14s; }
.js .wl-hero.in .wl-cta { opacity: 1; transform: none; transition: opacity .6s var(--ease) .2s, transform .7s var(--ease) .2s; }
.js .wl-hero.in .wl-fine { opacity: 1; transform: none; transition: opacity .6s var(--ease) .26s, transform .7s var(--ease) .26s; }
.js .wl-hero .hv-card { opacity: 0; transform: translateY(12px); }
.js .wl-hero.in .hv-card { opacity: 1; transform: none; transition: opacity .55s var(--ease), transform .6s var(--ease); transition-delay: calc(.26s + var(--i, 0) * 90ms); }
.wl-btn { display: inline-flex; align-items: center; gap: 9px; min-height: 50px; padding: 0 18px; border: 1px solid var(--accent); background: var(--accent); color: var(--on-accent); font-weight: 700; font-size: 13px; border-radius: 2px; transition: background-color .2s, border-color .2s, transform .2s; }
.wl-btn:hover { background: color-mix(in srgb, var(--accent) 86%, #000); border-color: color-mix(in srgb, var(--accent) 86%, #000); }
.wl-btn:active { transform: translateY(1px); }
.wl-btn .ar { font-family: var(--mono); font-size: 14px; line-height: 1; }
.wl-btn.ghost { background: transparent; border-color: var(--line); color: var(--ink); }
.wl-btn.ghost:hover { border-color: var(--ink); background: var(--panel2); }
.hv { border: 1px solid var(--line); background: var(--panel); padding: 14px; box-shadow: var(--card-shadow); }
.hv-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0 2px 10px; font-family: var(--mono); font-size: 9px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.hv-bar b { color: var(--accent); font-weight: 700; }
.hv-stack { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.hv-card { border: 1px solid var(--line2); background: var(--panel2); padding: 11px 12px; min-width: 0; }
.hv-card.wide { grid-column: 1 / -1; }
.hv-k { font-family: var(--mono); font-size: 8.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.hv-h { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-top: 7px; font-size: 11.5px; color: var(--muted); white-space: nowrap; }
.hv-h b { font-family: var(--mono); font-size: 17px; letter-spacing: -.02em; color: var(--ink); }
.hv-h small { font-size: 9px; margin-left: 2px; color: var(--muted); }
.hv-sets { display: flex; gap: 5px; margin-top: 8px; }
.hv-sets i { flex: 1; height: 22px; display: flex; align-items: center; justify-content: center; border: 1px solid var(--line2); font-family: var(--mono); font-style: normal; font-size: 10px; color: var(--muted); }
.hv-sets i.ok { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
.hv-spark { width: 100%; height: 30px; margin-top: 8px; display: block; }
.hv-spark polyline { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.hv-weeks { display: flex; gap: 3px; margin-top: 9px; }
.hv-weeks i { flex: 1; height: 16px; background: var(--line-soft); }
.hv-weeks i.ct.hyper { background: var(--ct-hyper); }
.hv-weeks i.ct.strength { background: var(--ct-strength); }
.hv-weeks i.ct.transmute { background: var(--ct-transmute); }
.hv-weeks i.ct.peak, .hv-weeks i.ct.test { background: var(--ct-peak); }
.hv-weeks i.ct.deload { background: repeating-linear-gradient(135deg, var(--ct-deload) 0 3px, var(--ct-deload-s) 3px 6px); }
.hv-weeks i.on { outline: 2px solid var(--ink); outline-offset: 1px; }
.hv-meta { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-top: 8px; font-family: var(--mono); font-size: 8.5px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
.hv-meta b { color: var(--ink); font-weight: 700; }
.wl-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; background: var(--line2); border: 1px solid var(--line2); margin-top: clamp(28px, 5vh, 46px); }
.wl-fact { background: var(--bg); padding: 14px 16px; min-width: 0; }
.wl-fact b { display: block; font-family: var(--mono); font-size: clamp(16px, 2.2vw, 22px); line-height: 1.1; letter-spacing: -.04em; }
.wl-fact em { display: block; margin-top: 4px; font-style: normal; font-size: 10.5px; letter-spacing: .04em; color: var(--muted); text-transform: uppercase; }
.wl-sec { padding-top: clamp(48px, 8vh, 86px); padding-bottom: clamp(24px, 4vh, 44px); border-top: 1px solid var(--line); margin-top: clamp(36px, 6vh, 64px); }
.wl-sec-head { margin-bottom: clamp(22px, 4vh, 34px); }
.wl-sec-head h2 { margin-top: 10px; max-width: 22em; }
.wl-deck { max-width: 46em; color: var(--muted); font-size: clamp(13px, 1.25vw, 15.5px); line-height: 1.85; margin-top: 10px; }
.wl-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--line2); border: 1px solid var(--line2); }
.wl-cap { background: var(--bg); min-width: 0; }
.wl-cap-in { display: block; padding: clamp(18px, 2.4vw, 26px); }
.wl-n { font-family: var(--mono); font-size: 10px; letter-spacing: .1em; color: var(--accent); }
.wl-cap h3 { margin-top: 8px; font-size: clamp(18px, 1.7vw, 22px); }
.wl-cap p { margin-top: 7px; font-size: 12.5px; line-height: 1.8; color: var(--muted); }
.js .rv { clip-path: inset(0 0 100% 0); }
.js .rv.in { clip-path: inset(-6% -6% -6% -6%); transition: clip-path .7s var(--ease); }
@supports not (clip-path: inset(0 0 0 0)) { .js .rv, .js .rv.in { clip-path: none; } }
.js [data-stagger] > * { opacity: 0; transform: translateY(14px); }
.js [data-stagger].in > * { opacity: 1; transform: none; transition: opacity .55s var(--ease), transform .65s var(--ease); transition-delay: var(--d, 0ms); }
.wl-enter { text-align: left; }
.wl-enter .wl-cta { margin-top: 20px; }

@media (max-width: 880px) {
  .wl-hero-grid { grid-template-columns: minmax(0, 1fr); grid-template-areas: 'copy' 'visual' 'lede' 'fine'; row-gap: 18px; }
  .wl-lede { margin-top: 0; }
}
@media (max-width: 760px) {
  .wl-grid.deck { display: block; background: none; border: 0; }
  .wl-grid.deck .wl-cap { position: sticky; top: calc(86px + var(--i, 0) * 16px); margin: 0 0 14px; padding: 0; background: none; border: 0; }
  .wl-grid.deck .wl-cap:last-child { margin-bottom: 0; }
  .wl-grid.deck .wl-cap-in { position: relative; padding: clamp(18px, 4.6vw, 24px); border: 1px solid var(--line); background: var(--panel); box-shadow: 0 -8px 16px rgba(17, 17, 17, .06), 0 10px 22px rgba(17, 17, 17, .09); transform-origin: 50% 0; transform: translate3d(0, var(--ty, 0px), 0) scale(var(--sc, 1)); will-change: transform; overflow: hidden; }
  .wl-grid.deck .wl-cap-in::after { content: ''; position: absolute; inset: 0; background: var(--panel); opacity: var(--dim, 0); pointer-events: none; }
  .wl-grid.deck .wl-cap-in > * { position: relative; z-index: 1; opacity: var(--op, 1); }
}
@media (max-width: 560px) {
  .wl-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 400px) {
  .hv-stack { grid-template-columns: minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .wl-progress { display: none; }
  .wl-card { transition: none; }
  .js .rv, .js .rv.in { clip-path: none; }
  .js [data-stagger] > *, .js .wl-hero .wl-lede, .js .wl-hero .wl-fine, .js .wl-hero .hv-card, .js .wl-hero h1 .li { opacity: 1; transform: none; transition: none; }
}

/* Screenshot deck: cards fan behind the active one and cross-fade on switch. */
.wl-shots { position: relative; overflow: hidden; max-width: 860px; margin: 0 auto; }
.wl-shots-track { position: relative; height: clamp(340px, 58vh, 600px); }
.wl-card { position: absolute; inset: 0; margin: auto; height: 100%; width: auto; aspect-ratio: 390 / 844; overflow: hidden; border: 1px solid var(--line); background: var(--panel2); box-shadow: 0 18px 44px rgba(17, 17, 17, .16); transition: transform .62s var(--ease), opacity .52s var(--ease), filter .52s var(--ease); will-change: transform, opacity; }
.wl-card.front { box-shadow: 0 26px 60px rgba(17, 17, 17, .22); }
.wl-card img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: top center; }
.wl-card::after { content: ''; position: absolute; inset: 0; pointer-events: none; background: linear-gradient(180deg, rgba(17, 17, 17, 0) 62%, rgba(17, 17, 17, .10) 100%); }
.wl-arrow { position: absolute; top: 50%; transform: translateY(-50%); z-index: 30; width: 44px; min-width: 44px; height: 44px; padding: 0; border: 1px solid var(--line2); border-radius: 50%; background: var(--panel); color: var(--ink); font-size: 20px; line-height: 1; }
.wl-arrow.left { left: 2px; }
.wl-arrow.right { right: 2px; }
.wl-arrow:hover { border-color: var(--ink); background: var(--panel2); }
.wl-deck-cap { display: flex; align-items: baseline; justify-content: center; gap: 10px; margin-top: 18px; font-family: var(--mono); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); text-align: center; }
.wl-deck-cap b { color: var(--ink); }
.wl-dots { display: flex; justify-content: center; gap: 6px; margin-top: 12px; }
.wl-dots button { width: 26px; height: 26px; min-height: 26px; padding: 0; border: 0; border-radius: 0; background: none; position: relative; }
.wl-dots button::before { content: ''; position: absolute; inset: 10px 3px; background: var(--line-soft); }
.wl-dots button[aria-current='true']::before { background: var(--accent); }
@media (max-width: 760px) {
  .wl-shots-track { height: clamp(320px, 54vh, 460px); }
  .wl-arrow { width: 38px; min-width: 38px; height: 38px; }
}
</style>