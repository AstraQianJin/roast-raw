<script setup>
import { computed } from 'vue';

const props = defineProps({
  load: { type: Number, default: null },
  barKg: { type: Number, default: 20 },
  collarPair: { type: Number, default: 5 },
  maxPlates: { type: Number, default: 7 },
});

const PLATES = [
  { kg: 25, color: 'var(--plate-25, #E53935)', ink: 'var(--ink-on-accent, #fff)', h: 30, w: 13, micro: false },
  { kg: 20, color: 'var(--plate-20, #1E88E5)', ink: 'var(--ink-on-accent, #fff)', h: 30, w: 11, micro: false },
  { kg: 15, color: 'var(--plate-15, #FFB300)', ink: 'var(--plate-15-ink, #1A1200)', h: 26, w: 10, micro: false },
  { kg: 10, color: 'var(--plate-10, #43A047)', ink: 'var(--ink-on-accent, #fff)', h: 22, w: 8.5, micro: false },
  { kg: 5, color: 'var(--plate-5, #E7ECF3)', ink: 'var(--plate-5-ink, #111)', h: 17, w: 7, micro: false },
  { kg: 2.5, color: 'var(--plate-2p5, #181C22)', h: 14, w: 4.5, micro: true },
  { kg: 1.25, color: 'var(--plate-1p25, #7C8084)', h: 11, w: 3.8, micro: true },
  { kg: 1, color: 'var(--plate-1, #8E9196)', h: 10, w: 3.4, micro: true },
  { kg: 0.75, color: 'var(--plate-0p75, #A0A3A7)', h: 9.5, w: 3, micro: true },
  { kg: 0.5, color: 'var(--plate-0p5, #B4B6BA)', h: 9, w: 2.6, micro: true },
  { kg: 0.25, color: 'var(--plate-0p25, #C8CACE)', h: 8, w: 2.2, micro: true },
];

function solvePerSide(total, bar, collar) {
  let perSide = Math.round(((total - bar - collar) / 2) * 1000) / 1000;
  if (!(perSide > 0)) return { plates: [], remainder: 0 };
  const plates = [];
  for (const plate of PLATES) {
    while (perSide >= plate.kg - 1e-9) {
      plates.push(plate);
      perSide = Math.round((perSide - plate.kg) * 1000) / 1000;
    }
  }
  return { plates, remainder: perSide };
}

const solved = computed(() => props.load === null ? null : solvePerSide(props.load, props.barKg, props.collarPair));
const visible = computed(() => solved.value ? solved.value.plates.slice(0, props.maxPlates) : []);
const hiddenCount = computed(() => solved.value ? Math.max(0, solved.value.plates.length - props.maxPlates) : 0);
const ariaLabel = computed(() => {
  if (props.load === null) return 'Barbell load not prescribed';
  if (!solved.value.plates.length) return `Empty bar, ${props.load} kg total`;
  const counts = {};
  for (const plate of solved.value.plates) counts[plate.kg] = (counts[plate.kg] || 0) + 1;
  const side = Object.entries(counts).map(([kg, count]) => `${count}×${kg}`).join(' + ');
  return `${props.load} kg total: ${props.barKg} kg bar + ${props.collarPair} kg collars + per side ${side} kg`;
});
</script>

<template>
  <div :class="['plate-strip', { empty: solved && !solved.plates.length }]" data-k="barbell" role="img" :aria-label="ariaLabel" data-testid="plate-strip">
    <template v-if="solved && solved.plates.length">
      <span v-for="(plate, index) in visible" :key="index" class="pb" :style="{ height: plate.h + 'px', width: plate.w + 'px', background: plate.color }">
        <i v-if="!plate.micro" :style="{ color: plate.ink }">{{ plate.kg }}</i>
      </span>
      <span class="pv-clamp" aria-hidden="true"></span>
      <span v-if="hiddenCount" class="pv-more" aria-hidden="true"></span>
    </template>
  </div>
</template>

<style scoped>
.plate-strip { flex: 1; min-width: 34px; display: flex; align-items: center; justify-content: flex-start; gap: 2px; height: 32px; padding: 0 4px; overflow: hidden; position: relative;
  background: linear-gradient(180deg, #525B69 0%, #C7CFDA 40%, #3B424E 100%) left 4px center / calc(100% - 8px) 3px no-repeat; }
.plate-strip.empty { background: none; justify-content: center; }
.plate-strip.empty::after { content: ''; width: 9px; height: 21px; border-radius: 2px; border: 2px solid var(--dim2, #8C8C86); opacity: .6; }
.pb { flex: none; border-radius: 1px; display: grid; place-items: center; box-shadow: inset 0 1px 0 rgba(255, 255, 255, .42), 1px 0 2px rgba(0, 0, 0, .55); }
.pb i { font: 700 7px var(--mono, monospace); font-style: normal; line-height: 1; }
.pv-clamp { position: relative; width: 5px; height: 11px; border-radius: 1.5px; margin-left: 1px; flex: none; background: var(--gear-metal, #9AA3AF); }
.pv-clamp::before, .pv-clamp::after { content: ''; position: absolute; left: -1px; right: -1px; height: 2px; background: var(--gear-metal, #9AA3AF); }
.pv-clamp::before { top: 1.5px; }
.pv-clamp::after { bottom: 1.5px; }
.pv-more { width: 2px; height: 2px; border-radius: 1px; background: var(--dim, #5E5E59); flex: none; margin: 0 3px; box-shadow: 4px 0 0 var(--dim, #5E5E59), 8px 0 0 var(--dim, #5E5E59); }
</style>