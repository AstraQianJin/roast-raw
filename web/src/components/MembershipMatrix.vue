<script setup>
// Membership matrix (0.36 / R6). Every tier name, price, billing string and capability
// comes from web/src/membership.json, which server/tools/export_membership.py writes
// from server/app/membership.py. Never type a second copy of this table here.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import membership from '../membership.json';
import BeanMark from './BeanMark.vue';

const tiers = membership.tiers;
const columns = membership.columns; // Free / Lite / Plus / Pro — Ultra never takes a column.
const pricing = membership.pricing;
const capabilities = membership.capabilities;
const deviceLimit = membership.device_limit;
const TIER_LABEL = { free: 'Free', lite: 'Lite', plus: 'Plus', pro: 'Pro', ultra: 'Ultra' };
const BEANS = { free: 0, lite: 1, plus: 2, pro: 3 };
const rank = tier => tiers.indexOf(tier);

// Rows: one device row plus every capability, each carrying the tier where it starts.
const rows = [
  { id: 'devices', label: 'Signed-in devices', note: `${deviceLimit} per account`, min: 'free' },
  ...capabilities.map(item => ({ id: item.id, label: item.label, note: item.note || '', min: item.min_tier })),
];
const VISIBLE_ROWS = 6; // devices + the five free capabilities, per the 0.36 spec.
const expanded = ref(false);
const shownRows = computed(() => expanded.value ? rows : rows.slice(0, VISIBLE_ROWS));

const included = (row, tier) => rank(tier) >= rank(row.min);
const tagFor = row => row.min === 'free' ? 'ALL TIERS' : `${TIER_LABEL[row.min].toUpperCase()}+`;

const currency = ref('CNY');
const price = tier => {
  const item = pricing[tier];
  if (item.usd === null) return '—';
  const symbol = currency.value === 'CNY' ? `¥${item.cny}` : `US$${item.usd}`;
  return item.period ? `${symbol}${item.period}` : symbol;
};
const billing = tier => pricing[tier].billing;
const billingNote = tier => pricing[tier].billing_text;

// Column focus: hover or keyboard focus lights the whole tier column.
const focus = ref('');
const focusedClass = tier => focus.value === tier ? 'is-focus' : '';
const cardIndex = ref(0);
const activeTier = computed(() => columns[cardIndex.value] || 'free');

const root = ref(null);
const head = ref(null);
const stage = ref(null);
const rail = ref(null);
let cleanups = [];

onMounted(() => {
  const el = root.value;
  if (!el) return;
  // Real header height, measured rather than assumed: sticky covers read it.
  const measure = () => {
    const bar = document.querySelector('.wl-top');
    document.documentElement.style.setProperty('--topH', bar ? `${bar.offsetHeight}px` : '0px');
  };
  measure();
  window.addEventListener('resize', measure, { passive: true });
  cleanups.push(() => window.removeEventListener('resize', measure));
  const bar = document.querySelector('.wl-top');
  if (bar && 'ResizeObserver' in window) {
    const ro = new ResizeObserver(measure);
    ro.observe(bar);
    cleanups.push(() => ro.disconnect());
  }

  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const markIn = (nodes, offset) => nodes.forEach((node, i) => {
    node.style.setProperty('--i', String(i));
    node.classList.add('in');
  });
  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      if (entry.target === stage.value) stage.value.classList.add('in');
      if (entry.target === rail.value) markIn([...rail.value.querySelectorAll('.mm-card')], 0);
      if (entry.target === el) {
        const checks = [...el.querySelectorAll('.mm-check')];
        checks.forEach((node, i) => {
          node.style.setProperty('--d', `${Math.floor(i / 4) * 30}ms`);
          node.classList.add('in');
        });
      }
      io.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -10% 0px', threshold: 0.15 });
  [el, stage.value, rail.value, head.value].filter(Boolean).forEach(node => io.observe(node));
  cleanups.push(() => io.disconnect());

  // The card strip snaps itself (CSS scroll-snap); this only tracks which tier is
  // centred so the capability rows below can emphasise that column.
  const onScroll = () => {
    if (!rail.value) return;
    const cards = [...rail.value.querySelectorAll('.mm-card')];
    const mid = rail.value.getBoundingClientRect().left + rail.value.clientWidth / 2;
    let best = 0;
    cards.forEach((card, i) => {
      const box = card.getBoundingClientRect();
      const d = Math.abs(box.left + box.width / 2 - mid);
      if (d < Math.abs(cards[best].getBoundingClientRect().left + cards[best].getBoundingClientRect().width / 2 - mid)) best = i;
    });
    cardIndex.value = best;
  };
  rail.value?.addEventListener('scroll', onScroll, { passive: true });
  cleanups.push(() => rail.value?.removeEventListener('scroll', onScroll));

  if (reduce) {
    el.classList.add('mm-reduced');
    el.querySelectorAll('.mm-check').forEach(node => node.classList.add('in'));
    stage.value?.classList.add('in');
  }
});
onBeforeUnmount(() => cleanups.forEach(fn => fn()));
</script>

<template>
  <section id="membership" ref="root" class="mm" data-testid="membership" aria-labelledby="mm-title">
    <header class="mm-head rv">
      <span class="wl-num">09 /</span>
      <h2 id="mm-title">Five tiers, with Free as the base.</h2>
      <p class="mm-lede">An invite code sets your tier. Higher tiers include everything below them. When a tier lapses you drop a tier, not your data.</p>
    </header>

    <!-- Wide screens: one real table, four tier columns, Ultra as a strip below. -->
    <div class="mm-wide">
      <div class="mm-currency" role="group" aria-label="Price currency">
        <button type="button" :aria-pressed="currency === 'CNY'" :class="{ on: currency === 'CNY' }" data-testid="mm-cny" @click="currency = 'CNY'">CNY</button>
        <button type="button" :aria-pressed="currency === 'USD'" :class="{ on: currency === 'USD' }" data-testid="mm-usd" @click="currency = 'USD'">USD</button>
      </div>
      <table class="mm-table" data-testid="mm-table">
        <thead ref="head">
          <tr>
            <th scope="col" class="mm-corner"><span>CAPABILITY</span></th>
            <th
              v-for="tier in columns" :key="tier" scope="col"
              :class="['mm-tier', focusedClass(tier), { 'is-plus': tier === 'plus' }]"
              :data-tier="tier"
              @mouseenter="focus = tier" @mouseleave="focus = ''"
              @focusin="focus = tier" @focusout="focus = ''"
              tabindex="0"
            >
              <span v-if="tier === 'plus'" class="mm-pill">RECOMMENDED</span>
              <span class="mm-beans" aria-hidden="true"><BeanMark v-for="n in BEANS[tier]" :key="n" class="mm-bean" /></span>
              <b class="mm-name">{{ TIER_LABEL[tier] }}</b>
              <span :key="`${tier}-${currency}`" class="mm-price" data-testid="mm-price">{{ price(tier) }}</span>
              <small class="mm-billing">{{ billing(tier) }}</small>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows.slice(0, VISIBLE_ROWS)" :id="`mm-row-${row.id}`" :key="row.id">
            <th scope="row" class="mm-label">
              <span class="mm-stair" aria-hidden="true">{{ tagFor(row) }}</span>
              <b>{{ row.label }}</b>
              <small v-if="row.note">{{ row.note }}</small>
            </th>
            <td
              v-for="(tier, i) in columns" :key="tier"
              :class="['mm-cell', focusedClass(tier), { 'is-plus': tier === 'plus', 'stair-start': included(row, tier) && (i === 0 || !included(row, columns[i - 1])) }]"
              @mouseenter="focus = tier" @mouseleave="focus = ''"
            >
              <span v-if="included(row, tier)" class="mm-check in" :aria-label="`${TIER_LABEL[tier]}: included`" role="img">
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5 8.2 15 16 5" /></svg>
              </span>
              <span v-else class="mm-dash" :aria-label="`${TIER_LABEL[tier]}: not included`" role="img">—</span>
            </td>
          </tr>
        </tbody>
        <!-- Rows below the fold stay in the document and animate through a 0fr → 1fr grid,
             so the reveal is a layout transition rather than a fixed max-height guess. -->
        <tbody class="mm-extra">
          <tr>
            <td colspan="5" style="padding: 0; border: 0;">
              <div class="mm-extra-wrap" :class="{ open: expanded }" :aria-hidden="!expanded">
                <div class="mm-extra-clip">
                  <table class="mm-extra-table">
                    <tbody>
                      <tr v-for="row in rows.slice(VISIBLE_ROWS)" :key="`x-${row.id}`">
                        <th scope="row" class="mm-label">
                          <span class="mm-stair" aria-hidden="true">{{ tagFor(row) }}</span>
                          <b>{{ row.label }}</b>
                          <small v-if="row.note">{{ row.note }}</small>
                        </th>
                        <td
                          v-for="(tier, i) in columns" :key="tier"
                          :class="['mm-cell', { 'is-plus': tier === 'plus', 'stair-start': included(row, tier) && (i === 0 || !included(row, columns[i - 1])) }]"
                        >
                          <span v-if="included(row, tier)" class="mm-check in" :aria-label="`${TIER_LABEL[tier]}: included`" role="img">
                            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5 8.2 15 16 5" /></svg>
                          </span>
                          <span v-else class="mm-dash" :aria-label="`${TIER_LABEL[tier]}: not included`" role="img">—</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <button v-if="!expanded" type="button" class="mm-more" data-testid="mm-more" @click="expanded = true">Show every row ↓</button>
      <button v-else type="button" class="mm-more" data-testid="mm-more" aria-expanded="true" @click="expanded = false">Show fewer rows ↑</button>
      <p class="mm-foot">Pricing is published. Checkout opens soon. Registration needs an invite code.</p>

      <div ref="stage" class="mm-ultra">
        <span class="mm-ultra-tag"><BeanMark class="mm-bean gold" />ULTRA</span>
        <span class="mm-ultra-copy">Invite only · includes every Pro capability</span>
        <a class="mm-ultra-link" href="/register">Have a code? Register →</a>
        <i class="mm-ultra-shine" aria-hidden="true"></i>
      </div>
    </div>

    <!-- Phones: draggable tier cards, then one row per capability with four marks. -->
    <div class="mm-mobile">
      <div ref="rail" class="mm-rail" data-testid="mm-rail" aria-label="Membership tiers" role="region">
        <article
          v-for="(tier, i) in columns" :key="tier" class="mm-card"
          :class="{ 'is-plus': tier === 'plus' }"
          :data-tier="tier"
          :aria-current="cardIndex === i ? 'true' : 'false'"
          @click="cardIndex = i"
        >
          <span v-if="tier === 'plus'" class="mm-pill">RECOMMENDED</span>
          <span class="mm-beans" aria-hidden="true"><BeanMark v-for="n in BEANS[tier]" :key="n" class="mm-bean" /></span>
          <b class="mm-name">{{ TIER_LABEL[tier] }}</b>
          <span class="mm-price">{{ price(tier) }}</span>
          <small class="mm-billing">{{ billing(tier) }} · {{ billingNote(tier) }}</small>
          <ul class="mm-new">
            <li v-for="row in rows.filter(r => r.min === tier).slice(0, 3)" :key="row.id">{{ row.label }}</li>
            <li v-if="tier === 'free'" class="mm-new-note">Everything below starts here</li>
          </ul>
        </article>
      </div>
      <div class="mm-currency mm-currency-mobile" role="group" aria-label="Price currency">
        <button type="button" :aria-pressed="currency === 'CNY'" :class="{ on: currency === 'CNY' }" @click="currency = 'CNY'">CNY</button>
        <button type="button" :aria-pressed="currency === 'USD'" :class="{ on: currency === 'USD' }" @click="currency = 'USD'">USD</button>
      </div>
      <ul class="mm-list" data-testid="mm-list">
        <li v-for="row in shownRows" :key="`m-${row.id}`">
          <span class="mm-list-label">{{ row.label }}<small v-if="row.note"> · {{ row.note }}</small></span>
          <span class="mm-list-marks">
            <span v-for="tier in columns" :key="tier" :class="{ on: activeTier === tier }" :aria-label="`${TIER_LABEL[tier]}: ${included(row, tier) ? 'included' : 'not included'}`" role="img">
              {{ included(row, tier) ? '✓' : '—' }}
            </span>
          </span>
        </li>
      </ul>
      <button v-if="!expanded" type="button" class="mm-more" data-testid="mm-more-mobile" @click="expanded = true">Show every row ↓</button>
      <button v-else type="button" class="mm-more" data-testid="mm-more-mobile" aria-expanded="true" @click="expanded = false">Show fewer rows ↑</button>
      <p class="mm-foot">Pricing is published. Checkout opens soon. Registration needs an invite code.</p>
      <div class="mm-ultra">
        <span class="mm-ultra-tag"><BeanMark class="mm-bean gold" />ULTRA</span>
        <span class="mm-ultra-copy">Invite only · includes every Pro capability</span>
        <a class="mm-ultra-link" href="/register">Have a code? Register →</a>
      </div>
    </div>
  </section>
</template>

<style scoped>
.mm { padding-top: clamp(40px, 6vh, 72px); border-top: 1px solid var(--line2); position: relative; }
.mm-head { max-width: 68ch; }
.mm-lede { margin: 12px 0 0; color: var(--muted); font-size: 15px; line-height: 1.55; }
.mm-wide { display: none; }
.mm-mobile { display: block; }

/* ---------- wide table ---------- */
@media (min-width: 861px) {
  .mm-wide { display: block; }
  .mm-mobile { display: none; }
  .mm-currency { display: flex; gap: 0; justify-content: flex-end; margin-bottom: 10px; }
  .mm-currency button { min-height: 44px; min-width: 64px; padding: 0 12px; border: 1px solid var(--line2); background: transparent; color: var(--muted); font: 700 9px var(--mono); letter-spacing: .1em; cursor: pointer; }
  .mm-currency button + button { border-left: 0; }
  .mm-currency button.on { background: var(--ink); border-color: var(--ink); color: var(--bg); }

  .mm-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  .mm-table thead th { position: sticky; top: var(--topH, 0px); z-index: 3; background: var(--bg); }
  .mm-table thead[data-sticky="off"] th { position: static; }
  .mm-corner { width: 26%; text-align: left; vertical-align: bottom; padding: 12px 12px 14px 0; font: 700 8px var(--mono); letter-spacing: .1em; color: var(--muted); }
  .mm-tier { width: 18.5%; padding: 12px 8px 10px; border-left: 1px solid var(--line-soft); text-align: left; vertical-align: bottom; transition: transform .2s var(--ease, ease), background .2s ease; }
  .mm-tier:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .mm-tier.is-focus { transform: translateY(-2px); background: var(--accent-soft); }
  .mm-tier.is-plus { background: rgba(17, 17, 17, .045); border-left: 1px solid var(--ink); border-right: 1px solid var(--ink); }
  .mm-tier.is-plus.is-focus { background: rgba(17, 17, 17, .08); }
  .mm-pill { position: absolute; margin-top: -26px; padding: 3px 8px; background: var(--accent); color: #fff; font: 700 7px var(--mono); letter-spacing: .1em; }
  .mm-beans { display: flex; gap: 3px; min-height: 12px; margin-bottom: 4px; }
  .mm-bean { width: 11px; height: 11px; }
  .mm-name { display: block; font: 500 19px var(--serif); letter-spacing: -.01em; }
  .mm-price { display: block; margin-top: 2px; font: 700 16px var(--mono); font-variant-numeric: tabular-nums; }
  .mm-price { animation: mm-flip .18s cubic-bezier(.22, 1, .36, 1); }
  .mm-billing { display: block; margin-top: 2px; font: 600 7.5px var(--mono); letter-spacing: .1em; color: var(--muted); }
  @keyframes mm-flip { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }

  .mm-table tbody th, .mm-table tbody td { border-top: 1px solid var(--line-soft); padding: 10px 12px 10px 8px; }
  .mm-label { text-align: left; vertical-align: middle; }
  .mm-stair { display: block; font: 700 7px var(--mono); letter-spacing: .1em; color: var(--muted); }
  .mm-label b { display: block; font: 600 12.5px var(--sans); }
  .mm-label small { display: block; margin-top: 2px; font: 10px var(--sans); color: var(--muted); }
  .mm-cell { text-align: left; vertical-align: middle; border-left: 1px solid var(--line-soft); transition: background .2s ease; }
  .mm-cell.is-focus { background: var(--accent-soft); }
  .mm-cell.is-plus { background: rgba(17, 17, 17, .045); }
  .mm-cell.stair-start { border-left: 1px solid var(--ink); }
  .mm-check { display: inline-grid; place-items: center; width: 20px; height: 20px; }
  /* A tick is visible by default; the reveal only animates it when motion is allowed,
     so reduced-motion users still see every included cell. */
  .mm-check svg { width: 20px; height: 20px; fill: none; stroke: var(--ink); stroke-width: 2; stroke-linecap: square; stroke-dasharray: 26; stroke-dashoffset: 0; }
  .mm-check.in svg { animation: mm-draw .24s linear forwards; animation-delay: var(--d, 0ms); }
  @keyframes mm-draw { from { stroke-dashoffset: 26; } to { stroke-dashoffset: 0; } }
  .mm-dash { color: var(--line); font: 700 13px var(--mono); }

  .mm-more { display: inline-flex; min-height: 44px; align-items: center; margin-top: 14px; padding: 0 14px; border: 1px solid var(--line2); background: transparent; color: var(--ink); font: 700 9px var(--mono); letter-spacing: .08em; cursor: pointer; list-style: none; }
  .mm-extra-wrap { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .24s cubic-bezier(.22, 1, .36, 1); }
  .mm-extra-wrap.open { grid-template-rows: 1fr; }
  .mm-extra-clip { overflow: hidden; }
  .mm-extra-table { width: 100%; table-layout: fixed; border-collapse: collapse; }
  .mm-extra-table th.mm-label { width: 26%; }
  .mm-extra-table td.mm-cell { width: 18.5%; }
  .mm-more summary::-webkit-details-marker { display: none; }
  .mm-foot { margin: 12px 0 0; font: 10.5px var(--mono); color: var(--muted); line-height: 1.6; }

  .mm-ultra { position: relative; display: grid; grid-template-columns: auto 1fr auto; gap: 16px; align-items: center; margin-top: 22px; padding: 16px 18px; background: var(--ink); color: var(--bg); overflow: hidden; }
  .mm-ultra-tag { display: flex; align-items: center; gap: 8px; font: 700 10px var(--mono); letter-spacing: .14em; }
  .mm-bean.gold { outline: 1px solid var(--gold); outline-offset: 1px; }
  .mm-ultra-copy { font: 500 13px var(--sans); color: rgba(241, 240, 235, .78); }
  .mm-ultra-link { color: var(--bg); font: 700 9.5px var(--mono); letter-spacing: .06em; text-decoration: none; border-bottom: 1px solid rgba(241, 240, 235, .4); padding-bottom: 2px; }
  .mm-ultra-shine { position: absolute; left: 0; right: 0; top: 0; height: 1px; background: linear-gradient(90deg, transparent, rgba(255, 255, 255, .85), transparent); transform: scaleX(0); transform-origin: left center; }
  .mm-ultra.in .mm-ultra-shine { animation: mm-sweep .9s cubic-bezier(.22, 1, .36, 1) forwards; }
  @keyframes mm-sweep { to { transform: scaleX(1); } }
}

/* ---------- phone cards ---------- */
.mm-rail { display: flex; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 4px 0 14px; -webkit-overflow-scrolling: touch; }
.mm-rail::-webkit-scrollbar { display: none; }
.mm-card { position: relative; flex: 0 0 78%; scroll-snap-align: center; border: 1px solid var(--line2); padding: 14px; background: var(--bg); }
.mm-card.is-plus { border-color: var(--ink); background: rgba(17, 17, 17, .045); }
.mm-card[aria-current="true"] { border-color: var(--accent); }
.mm-pill { display: inline-block; margin-bottom: 6px; padding: 3px 7px; background: var(--accent); color: #fff; font: 700 7px var(--mono); letter-spacing: .1em; }
.mm-beans { display: flex; gap: 3px; min-height: 12px; }
.mm-bean { width: 11px; height: 11px; }
.mm-name { display: block; margin-top: 4px; font: 500 20px var(--serif); }
.mm-price { display: block; font: 700 16px var(--mono); }
.mm-billing { display: block; margin-top: 2px; font: 600 7.5px var(--mono); letter-spacing: .08em; color: var(--muted); text-transform: uppercase; }
.mm-new { margin: 10px 0 0; padding: 0; list-style: none; }
.mm-new li { padding: 6px 0; border-top: 1px solid var(--line-soft); font: 11.5px var(--sans); }
.mm-new-note { color: var(--muted); font-size: 10.5px; }
.mm-currency-mobile { display: flex; margin: 0 0 10px; }
.mm-currency-mobile button { min-height: 44px; min-width: 64px; border: 1px solid var(--line2); background: transparent; color: var(--muted); font: 700 9px var(--mono); letter-spacing: .1em; }
.mm-currency-mobile button + button { border-left: 0; }
.mm-currency-mobile button.on { background: var(--ink); border-color: var(--ink); color: var(--bg); }
.mm-list { margin: 0; padding: 0; list-style: none; }
.mm-list li { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 0; border-top: 1px solid var(--line-soft); }
.mm-list-label { font: 11.5px/1.35 var(--sans); min-width: 0; }
.mm-list-label small { color: var(--muted); }
.mm-list-marks { display: flex; gap: 2px; flex: none; }
.mm-list-marks span { width: 22px; text-align: center; font: 700 10px var(--mono); color: var(--line); }
.mm-list-marks span.on { color: var(--ink); background: var(--accent-soft); }
.mm-foot { margin: 12px 0 0; font: 10px var(--mono); color: var(--muted); line-height: 1.6; }
.mm-ultra { display: grid; gap: 8px; margin-top: 16px; padding: 14px; background: var(--ink); color: var(--bg); }
.mm-ultra-tag { display: flex; align-items: center; gap: 8px; font: 700 10px var(--mono); letter-spacing: .14em; }
.mm-bean.gold { outline: 1px solid var(--gold); outline-offset: 1px; }
.mm-ultra-copy { font: 12.5px var(--sans); color: rgba(241, 240, 235, .78); }
.mm-ultra-link { color: var(--bg); font: 700 9.5px var(--mono); letter-spacing: .06em; text-decoration: none; }

.mm.mm-reduced, .mm.mm-reduced * { animation: none !important; transition: none !important; }
@media (prefers-reduced-motion: reduce) {
  .mm, .mm * { animation: none !important; transition: none !important; }
}
</style>
