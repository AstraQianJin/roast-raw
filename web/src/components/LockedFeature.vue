<script setup>
defineProps({
  label: { type: String, required: true },
  tier: { type: String, required: true },
  compact: { type: Boolean, default: false },
});
</script>

<template>
  <section v-if="compact" class="locked-feature compact" :data-required-tier="tier" role="note">
    <span class="section-label">{{ tier.toUpperCase() }}</span>
    <p><strong>{{ label }}</strong> · locked on this tier</p>
    <RouterLink to="/archive#account" class="inline-link">Redeem a code</RouterLink>
  </section>
  <section v-else class="locked-feature" :data-required-tier="tier" role="note">
    <span class="section-label">{{ tier.toUpperCase() }} FEATURE</span>
    <p><strong>{{ label }}</strong> unlocks at {{ tier.charAt(0).toUpperCase() + tier.slice(1) }} or higher. Your saved records stay readable and exportable.</p>
    <RouterLink to="/archive#account" class="inline-link">Redeem a code</RouterLink>
  </section>
</template>

<style scoped>
.locked-feature { margin: 14px 0; padding: 14px 16px; border: 1px dashed var(--line); border-radius: 14px; color: var(--muted); }
.locked-feature p { margin: 6px 0 8px; font-size: 13px; line-height: 1.5; color: var(--ink); }
.locked-feature.compact { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; margin: 10px 0; padding: 9px 12px 9px 11px; border: 0; border-left: 3px solid var(--line); border-radius: 0; background: var(--panel2); }
.locked-feature.compact p { margin: 0; font-size: 12px; }
.locked-feature.compact .section-label { font-size: 10px; letter-spacing: .08em; }
.locked-feature.compact .inline-link { margin-left: auto; font-size: 12px; }
</style>
