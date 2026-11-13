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
</script>

<template>
  <div class="exercise-rows">
    <template v-for="(label, role) in roleNames" :key="role">
      <template v-if="rows.some(row => row.bucket === role)">
        <div class="section-heading"><span class="section-label">{{ label }}</span><span class="mono">{{ String(rows.filter(row => row.bucket === role).length).padStart(2, '0') }}</span></div>
        <article v-for="row in rows.filter(row => row.bucket === role)" :key="`${row.week}-${row.day}-${row.seq}`" :class="['exercise', row.bucket]">
          <div class="exercise-heading"><span class="exercise-index">{{ String(row.seq).padStart(2, '0') }}</span><span class="exercise-name">{{ row.nameEn }}</span><span class="rpe">RPE {{ display(row.targetRpe) }}</span></div>
          <div v-for="(segment, index) in row.segments" :key="index" class="prescription">
            <span class="segment-label">{{ segment.label }}</span>
            <span class="reps">{{ segment.sets }} × {{ segment.reps }}<small v-if="segment.unit"> {{ segment.unit }}</small></span>
            <span class="weight">{{ role === 'accessory' ? '—' : display(segment.load) }}<small v-if="role !== 'accessory' && segment.load !== null"> kg</small></span>
            <small>{{ segment.pct === null || role === 'accessory' ? '' : `${display(segment.pct)}%` }}</small>
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
          <button
            v-if="!readonly"
            type="button"
            class="log-toggle"
            :aria-expanded="openEditor === editorKey(row)"
            @click="toggleEditor(row)"
          >{{ openEditor === editorKey(row) ? 'Close log' : `Log ${row.nameEn}` }}</button>
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
.system-load { font-size: 12px; color: var(--muted); line-height: 1.6; overflow-wrap: anywhere; }
.logged-system { display: block; }
.log-toggle {
  box-sizing: border-box;
  min-height: 44px;
  min-width: 44px;
  max-width: 100%;
  margin-top: 12px;
  padding: 8px 12px;
  white-space: normal;
  overflow-wrap: anywhere;
  text-align: left;
}
.log-toggle:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
