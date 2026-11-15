<script setup>
import { onMounted, ref } from 'vue';

const props = defineProps({ cycleId: { type: String, required: true } });

const TIERS = [
  { id: 'aggressive', label: 'AGGRESSIVE' },
  { id: 'stable', label: 'STABLE' },
  { id: 'conservative', label: 'CONSERVATIVE' },
];

const status = ref(null);
const loadError = ref('');
const outlook = ref(null);
const pending = ref('');
const failure = ref('');
const chatOpen = ref(false);
const chatInput = ref('');
const conversation = ref([]);
const openCall = ref(null);
const callState = ref({ id: '', loading: false, error: '' });

async function getJson(path) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) {
    let message = `Server request failed (${response.status}).`;
    try { const body = await response.json(); message = body.error || body.detail || message; } catch { /* keep default */ }
    throw new Error(message);
  }
  return response.json();
}

async function loadStatus() {
  loadError.value = '';
  try { status.value = await getJson(`/api/ai/status?${new URLSearchParams({ cycle_id: props.cycleId })}`); }
  catch (error) { loadError.value = error.message; }
}

async function generate() {
  if (pending.value) return;
  pending.value = 'outlook';
  failure.value = '';
  try {
    const response = await fetch('/api/ai/outlook', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: props.cycleId }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || body.error || `Server request failed (${response.status}).`);
    outlook.value = body.result;
    status.value = { ...status.value, quota: body.quota };
    await loadStatus();
  } catch (error) { failure.value = error.message; await loadStatus(); }
  finally { pending.value = ''; }
}

async function sendChat() {
  const message = chatInput.value.trim();
  if (!message || pending.value) return;
  pending.value = 'chat';
  failure.value = '';
  const history = conversation.value.slice();
  conversation.value = [...history, { role: 'user', content: message }];
  chatInput.value = '';
  try {
    const response = await fetch('/api/ai/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: props.cycleId, message, conversation: history }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || body.error || `Server request failed (${response.status}).`);
    conversation.value = [...conversation.value, { role: 'assistant', content: body.result }];
    status.value = { ...status.value, quota: body.quota };
    await loadStatus();
  } catch (error) {
    failure.value = error.message;
    conversation.value = history;
    chatInput.value = message;
    await loadStatus();
  } finally { pending.value = ''; }
}

async function exportBundle() {
  failure.value = '';
  try {
    const response = await fetch(`/api/ai/export?${new URLSearchParams({ cycle_id: props.cycleId })}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Export failed (${response.status}). Nothing was downloaded.`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'RoastRaw-ai-export.json';
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) { failure.value = error.message; }
}

async function showCall(id) {
  if (openCall.value?.id === id) { openCall.value = null; callState.value = { id: '', loading: false, error: '' }; return; }
  callState.value = { id, loading: true, error: '' };
  try { openCall.value = await getJson(`/api/ai/call/${id}`); }
  catch (error) {
    // A click must always produce a visible answer: either the stored call or
    // the reason its detail is missing. Never a dead button (0.43).
    openCall.value = { id };
    callState.value = { id, loading: false, error: error.message };
  } finally {
    if (callState.value.id === id) callState.value = { ...callState.value, loading: false };
  }
}

function callOutlook(call) {
  if (call.kind !== 'outlook' || call.status !== 'ok' || !call.response) return null;
  try { return JSON.parse(call.response); } catch { return null; }
}

onMounted(loadStatus);
</script>

<template>
  <section class="ai-outlook" data-testid="ai-outlook" aria-label="AI outlook">
    <div class="ai-head">
      <div><span class="section-label">AI OUTLOOK · DEEPSEEK</span>
        <p class="micro-copy">Three next-cycle tiers from your review and questionnaire. Advice only — the final plan JSON is generated externally and imported.</p></div>
      <span v-if="status" class="badge" data-testid="ai-quota">QUOTA {{ status.quota.used }}/{{ status.quota.limit }} · {{ status.quota.date }}</span>
    </div>
    <p v-if="loadError" class="notice" role="alert">{{ loadError }} <button class="inline-link" @click="loadStatus">Retry</button></p>
    <template v-if="status">
      <p v-if="!status.configured" class="notice" data-testid="ai-unconfigured">DeepSeek is not configured on this server. Export the review, questionnaire and full prompt, then hand them to an external AI.</p>
      <div class="ai-actions">
        <button data-testid="ai-generate" :disabled="pending !== '' || !status.configured || status.quota.remaining === 0" @click="generate">{{ pending === 'outlook' ? 'Calling DeepSeek…' : 'Generate outlook' }}</button>
        <button class="inline-link" data-testid="ai-export" @click="exportBundle">Export for external AI</button>
        <button class="inline-link" data-testid="ai-chat-toggle" :aria-expanded="chatOpen" @click="chatOpen = !chatOpen">{{ chatOpen ? 'Close chat' : 'Fine-tune in chat' }}</button>
      </div>
      <p v-if="status.configured && status.quota.remaining === 0" class="notice">Today’s quota is used up (Beijing time). It resets tomorrow; export works without quota.</p>
      <p v-if="failure" class="notice ai-failure" role="alert" data-testid="ai-failure">{{ failure }} <button class="inline-link" @click="exportBundle">Export instead</button></p>
      <div v-if="outlook" class="ai-tiers" data-testid="ai-tiers">
        <article v-for="tier in TIERS" :key="tier.id" class="ai-tier" :data-tier="tier.id">
          <span class="section-label">{{ tier.label }}</span>
          <p>{{ outlook[tier.id].summary }}</p>
          <ul><li v-for="(item, index) in outlook[tier.id].adjustments" :key="index">{{ item }}</li></ul>
        </article>
      </div>
      <div v-if="chatOpen" class="ai-chat" data-testid="ai-chat">
        <span class="section-label">FINE-TUNE CHAT · EACH SEND USES ONE CALL</span>
        <p v-if="!conversation.length" class="micro-copy">Ask for concrete changes: loads, sets, reps, RPE. The cycle review and questionnaire are attached automatically.</p>
        <div v-for="(entry, index) in conversation" :key="index" class="ai-msg" :data-role="entry.role"><b>{{ entry.role === 'user' ? 'YOU' : 'AI' }}</b><p>{{ entry.content }}</p></div>
        <form class="ai-chat-form" @submit.prevent="sendChat">
          <input v-model="chatInput" maxlength="4000" placeholder="e.g. Make the stable tier squat 2.5 kg heavier" aria-label="Chat message" :disabled="pending !== ''" />
          <button type="submit" data-testid="ai-chat-send" :disabled="pending !== '' || !chatInput.trim() || !status.configured || status.quota.remaining === 0">{{ pending === 'chat' ? 'Sending…' : 'Send' }}</button>
        </form>
      </div>
      <details v-if="status.calls.length" class="ai-history" data-testid="ai-history">
        <summary>CALL HISTORY <span class="badge">{{ status.calls.length }}</span></summary>
        <div v-for="call in status.calls" :key="call.id" class="ai-call">
          <button class="inline-link" :disabled="callState.loading && callState.id === call.id" @click="showCall(call.id)">#{{ call.id }} · {{ call.kind.toUpperCase() }} · {{ call.status.toUpperCase() }} · {{ call.created_at.slice(0, 16).replace('T', ' ') }}{{ callState.loading && callState.id === call.id ? ' · loading…' : '' }}</button>
          <p v-if="call.status === 'error'" class="micro-copy">{{ call.error }}</p>
          <template v-if="openCall?.id === call.id">
            <p v-if="callState.error" class="micro-copy ai-failure" role="alert">{{ callState.error }} This call keeps its timing and usage only; its text was not stored.</p>
            <template v-else>
              <div v-if="callOutlook(openCall)" class="ai-tiers">
                <article v-for="tier in TIERS" :key="tier.id" class="ai-tier" :data-tier="tier.id">
                  <span class="section-label">{{ tier.label }}</span>
                  <p>{{ callOutlook(openCall)[tier.id].summary }}</p>
                  <ul><li v-for="(item, index) in callOutlook(openCall)[tier.id].adjustments" :key="index">{{ item }}</li></ul>
                </article>
              </div>
              <p v-else-if="openCall.response" class="ai-record">{{ openCall.response }}</p>
              <p v-else class="micro-copy">This call stored its timing and usage only; no text was kept for it.</p>
            </template>
          </template>
        </div>
      </details>
    </template>
  </section>
</template>

<style scoped>
.ai-outlook { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--line); }
.ai-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.ai-actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin: 16px 0; }
.ai-actions button { min-height: 44px; }
.ai-failure { border-left: 3px solid var(--main, #B3261E); padding-left: 12px; }
.ai-tiers { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 16px 0; }
.ai-tier { border: 1px solid var(--line); padding: 16px; }
.ai-tier[data-tier='aggressive'] { border-top: 3px solid var(--main, #B3261E); }
.ai-tier[data-tier='stable'] { border-top: 3px solid var(--var, #1D5BC4); }
.ai-tier[data-tier='conservative'] { border-top: 3px solid var(--accCol, #1E7A45); }
.ai-tier p { margin: 8px 0; font-size: 14px; line-height: 1.6; }
.ai-tier ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.7; }
.ai-chat { border: 1px solid var(--line); padding: 16px; margin: 16px 0; }
.ai-msg { margin: 12px 0; }
.ai-msg b { font-size: 11px; letter-spacing: .08em; color: var(--muted); }
.ai-msg p { margin: 4px 0 0; font-size: 14px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.ai-chat-form { display: flex; gap: 8px; margin-top: 12px; }
.ai-chat-form input { flex: 1; min-height: 44px; min-width: 0; padding: 0 12px; border: 1px solid var(--line); background: var(--surface, transparent); color: inherit; font: inherit; }
.ai-chat-form button { min-height: 44px; }
.ai-history { margin-top: 16px; }
.ai-history summary { min-height: 44px; display: flex; align-items: center; gap: 8px; cursor: pointer; }
.ai-call { padding: 8px 0; border-top: 1px solid var(--line-soft, var(--line)); }
.ai-call .inline-link { min-height: 44px; display: inline-flex; align-items: center; }
.ai-record { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 1.6; }
</style>