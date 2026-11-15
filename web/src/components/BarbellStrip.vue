<script setup>
import { computed } from 'vue';
import { solveLoad, sideText, plateLabel } from '../plate-load.js';

const props = defineProps({
  load: { type: Number, default: null },
  barKg: { type: Number, default: 20 },
  collarPair: { type: Number, default: 0 },
});

const solved = computed(() => props.load === null ? null : solveLoad(props.load, props.barKg, props.collarPair));
const sides = computed(() => solved.value
  ? [{ key: 'A', side: solved.value.sideA }, { key: 'B', side: solved.value.sideB }]
  : []);
const microText = computed(() => (solved.value ? solved.value.microUsed.map(plateLabel).join(' + ') : ''));
const ariaLabel = computed(() => {
  if (props.load === null) return 'Barbell load not prescribed';
  if (!solved.value.plateTotal) return `Empty bar, ${plateLabel(solved.value.load)} kg total`;
  const base = `${plateLabel(solved.value.load)} kg total: ${plateLabel(solved.value.barKg)} kg bar`
    + `${solved.value.collarPair ? ` + ${plateLabel(solved.value.collarPair)} kg collars` : ''}`;
  const built = solved.value.asymmetric
    ? `asymmetric single-side loading, side A ${sideText(solved.value.sideA)}, side B ${sideText(solved.value.sideB)}`
    : `per side ${sideText(solved.value.sideA)}`;
  const micro = solved.value.microUsed.length ? `, micro plates ${microText.value}` : '';
  const short = solved.value.shortKg > 0 ? `, ${plateLabel(solved.value.shortKg)} kg cannot be loaded` : '';
  return `${base}, ${built}${micro}${short}`;
});
</script>

<template>
  <div
    :class="['plate-strip', { empty: solved && !solved.plateTotal, asym: solved && solved.asymmetric, short: solved && solved.shortKg > 0 }]"
    data-k="barbell" role="img" :aria-label="ariaLabel" data-testid="plate-strip"
    :data-asymmetric="solved ? String(solved.asymmetric) : 'false'"
    :data-micro="microText"
    :data-short="solved ? String(solved.shortKg) : ''"
  >
    <template v-if="solved && solved.plateTotal">
      <div v-for="item in sides" :key="item.key" class="ps-row">
        <span v-if="solved.asymmetric" class="ps-side" aria-hidden="true">{{ item.key }}</span>
        <span
          v-for="(plate, index) in item.side.plates" :key="`${item.key}-${index}`"
          :class="['pb', { chip: plate.kg <= 1.25 }]"
          :style="{ height: plate.h + 'px', width: plate.w + 'px', background: `var(${plate.token})` }"
          aria-hidden="true"
        >
          <i v-if="plate.kg >= 5" :style="{ color: `var(${plate.ink})` }">{{ plateLabel(plate.kg) }}</i>
          <em v-else-if="plate.kg <= 1.25">{{ plateLabel(plate.kg) }}</em>
        </span>
        <span v-if="solved.asymmetric" class="ps-kg" aria-hidden="true">{{ plateLabel(item.side.loaded) }} kg</span>
      </div>
      <span class="pv-clamp" aria-hidden="true"></span>
      <span v-if="solved.shortKg > 0" class="ps-short" aria-hidden="true">−{{ plateLabel(solved.shortKg) }}</span>
    </template>
  </div>
</template>

<style scoped>
.plate-strip { flex: 1; min-width: 34px; display: flex; align-items: center; justify-content: flex-start; gap: 2px; min-height: 32px; padding: 0 4px; overflow: hidden; position: relative;
  background: linear-gradient(180deg, #525B69 0%, #C7CFDA 40%, #3B424E 100%) left 4px center / calc(100% - 8px) 3px no-repeat; }
.plate-strip.asym { flex-direction: column; align-items: stretch; gap: 1px; justify-content: center; padding: 2px 4px;
  background: linear-gradient(180deg, #525B69 0%, #C7CFDA 40%, #3B424E 100%) left 4px center / calc(100% - 8px) 2px no-repeat; }
.plate-strip.empty { background: none; justify-content: center; }
.plate-strip.empty::after { content: ''; width: 9px; height: 21px; border-radius: 2px; border: 2px solid var(--dim2, #8C8C86); opacity: .6; }
.ps-row { display: flex; align-items: center; gap: 2px; min-width: 0; }
.ps-side { flex: none; font: 700 7px var(--mono); letter-spacing: .06em; color: var(--muted); width: 7px; }
.ps-kg { flex: none; margin-left: auto; padding-left: 4px; font: 600 7.5px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.pb { flex: none; border-radius: 1px; display: grid; place-items: center; box-shadow: inset 0 1px 0 rgba(255, 255, 255, .42), 1px 0 2px rgba(0, 0, 0, .55); }
.pb i { font: 700 7px var(--mono); font-style: normal; line-height: 1; }
/* Micro plates carry a legible number; without it a 0.5 kg slab is just a sliver. */
.pb.chip { min-width: 26px !important; height: 16px !important; border-radius: 2px; box-shadow: inset 0 0 0 1px rgba(17, 17, 17, .28); }
.pb.chip em { font: 700 8px var(--mono); font-style: normal; line-height: 1; color: var(--ink); letter-spacing: -.01em; }
.pv-clamp { position: relative; width: 5px; height: 11px; border-radius: 1.5px; margin-left: 1px; flex: none; background: var(--gear-metal, #9AA3AF); align-self: center; }
.pv-clamp::before, .pv-clamp::after { content: ''; position: absolute; left: -1px; right: -1px; height: 2px; background: var(--gear-metal, #9AA3AF); }
.pv-clamp::before { top: 1.5px; }
.pv-clamp::after { bottom: 1.5px; }
.ps-short { flex: none; margin-left: 2px; padding: 0 3px; border: 1px solid var(--accent); color: var(--accent); font: 700 7.5px var(--mono); line-height: 1.4; }
@media (max-width: 420px) {
  .pb.chip { min-width: 24px !important; }
  .ps-kg { font-size: 7px; }
}
</style>
