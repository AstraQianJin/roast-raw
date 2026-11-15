<script setup>
import { ref, watch } from 'vue';
import LogEditor from './LogEditor.vue';

const props = defineProps({
  rows: { type: Array, default: () => [] },
  cycleId: { type: String, default: '' },
  logs: { type: Object, default: () => ({}) },
  systemLoads: { type: Object, default: () => ({}) },
  readonly: { type: Boolean, default: false },
});
const emit = defineEmits(['saved']);
const openEditor = ref(null);
const visitedEditors = ref(new Set());
const logKey = row => `${row.week}|${row.day}|${row.seq}`;
const editorKey = row => JSON.stringify([props.cycleId, row.week, row.day, row.seq]);
const toggleEditor = row => {
  const key = editorKey(row);
  visitedEditors.value.add(key);
  openEditor.value = openEditor.value === key ? null : key;
};
watch(() => props.readonly, value => { if (value) openEditor.value = null; });
const roleNames = { main: 'MAIN LIFTS', sbdVar: 'SBD VARIATIONS', nonSbdVar: 'OTHER VARIATIONS', accessory: 'ACCESSORIES' };
const display = value => value === null || value === undefined ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 1 });
const setTag = segment => {
  const label = (segment.label || 'WORK').toUpperCase();
  const tag = label === 'BACK-OFF' ? 'BACK-OFF' : label === 'TOP' ? 'TOP SET' : label;
  return segment.amrap ? `${tag} · AMRAP` : tag;
};
const logSummary = row => {
  const log = props.logs[logKey(row)];
  if (!log) return '';
  if (log.sets === 0) return 'SKIPPED';
  return `${display(log.load)}×${log.reps}×${log.sets}${log.rpe !== null && log.rpe !== undefined ? ` @${display(log.rpe)}` : ''}`;
};
</script>

<template>
  <div class="exercise-rows">
    <template v-for="(label, role) in roleNames" :key="role">
      <template v-if="rows.some(row => row.bucket === role)">
        <div class="section-heading"><span class="section-label">{{ label }}</span><span class="mono">{{ String(rows.filter(row => row.bucket === role).length).padStart(2, '0') }}</span></div>
        <article v-for="row in rows.filter(row => row.bucket === role)" :key="`${row.week}-${row.day}-${row.seq}`" :class="['exercise', row.bucket]">
          <header class="ex-head">
            <span class="ex-index">{{ String(row.seq).padStart(2, '0') }}</span>
            <div class="ex-title"><h3 class="ex-name">{{ row.nameEn }}</h3><span class="ex-rpe">RPE {{ display(row.targetRpe) }}</span></div>
            <button
              v-if="!readonly"
              type="button"
              class="log-inline"
              :class="{ done: !!logs[logKey(row)] }"
              :aria-expanded="openEditor === editorKey(row)"
              @click="toggleEditor(row)"
            ><small>{{ openEditor === editorKey(row) ? 'CLOSE' : logs[logKey(row)] ? 'EDIT' : 'LOG' }}</small><b>{{ logSummary(row) || '—' }}</b></button>
          </header>
          <div class="ex-sets">
            <div v-for="(segment, index) in row.segments" :key="index" class="ex-set" :class="segment.kind">
              <span class="set-tag">{{ setTag(segment) }}</span>
              <span class="set-scheme"><b>{{ segment.sets }}</b><i>×</i><b>{{ segment.reps }}</b><i v-if="segment.unit">{{ segment.unit }}</i></span>
              <span class="set-load"><b>{{ role === 'accessory' && segment.load === null ? '—' : display(segment.load) }}</b><small v-if="segment.load !== null && role !== 'accessory'"> kg</small></span>
              <span v-if="segment.pct !== null && role !== 'accessory'" class="set-pct">{{ display(segment.pct) }}<small>%</small></span>
            </div>
          </div>
          <p v-if="systemLoads[logKey(row)]" class="system-load" data-testid="system-load">
            Total system weight ·
            <template v-for="(weight, index) in systemLoads[logKey(row)].planned" :key="index">
              {{ display(weight.total) }} kg ·
              <template v-if="weight.adjustment === null">External load unknown: record bodyweight on or before {{ row.date }}.</template>
              <template v-else>{{ weight.adjustment < 0 ? `${display(-weight.adjustment)} kg assistance` : weight.adjustment > 0 ? `+${display(weight.adjustment)} kg added` : 'Bodyweight only' }} · bodyweight {{ display(weight.bodyweight) }} kg ({{ weight.bodyweightDate }}).</template>
            </template>
            <span v-if="systemLoads[logKey(row)].logged" class="logged-system">Logged total {{ display(systemLoads[logKey(row)].logged.total) }} kg · {{ systemLoads[logKey(row)].logged.adjustment === null ? 'external load unknown' : `${display(systemLoads[logKey(row)].logged.adjustment)} kg external adjustment` }}.</span>
          </p>
          <LogEditor
            v-if="visitedEditors.has(editorKey(row))"
            v-show="!readonly && openEditor === editorKey(row)"
            :key="editorKey(row)"
            :row="row"
            :cycle-id="cycleId"
            :log="logs[logKey(row)]"
            @saved="emit('saved', $event)"
          />
        </article>
      </template>
    </template>
  </div>
</template>

<style scoped>
.exercise { padding: 12px 8px 10px; border: 0; border-top: 1px solid var(--line-soft); border-radius: 0; background: none; box-shadow: none; margin: 0; }
.exercise:nth-of-type(even) { background: var(--panel2); }
.exercise:first-of-type { border-top: 1px solid var(--line2); }
.ex-head { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: baseline; gap: 8px; }
.ex-title { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.ex-index { font: 700 8px var(--mono); color: var(--muted); }
.ex-name { margin: 0; font: 600 13px/1.35 var(--sans); letter-spacing: -.01em; }
.ex-rpe { font: 600 8px var(--mono); letter-spacing: .06em; color: var(--muted); white-space: nowrap; }
.log-inline { display: inline-flex; align-items: baseline; justify-content: flex-end; gap: 6px; min-width: 58px; min-height: 30px; padding: 2px 0 2px 10px; border: 0; border-left: 1px solid var(--line-soft); border-radius: 0; background: none; color: var(--muted); cursor: pointer; white-space: nowrap; }
.log-inline small { flex: 0 0 auto; font: 700 8px var(--mono); letter-spacing: .1em; white-space: nowrap; }
.log-inline b { font: 600 9px var(--mono); font-variant-numeric: tabular-nums; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
.log-inline.done { color: var(--ct-deload); }
.log-inline.done small::before { content: '✓ '; }
.log-inline[aria-expanded='true'] { color: var(--accent); }
.log-inline:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.ex-sets { margin-top: 3px; padding-left: 30px; }
.ex-set { display: grid; grid-template-columns: 58px 70px minmax(0, 1fr) 46px; align-items: baseline; gap: 8px; padding: 3px 0; }
.set-tag { font: 700 7.5px var(--mono); letter-spacing: .1em; color: var(--muted); text-transform: uppercase; white-space: nowrap; }
.ex-set.top .set-tag { color: var(--accent); }
.ex-set.backoff .set-tag { color: var(--ct-strength); }
.set-scheme { display: inline-flex; align-items: baseline; gap: 2px; font: 700 13px var(--mono); font-variant-numeric: tabular-nums; }
.set-scheme i { font-style: normal; font-size: 9px; color: var(--muted); margin: 0 1px; }
.set-load { text-align: right; font: 700 17px/1 var(--mono); letter-spacing: -.03em; font-variant-numeric: tabular-nums; }
.set-load b { font-weight: 700; }
.set-load small { font: 8px var(--mono); color: var(--muted); margin-left: 2px; }
.set-pct { text-align: right; font: 600 9px var(--mono); color: var(--gold); }
.set-pct small { font-size: 7px; margin-left: 1px; }
.system-load { font-size: 11px; color: var(--muted); line-height: 1.6; overflow-wrap: anywhere; margin-top: 6px; padding-left: 30px; }
.logged-system { display: block; }
@media (max-width: 420px) {
  .ex-set { grid-template-columns: 52px 62px minmax(0, 1fr) 40px; gap: 6px; }
  .set-load { font-size: 15px; }
  .ex-name { font-size: 12.5px; }
  .log-inline b { display: none; }
}
</style>
