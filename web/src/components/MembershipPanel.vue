<script setup>
// Account membership panel: tier, expiry, signed-in devices and code redemption.
// Everything comes from /api/session and /api/membership/*, never from a local guess.
import { computed, onMounted, ref } from 'vue';
import BeanMark from './BeanMark.vue';
import membership from '../membership.json';

const props = defineProps({ session: { type: Object, default: null } });
const emit = defineEmits(['changed']);

const TIER_LABEL = { free: 'Free', lite: 'Lite', plus: 'Plus', pro: 'Pro', ultra: 'Ultra' };
const BEANS = { free: 0, lite: 1, plus: 2, pro: 3, ultra: 4 };
const code = ref('');
const message = ref('');
const failed = ref(false);
const busy = ref(false);
const devices = ref(null);
const revoking = ref(null);

const tier = computed(() => props.session?.tier || 'free');
const label = computed(() => TIER_LABEL[tier.value] || tier.value);
const beans = computed(() => BEANS[tier.value] || 0);
const permanent = computed(() => !!props.session?.authenticated && (tier.value === 'ultra' || props.session?.base_tier === tier.value));
const expiry = computed(() => {
  const date = toDate(props.session?.timed_until);
  if (!date) return '';
  return new Intl.DateTimeFormat('en-CA', { dateStyle: 'medium', timeZone: 'Asia/Shanghai' }).format(date);
});
const deviceLimit = computed(() => props.session?.device_limit ?? membership.device_limit);

// SQLite hands back UTC without a marker, sometimes with a space instead of T.
// Parse defensively: an invalid stamp must render as blank, never throw mid-render.
function toDate(value) {
  if (!value) return null;
  const text = String(value).trim().replace(' ', 'T');
  const date = new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(text) ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function stamp(value) {
  const date = toDate(value);
  if (!date) return '';
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Shanghai' }).format(date);
}

async function loadDevices() {
  try {
    const response = await fetch('/api/membership/sessions');
    if (!response.ok) { devices.value = null; return; }
    devices.value = await response.json();
  } catch { devices.value = null; }
}

async function revoke(id) {
  revoking.value = id;
  try {
    const response = await fetch(`/api/membership/sessions/${id}`, { method: 'DELETE' });
    if (response.ok) await loadDevices();
    else { failed.value = true; message.value = 'That device could not be signed out.'; }
  } catch { failed.value = true; message.value = 'That device could not be signed out.'; }
  finally { revoking.value = null; }
}

async function redeem() {
  const value = code.value.trim();
  if (!value) { failed.value = true; message.value = 'Enter a code first.'; return; }
  busy.value = true; failed.value = false; message.value = '';
  try {
    const response = await fetch('/api/membership/redeem', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: value }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { failed.value = true; message.value = data.error || 'That code was not accepted.'; return; }
    failed.value = false;
    message.value = data.message || 'Code redeemed. Your membership is updated.';
    code.value = '';
    emit('changed');
  } catch { failed.value = true; message.value = 'The server did not answer. Try again.'; }
  finally { busy.value = false; }
}

onMounted(loadDevices);
</script>

<template>
  <section id="membership-panel" class="mp" data-testid="membership-panel" aria-label="Membership">
    <div class="mp-head">
      <div class="mp-tier">
        <span class="mp-beans" aria-hidden="true"><BeanMark v-for="n in beans" :key="n" class="mp-bean" /></span>
        <strong data-testid="mp-tier">{{ label }}</strong>
        <small v-if="permanent">PERMANENT</small>
        <small v-else-if="expiry" data-testid="mp-expiry">UNTIL {{ expiry }}</small>
      </div>
      <p class="mp-copy">Higher tiers include everything below them. A lapsed timed tier drops one tier, never the ledger.</p>
    </div>

    <div class="mp-block">
      <span class="mp-label">SIGNED-IN DEVICES</span>
      <b data-testid="mp-devices">{{ devices ? `${devices.sessions.length} / ${deviceLimit}` : `— / ${deviceLimit}` }}</b>
      <ul v-if="devices" class="mp-list" data-testid="mp-device-list">
        <li v-for="entry in devices.sessions" :key="entry.id" :class="{ mine: entry.id === devices.current }">
          <span>{{ entry.id === devices.current ? 'THIS DEVICE' : 'OTHER DEVICE' }}</span>
          <small>{{ stamp(entry.last_seen_at || entry.created_at) }}</small>
          <small class="mp-agent">{{ (entry.user_agent || 'unknown browser').slice(0, 48) }}</small>
          <button v-if="entry.id !== devices.current" type="button" class="quiet-button" :disabled="revoking === entry.id" @click="revoke(entry.id)">Sign out</button>
          <em v-else class="mp-here">current</em>
        </li>
      </ul>
    </div>

    <form class="mp-redeem" data-testid="redeem-form" @submit.prevent="redeem">
      <label for="mp-code">Redeem a code</label>
      <div class="mp-row">
        <input id="mp-code" v-model="code" data-testid="redeem-code" name="code" autocomplete="off" spellcheck="false" placeholder="INVITE OR GRANT CODE">
        <button type="submit" class="quiet-button" data-testid="redeem-submit" :disabled="busy">{{ busy ? 'Redeeming…' : 'Redeem' }}</button>
      </div>
      <p v-if="message" class="mp-message" :class="{ bad: failed }" data-testid="redeem-message" role="status">{{ message }}</p>
    </form>
  </section>
</template>

<style scoped>
.mp { border: 1px solid var(--line2); background: var(--panel); padding: 18px; display: grid; gap: 18px; }
.mp-head { display: grid; gap: 8px; }
.mp-tier { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.mp-beans { display: inline-flex; gap: 3px; }
.mp-bean { width: 10px; height: 10px; }
.mp-tier strong { font: 500 26px var(--serif); }
.mp-tier small { font: 8px var(--mono); letter-spacing: .14em; color: var(--accent); }
.mp-copy { font-size: 12px; line-height: 1.7; color: var(--muted); max-width: 46em; }
.mp-block { display: grid; gap: 8px; border-top: 1px solid var(--hair); padding-top: 14px; }
.mp-label { font: 8.5px var(--mono); letter-spacing: .14em; color: var(--muted); }
.mp-block b { font: 500 20px var(--mono); }
.mp-list { display: grid; gap: 1px; background: var(--soft); border: 1px solid var(--soft); }
.mp-list li { display: grid; grid-template-columns: 86px 96px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 8px 10px; background: var(--panel2); font: 9px var(--mono); }
.mp-list li.mine { background: var(--accent-soft); }
.mp-list li span { font-weight: 700; letter-spacing: .1em; }
.mp-agent { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); }
.mp-here { font: 8px var(--mono); letter-spacing: .1em; color: var(--muted); }
.mp-row { display: flex; gap: 8px; flex-wrap: wrap; }
.mp-row input { flex: 1 1 200px; min-height: 44px; padding: 0 12px; border: 1px solid var(--line2); background: var(--panel2); font: 11px var(--mono); letter-spacing: .06em; }
.mp-message { font: 10px var(--mono); letter-spacing: .05em; }
.mp-message.bad { color: var(--accent); }
.mp .quiet-button { min-height: 44px; }
@media (max-width: 560px) {
  .mp-list li { grid-template-columns: 1fr auto; }
  .mp-agent { display: none; }
}
</style>
