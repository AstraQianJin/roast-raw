<script setup>
import { RouterLink } from 'vue-router';
</script>

<template>
  <main class="about">
    <section class="about-hero">
      <div class="eyebrow">ABOUT · ONE LEDGER, ONE SERVER</div>
      <h1>What this journal is, and what it does with your numbers.</h1>
      <p class="lede">Roast Raw is a training journal for one lifter. It holds one cycle at a time, the sets you actually record, and the statistics derived from those two. There is no feed, no follower count and no second copy of your data somewhere else.</p>
    </section>

    <section class="about-grid">
      <article>
        <span class="section-label">01 / WHAT IT DOES</span>
        <h2>Plan in, sets out.</h2>
        <p>The cycle arrives as a plan file: weeks, sessions, prescribed sets, loads and percentages. You record what you lifted. Everything on the cycle, assay and vault screens is computed from those two inputs on the server, then drawn in the browser. Nothing is inferred from a phone sensor and nothing is synced from a wearable.</p>
      </article>
      <article>
        <span class="section-label">02 / WHO RUNS IT</span>
        <h2>One owner, one small host.</h2>
        <p>This is a personal project, not a company. One server runs the API and serves this page. There is no support team behind it, so if something breaks the fix comes from the same person who wrote the plan file.</p>
      </article>
      <article>
        <span class="section-label">03 / WHAT IS STORED</span>
        <h2>One SQLite file.</h2>
        <p>The plan, your logged rows and their full save history, recovery and body readings, and competition attempts. Dates are fixed to Asia/Shanghai. Every migration takes a snapshot first.</p>
      </article>
      <article>
        <span class="section-label">04 / WHAT LEAVES THE SERVER</span>
        <h2>Nothing by default.</h2>
        <p>No analytics, no third-party scripts, no web fonts fetched from another domain, and no model provider. Nothing you record is sent anywhere; the only network call this page makes is to its own server.</p>
      </article>
      <article>
        <span class="section-label">05 / ACCESS</span>
        <h2>A code sets the tier.</h2>
        <p>Registration needs an invite code. Each tier includes the ones below it. A timed tier lapses on its own clock and you drop to the tier underneath; your rows stay where they are. Reading your own records is open on every tier. Saving recovery, body metrics, meet attempts or derived views needs the tier that carries them.</p>
      </article>
      <article>
        <span class="section-label">06 / YOUR EXITS</span>
        <h2>Export and delete, both explicit.</h2>
        <p>The vault exports your recorded rows as CSV and the whole cycle review as JSON. Deleting a cycle needs a prepared token and a typed confirmation; the active cycle refuses both. Exporting never deletes anything.</p>
      </article>
    </section>

    <section class="about-close">
      <p class="annotation">Written copy on this page describes behaviour that the tests exercise. If a sentence here stops being true, it is a bug in this page.</p>
      <RouterLink to="/welcome" class="inline-link">Back to the front page →</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.about { max-width: 1080px; margin: 0 auto; padding: 28px 18px 48px; }
.about-hero { border-bottom: 1px solid var(--line); padding-bottom: 18px; }
.eyebrow { font-family: var(--mono); font-size: 8.5px; letter-spacing: .18em; text-transform: uppercase; color: var(--muted); }
h1 { margin: 10px 0 8px; font-family: var(--serif); font-size: clamp(24px, 5.2vw, 40px); line-height: 1.14; letter-spacing: -.01em; }
.lede { margin: 0; max-width: 62ch; color: var(--ink-soft); font-size: 15px; line-height: 1.55; }
.about-grid { display: grid; gap: 14px; margin: 18px 0; grid-template-columns: 1fr; }
@media (min-width: 720px) { .about-grid { grid-template-columns: 1fr 1fr; } }
article { background: var(--card-grad); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--card-shadow); padding: 16px; min-width: 0; }
.section-label { font-family: var(--mono); font-size: 8.5px; letter-spacing: .16em; color: var(--muted); }
h2 { margin: 8px 0 6px; font-family: var(--serif); font-size: 20px; line-height: 1.2; }
p { margin: 0; font-size: 14px; line-height: 1.6; color: var(--ink-soft); }
.about-close { border-top: 1px solid var(--line); padding-top: 14px; display: grid; gap: 8px; }
.annotation { font-family: var(--mono); font-size: 10px; letter-spacing: .04em; color: var(--muted); }
.inline-link { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--ink); }
</style>
