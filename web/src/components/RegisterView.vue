<script setup>
import { onMounted, ref } from 'vue';
import { animate } from '@motionone/dom';
import packageInfo from '../../package.json';
import BarbellLogo from './BarbellLogo.vue';

const [major, , patch] = packageInfo.version.split('.');
const releaseVersion = `${major}.${patch.padStart(2, '0')}`;
const emit = defineEmits(['authed']);

const code = ref('');
const username = ref('');
const password = ref('');
const confirm = ref('');
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
  const name = username.value.trim();
  if (!code.value.trim()) {
    error.value = 'Enter your invite code. Registration is by invitation.';
    shake();
    return;
  }
  if (!/^[A-Za-z][A-Za-z0-9_-]{1,63}$/.test(name)) {
    error.value = 'Username must start with a letter and use only letters, numbers, underscores or hyphens (2–64 characters).';
    shake();
    return;
  }
  if (password.value.length < 6) {
    error.value = 'Password must be at least 6 characters.';
    shake();
    return;
  }
  if (password.value !== confirm.value) {
    error.value = 'The two passwords do not match.';
    shake();
    return;
  }
  busy.value = true;
  try {
    const response = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: name, password: password.value, invite_code: code.value.trim() }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      error.value = data.error || 'Could not create the account. Try again.';
      shake();
      return;
    }
    emit('authed', data);
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
  <div class="auth" data-testid="register">
    <div ref="card" class="auth-card">
      <div class="auth-head">
        <BarbellLogo :size="184" />
        <span class="auth-kicker">ROAST RAW · PRIVATE RELEASE</span>
      </div>
      <h1>Create your <em>account.</em></h1>
      <p class="auth-lede">Registration is by invitation. Enter your invite code, then choose a username and a password to open your own journal.</p>
      <form class="auth-form" novalidate @submit.prevent="submit">
        <label class="auth-field">
          <span class="auth-label">INVITE CODE</span>
          <input v-model="code" type="text" name="invite_code" autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false" placeholder="RR-PLUS-XXXX-XXXX" :disabled="busy" />
          <span class="auth-hint">The code sets your starting tier. Not case-sensitive.</span>
        </label>
        <label class="auth-field">
          <span class="auth-label">USERNAME</span>
          <input v-model="username" type="text" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" placeholder="e.g. Astra" :disabled="busy" />
          <span class="auth-hint">Starts with a letter · letters, numbers, _ or - · 2–64 characters. Not case-sensitive.</span>
        </label>
        <label class="auth-field">
          <span class="auth-label">PASSWORD</span>
          <span class="auth-pass">
            <input v-model="password" :type="show ? 'text' : 'password'" autocomplete="new-password" placeholder="At least 6 characters" :disabled="busy" />
            <button type="button" class="auth-eye" :aria-label="show ? 'Hide password' : 'Show password'" :aria-pressed="show" @click="show = !show">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                <path v-if="show" d="M4 4l16 16" />
              </svg>
            </button>
          </span>
        </label>
        <label class="auth-field">
          <span class="auth-label">CONFIRM PASSWORD</span>
          <input v-model="confirm" :type="show ? 'text' : 'password'" autocomplete="new-password" placeholder="Repeat the password" :disabled="busy" />
        </label>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <button class="auth-submit" type="submit" :disabled="busy">
          <span>{{ busy ? 'Creating account…' : 'Create account' }}</span><span class="ar" aria-hidden="true">→</span>
        </button>
      </form>
      <p class="auth-switch">Already have an account? <RouterLink to="/login">Sign in</RouterLink></p>
      <div class="auth-strip" aria-hidden="true"><i v-for="(phase, index) in demoWeeks" :key="index" :class="['ct', phase]"></i></div>
    </div>
    <p class="auth-fine">Release {{ releaseVersion }} · Registration needs an invite code · No offline cache, no sync service.</p>
  </div>
</template>