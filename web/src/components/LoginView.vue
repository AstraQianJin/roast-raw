<script setup>
import { onMounted, ref } from 'vue';
import { animate } from '@motionone/dom';
import packageInfo from '../../package.json';
import BarbellLogo from './BarbellLogo.vue';

const [major, , patch] = packageInfo.version.split('.');
const releaseVersion = `${major}.${patch.padStart(2, '0')}`;
const props = defineProps({ next: { type: String, default: '' } });
const emit = defineEmits(['authed']);

const username = ref('');
const password = ref('');
const show = ref(false);
const error = ref('');
const busy = ref(false);
const card = ref(null);
const demoWeeks = ['hyper', 'hyper', 'hyper', 'hyper', 'strength', 'strength', 'strength', 'deload', 'transmute', 'transmute', 'peak', 'deload', 'test'];
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

function shake() {
  if (card.value && !reduce()) {
    animate(card.value, { transform: ['translateX(0)', 'translateX(-7px)', 'translateX(6px)', 'translateX(-4px)', 'translateX(0)'] }, { duration: .34, easing: 'ease-in-out' });
  }
}

async function submit() {
  error.value = '';
  if (!username.value.trim() || !password.value) {
    error.value = 'Enter your username and password.';
    shake();
    return;
  }
  busy.value = true;
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      error.value = data.error || 'Sign in failed. Check your details and try again.';
      shake();
      return;
    }
    emit('authed', { ...data, next: props.next });
  } catch {
    error.value = 'Connection interrupted. Your details were not sent. Try again.';
    shake();
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  if (card.value && !reduce()) {
    animate(card.value, { opacity: [0, 1], transform: ['translateY(14px)', 'translateY(0)'] }, { duration: .5, easing: [.22, 1, .36, 1] });
  }
});
</script>

<template>
  <div class="auth" data-testid="login">
    <div ref="card" class="auth-card">
      <div class="auth-head">
        <BarbellLogo :size="184" />
        <span class="auth-kicker">ROAST RAW · PRIVATE RELEASE</span>
      </div>
      <h1>Welcome <em>back.</em></h1>
      <p class="auth-lede">Sign in to open your training journal — the fixed plan, the actual log and every set you have recorded.</p>
      <form class="auth-form" novalidate @submit.prevent="submit">
        <label class="auth-field">
          <span class="auth-label">USERNAME</span>
          <input v-model="username" type="text" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" placeholder="Astra" :disabled="busy" />
        </label>
        <label class="auth-field">
          <span class="auth-label">PASSWORD</span>
          <span class="auth-pass">
            <input v-model="password" :type="show ? 'text' : 'password'" autocomplete="current-password" placeholder="Your password" :disabled="busy" />
            <button type="button" class="auth-eye" :aria-label="show ? 'Hide password' : 'Show password'" :aria-pressed="show" @click="show = !show">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                <path v-if="show" d="M4 4l16 16" />
              </svg>
            </button>
          </span>
        </label>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <button class="auth-submit" type="submit" :disabled="busy">
          <span>{{ busy ? 'Signing in…' : 'Sign in' }}</span><span class="ar" aria-hidden="true">→</span>
        </button>
      </form>
      <p class="auth-switch">New here? <RouterLink to="/register">Create an account</RouterLink></p>
      <div class="auth-strip" aria-hidden="true"><i v-for="(phase, index) in demoWeeks" :key="index" :class="['ct', phase]"></i></div>
    </div>
    <p class="auth-fine">Single-user release {{ releaseVersion }} · Records live on your server · No offline cache, no sync service.</p>
  </div>
</template>