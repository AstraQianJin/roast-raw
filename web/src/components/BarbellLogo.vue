<script setup>
defineProps({ size: { type: Number, default: 200 } });
</script>

<template>
  <svg class="barbell-logo" :width="size" :height="Math.round(size * 0.28)" viewBox="0 0 200 56" role="img" aria-label="Roast Raw loaded barbell">
    <rect x="18" y="26" width="164" height="4" rx="2" fill="var(--anatomy-outline)" />
    <rect x="72" y="21" width="5" height="14" rx="1" fill="var(--anatomy-outline)" />
    <rect x="123" y="21" width="5" height="14" rx="1" fill="var(--anatomy-outline)" />
    <rect x="22" y="6" width="12" height="44" rx="2" fill="var(--plate-25)" />
    <rect x="36" y="10" width="11" height="36" rx="2" fill="var(--plate-20)" />
    <rect x="49" y="15" width="10" height="26" rx="2" fill="var(--plate-15)" />
    <rect x="61" y="19" width="9" height="18" rx="2" fill="var(--plate-10)" />
    <rect x="166" y="6" width="12" height="44" rx="2" fill="var(--plate-25)" />
    <rect x="153" y="10" width="11" height="36" rx="2" fill="var(--plate-20)" />
    <rect x="141" y="15" width="10" height="26" rx="2" fill="var(--plate-15)" />
    <rect x="130" y="19" width="9" height="18" rx="2" fill="var(--plate-10)" />
  </svg>
</template>

<style scoped>
.barbell-logo { display: block; max-width: 100%; height: auto; }
.barbell-logo rect { stroke: rgba(0, 0, 0, .22); stroke-width: .6; }
</style>