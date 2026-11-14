<script setup>
import { ref, watch } from 'vue';
import LogEditor from './LogEditor.vue';
import BarbellStrip from './BarbellStrip.vue';

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
const topLoad = row => row.segments.reduce((max, segment) => segment.load !== null && segment.load > max ? segment.load : max, 0);
const logSummary = row => {
  const log = props.logs[logKey(row)];
  if (!log) return null;
  if (log.sets === 0) return 'SKIPPED';
  return `${display(log.load)} × ${log.reps} × ${log.sets}${log.rpe !== null && log.rpe !== undefined ? ` @ ${display(log.rpe)}` : ''}`;
};
</script>

<template>
  <div class="exercise-rows">
    <template v-for="(label, role) in roleNames" :key="role">
      <template v-if="rows.some(row => row.bucket === role)">
        <div class="section-heading"><span class="section-label">{{ label }}</span><span class="mono">{{ String(rows.filter(row => row.bucket === role).length).padStart(2, '0') }}</span></div>
        <article v-for="row in rows.filter(row => row.bucket === role)" :key="`${row.week}-${row.day}-${row.seq}`" :class="['exercise', row.bucket]">
          <div class="exercise-heading"><span class="exercise-index">{{ String(row.seq).padStart(2, '0') }}</span><span class="exercise-name">{{ row.nameEn }}</span><span class="rpe">RPE {{ display(row.targetRpe) }}</span></div>
          <BarbellStrip v-if="role === 'main' && topLoad(row) > 0" class="exercise-barbell" :load="topLoad(row)" :collar-pair="0" />
          <div class="exercise-foot">
            <div v-for="(segment, index) in row.segments" :key="index" class="prescription">
              <span class="lbox"><small>{{ role === 'accessory' ? 'LOAD' : 'LOAD KG' }}</small><b class="weight">{{ role === 'accessory' ? '—' : display(segment.load) }}</b></span>
              <span class="rbox"><small>SETS × REPS</small><b class="reps">{{ segment.sets }} × {{ segment.reps }}<template v-if="segment.unit"> {{ segment.unit }}</template></b></span>
              <span v-if="segment.pct !== null && role !== 'accessory'" class="pct-chip">{{ display(segment.pct) }}%</span>
            </div>
            <button
              v-if="!readonly"
              type="button"
              class="log-toggle"
              :class="{ done: !!logs[logKey(row)] }"
              :aria-expanded="openEditor === editorKey(row)"
              @click="toggleEditor(row)"
            ><small>{{ openEditor === editorKey(row) ? 'CLOSE' : 'LOG' }}</small><b v-if="logSummary(row)">{{ logSummary(row) }}</b><b v-else>—</b></button>
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
.exercise-barbell { margin: 10px 0 2px; }
.exercise-foot { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; margin-top: 10px; }
.prescription { display: flex; gap: 8px; align-items: stretch; flex: 1 1 auto; min-width: 0; }
.lbox, .rbox, .log-toggle {
  display: flex; flex-direction: column; justify-content: center; gap: 2px;
  min-height: 48px; padding: 6px 10px; border-radius: 9px;
  background: var(--inset); border: 1px solid var(--line-soft);
}
.lbox { flex: 0 1 auto; }
.rbox { flex: 1 1 auto; min-width: 84px; }
.lbox small, .rbox small, .log-toggle small { font: 800 8px var(--mono); letter-spacing: .1em; color: var(--muted); }
.lbox b { font: 800 19px var(--mono); letter-spacing: -.03em; font-variant-numeric: tabular-nums; }
.rbox b { font: 700 15px var(--mono); font-variant-numeric: tabular-nums; }
.pct-chip { align-self: center; font: 800 9px var(--mono); color: var(--gold); border: 1px solid var(--gold-line); background: var(--gold-soft); border-radius: 6px; padding: 3px 6px; white-space: nowrap; }
.log-toggle {
  flex: 1 1 100%; flex-direction: row; align-items: center; justify-content: flex-start; gap: 8px;
  min-width: 44px; max-width: 100%; cursor: pointer; text-align: left;
  color: var(--ink); font: inherit; white-space: normal; overflow-wrap: anywhere;
}
.log-toggle b { font: 700 13px var(--mono); font-variant-numeric: tabular-nums; }
.log-toggle.done { border-color: var(--gold-line); }
.log-toggle.done small { color: var(--gold); }
.log-toggle.done small::before { content: '✓ '; }
.log-toggle[aria-expanded='true'] { border-color: var(--accent); }
.log-toggle[aria-expanded='true'] small { color: var(--accent); }
.log-toggle:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.system-load { font-size: 12px; color: var(--muted); line-height: 1.6; overflow-wrap: anywhere; margin-top: 8px; }
.logged-system { display: block; }
@media (min-width: 560px) {
  .log-toggle { flex: 1 1 180px; }
}
</style>