<script setup>
defineOptions({ inheritAttrs: false });
</script>

<template>
  <svg :class="$attrs.class" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <ellipse cx="12" cy="12" rx="7.1" ry="9.1" transform="rotate(22 12 12)" fill="currentColor" />
    <path d="M13.3 5.1c-2.3 2.2-2.3 4.4 0 6.9 2.3 2.5 2.3 4.6 0 7" fill="none" stroke="var(--bg, #F1F0EB)" stroke-width="1.8" stroke-linecap="round" />
  </svg>
</template>
