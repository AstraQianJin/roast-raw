<script setup>
import { ref } from 'vue';
import ShareCard from './ShareCard.vue';

defineProps({
  plan: { type: Object, required: true },
  logs: { type: Object, default: () => ({}) },
  defaultDate: { type: String, required: true },
});

const open = ref(false);
const dialog = ref(null);

function show() {
  open.value = true;
  dialog.value?.showModal();
}
</script>

<template>
  <div class="share-row">
    <button type="button" class="share-open" data-testid="share-open" @click="show">Share card</button>
  </div>
  <dialog ref="dialog" class="share-dialog" aria-label="Daily share card" @close="open = false">
    <div class="share-dialog-in">
      <button type="button" class="share-close" aria-label="Close share card" @click="dialog.close()">×</button>
      <ShareCard v-if="open" :plan="plan" :logs="logs" :default-date="defaultDate" />
    </div>
  </dialog>
</template>

<style scoped>
.share-row { display: flex; justify-content: center; padding: 22px 0 6px; }
.share-open { min-height: 36px; padding: 0 2px; border: 0; border-bottom: 1px solid var(--line2); border-radius: 0; font: 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); background: none; }
.share-open:hover { color: var(--ink); border-color: var(--ink); background: none; }
.share-dialog { width: min(560px, 94vw); max-height: 90vh; padding: 0; border: 1px solid var(--line); background: var(--panel); color: var(--ink); overflow: auto; }
.share-dialog::backdrop { background: rgba(17, 17, 17, .55); }
.share-dialog-in { position: relative; padding: 18px 16px 20px; }
.share-close { position: absolute; top: 8px; right: 8px; z-index: 2; width: 36px; min-height: 36px; padding: 0; border: 1px solid var(--line2); border-radius: 50%; font-size: 18px; line-height: 1; color: var(--muted); }
</style>
