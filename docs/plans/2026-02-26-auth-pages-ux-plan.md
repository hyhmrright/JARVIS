# Auth Pages UX Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add password show/hide toggle and real-time field-level validation to LoginPage and RegisterPage.

**Architecture:** Pure frontend changes. Add validation composable logic inline in each page component (no shared composable needed — the two pages have slightly different fields). Add CSS classes for error states to `components.css`. Add i18n validation keys to all 6 locale files.

**Tech Stack:** Vue 3 Composition API, vue-i18n, inline SVG icons, CSS transitions. No new dependencies.

**Note:** This project has no frontend test framework (no vitest/jest). Verification is done via `vue-tsc --noEmit` (type check) and `bun run lint` (ESLint). Manual browser testing is noted where relevant.

---

### Task 1: Add validation i18n keys to all 6 locale files

**Files:**
- Modify: `frontend/src/locales/zh.json`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/locales/ja.json`
- Modify: `frontend/src/locales/ko.json`
- Modify: `frontend/src/locales/fr.json`
- Modify: `frontend/src/locales/de.json`

**Step 1: Add `validation` section to each locale file**

Add the following `"validation"` key as a new top-level section at the end of each JSON file (before the closing `}`):

**zh.json:**
```json
  "validation": {
    "emailRequired": "请输入邮箱地址",
    "emailInvalid": "请输入有效的邮箱地址",
    "passwordRequired": "请输入密码",
    "passwordMinLength": "密码至少需要 8 个字符"
  }
```

**en.json:**
```json
  "validation": {
    "emailRequired": "Please enter your email address",
    "emailInvalid": "Please enter a valid email address",
    "passwordRequired": "Please enter your password",
    "passwordMinLength": "Password must be at least 8 characters"
  }
```

**ja.json:**
```json
  "validation": {
    "emailRequired": "メールアドレスを入力してください",
    "emailInvalid": "有効なメールアドレスを入力してください",
    "passwordRequired": "パスワードを入力してください",
    "passwordMinLength": "パスワードは8文字以上必要です"
  }
```

**ko.json:**
```json
  "validation": {
    "emailRequired": "이메일 주소를 입력해 주세요",
    "emailInvalid": "유효한 이메일 주소를 입력해 주세요",
    "passwordRequired": "비밀번호를 입력해 주세요",
    "passwordMinLength": "비밀번호는 8자 이상이어야 합니다"
  }
```

**fr.json:**
```json
  "validation": {
    "emailRequired": "Veuillez saisir votre adresse e-mail",
    "emailInvalid": "Veuillez saisir une adresse e-mail valide",
    "passwordRequired": "Veuillez saisir votre mot de passe",
    "passwordMinLength": "Le mot de passe doit contenir au moins 8 caractères"
  }
```

**de.json:**
```json
  "validation": {
    "emailRequired": "Bitte geben Sie Ihre E-Mail-Adresse ein",
    "emailInvalid": "Bitte geben Sie eine gültige E-Mail-Adresse ein",
    "passwordRequired": "Bitte geben Sie Ihr Passwort ein",
    "passwordMinLength": "Das Passwort muss mindestens 8 Zeichen lang sein"
  }
```

**Step 2: Verify JSON is valid**

Run: `cd /Users/hyh/code/JARVIS/.worktrees/feature-frontend/frontend && for f in src/locales/*.json; do echo "--- $f ---"; node -e "JSON.parse(require('fs').readFileSync('$f','utf8')); console.log('OK')"; done`

Expected: all 6 files print `OK`.

**Step 3: Commit**

```bash
git add frontend/src/locales/*.json
git commit -m "feat(i18n): add validation error messages for all 6 locales"
```

---

### Task 2: Add field error and input error CSS styles

**Files:**
- Modify: `frontend/src/assets/styles/components.css`

**Step 1: Add error state styles**

Add these rules at the end of `components.css`, before the closing `@media (prefers-reduced-motion)` block (i.e., insert before line 177):

```css
/* ── Field Validation Errors ── */
.input-error {
  border-color: rgba(232, 93, 93, 0.3) !important;
}

.input-error:focus {
  border-color: var(--danger) !important;
  box-shadow: 0 0 0 3px var(--danger-a10) !important;
}

.field-error {
  color: var(--danger);
  font-size: 13px;
  line-height: 1.4;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  transition:
    max-height 0.25s ease,
    opacity 0.25s ease;
}

.field-error.visible {
  max-height: 40px;
  opacity: 1;
}

/* ── Password Input Wrapper ── */
.password-wrapper {
  position: relative;
}

.password-wrapper input {
  padding-right: 44px;
}

.password-toggle {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: none;
  border: none;
  padding: 0;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.2s ease;
}

.password-toggle:hover {
  color: var(--text-secondary);
}

.password-toggle:disabled {
  opacity: 1;
}
```

**Step 2: Verify type-check still passes**

Run: `cd /Users/hyh/code/JARVIS/.worktrees/feature-frontend/frontend && bun run type-check`

Expected: exit code 0 (CSS changes don't affect type-check, but confirms no regressions).

**Step 3: Commit**

```bash
git add frontend/src/assets/styles/components.css
git commit -m "feat(ui): add field error and password toggle CSS styles"
```

---

### Task 3: Update LoginPage with password toggle and validation

**Files:**
- Modify: `frontend/src/pages/LoginPage.vue`

**Step 1: Replace the entire LoginPage.vue content**

The new `LoginPage.vue` should contain:

**Template changes:**
- Email input: add `@blur` and `@input` handlers, `:class="{ 'input-error': emailError }"`, remove `required` attribute (validation is now manual). Add `<p class="field-error" :class="{ visible: emailError }">{{ emailError }}</p>` after the input.
- Password input: wrap in `<div class="password-wrapper">`, change `:type="showPassword ? 'text' : 'password'"`, add `@blur` and `@input` handlers, `:class="{ 'input-error': passwordError }"`, remove `required`. Add the toggle button with inline SVG. Add `<p class="field-error">` after the wrapper.
- Submit button: add `:disabled="loading || !isFormValid"`.
- Keep the existing `<p v-if="error" class="error-msg">` for backend errors.

**Script changes:**
- Add `showPassword` ref (boolean, default `false`)
- Add `emailTouched`, `passwordTouched` refs (boolean, default `false`)
- Add `emailError`, `passwordError` computed properties:
  - `emailError`: if not touched → `""`. If empty → `t("validation.emailRequired")`. If invalid format → `t("validation.emailInvalid")`. Else `""`.
  - `passwordError`: if not touched → `""`. If empty → `t("validation.passwordRequired")`. If < 8 chars → `t("validation.passwordMinLength")`. Else `""`.
- Add `isFormValid` computed: `email.value.length > 0 && !emailError.value && password.value.length > 0 && !passwordError.value`
- Email regex: `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`
- In `handleLogin()`, add at the top: set both touched to `true`, if `!isFormValid.value` return early.

Complete new `<script setup>`:

```typescript
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";
import { AxiosError } from "axios";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const showPassword = ref(false);
const emailTouched = ref(false);
const passwordTouched = ref(false);

const error = ref("");
const loading = ref(false);

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const emailError = computed(() => {
  if (!emailTouched.value) return "";
  if (!email.value) return t("validation.emailRequired");
  if (!EMAIL_RE.test(email.value)) return t("validation.emailInvalid");
  return "";
});

const passwordError = computed(() => {
  if (!passwordTouched.value) return "";
  if (!password.value) return t("validation.passwordRequired");
  if (password.value.length < 8) return t("validation.passwordMinLength");
  return "";
});

const isFormValid = computed(
  () =>
    email.value.length > 0 &&
    !emailError.value &&
    password.value.length > 0 &&
    !passwordError.value,
);

async function handleLogin() {
  emailTouched.value = true;
  passwordTouched.value = true;
  if (!isFormValid.value) return;

  loading.value = true;
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch (e) {
    if (e instanceof AxiosError && e.response) {
      const status = e.response.status;
      if (status === 401) {
        error.value = t("login.invalidCredentials");
      } else if (status === 429) {
        error.value = t("common.rateLimitError");
      } else {
        error.value = t("login.genericError");
      }
    } else {
      error.value = t("common.networkError");
    }
  } finally {
    loading.value = false;
  }
}
```

Complete new `<template>`:

```html
<template>
  <div class="auth-page">
    <div class="auth-card animate-slide-up">
      <div class="auth-brand">
        <span class="brand-icon">&#10022;</span>
        <h1>JARVIS</h1>
        <p class="brand-tagline">{{ $t("login.title") }}</p>
      </div>
      <div class="shimmer-line animate-shimmer"></div>
      <form class="auth-form" @submit.prevent="handleLogin">
        <div class="form-group animate-slide-up-delay-1">
          <label for="email">{{ $t("login.email") }}</label>
          <input
            id="email"
            v-model="email"
            type="email"
            :placeholder="$t('login.email')"
            :class="{ 'input-error': emailError }"
            @blur="emailTouched = true"
            @input="emailTouched && (emailTouched = true)"
          />
          <p class="field-error" :class="{ visible: emailError }">{{ emailError }}</p>
        </div>
        <div class="form-group animate-slide-up-delay-2">
          <label for="password">{{ $t("login.password") }}</label>
          <div class="password-wrapper">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :placeholder="$t('login.password')"
              :class="{ 'input-error': passwordError }"
              @blur="passwordTouched = true"
              @input="passwordTouched && (passwordTouched = true)"
            />
            <button type="button" class="password-toggle" @click="showPassword = !showPassword">
              <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            </button>
          </div>
          <p class="field-error" :class="{ visible: passwordError }">{{ passwordError }}</p>
        </div>
        <button type="submit" class="btn-primary animate-slide-up-delay-3" :disabled="loading || !isFormValid">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? $t("login.loading") : $t("login.submit") }}
        </button>
        <p v-if="error" class="error-msg">{{ error }}</p>
      </form>
      <p class="auth-footer">
        {{ $t("login.noAccount") }}
        <router-link to="/register">{{ $t("login.register") }}</router-link>
      </p>
    </div>
  </div>
</template>
```

**Step 2: Verify**

Run: `cd /Users/hyh/code/JARVIS/.worktrees/feature-frontend/frontend && bun run type-check && bun run lint`

Expected: both pass with exit code 0.

**Step 3: Commit**

```bash
git add frontend/src/pages/LoginPage.vue
git commit -m "feat(login): add password toggle and real-time field validation"
```

---

### Task 4: Update RegisterPage with password toggle and validation

**Files:**
- Modify: `frontend/src/pages/RegisterPage.vue`

**Step 1: Apply the same pattern as LoginPage**

The changes mirror Task 3, with these differences:
- Three fields: email, displayName (optional, no validation), password
- The `handleRegister()` function keeps the existing 409/422/429 error handling
- `isFormValid` only checks email and password (displayName is optional)

Complete new `<script setup>`:

```typescript
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useI18n } from "vue-i18n";
import { AxiosError } from "axios";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();

const email = ref("");
const displayName = ref("");
const password = ref("");
const showPassword = ref(false);
const emailTouched = ref(false);
const passwordTouched = ref(false);

const error = ref("");
const loading = ref(false);

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const emailError = computed(() => {
  if (!emailTouched.value) return "";
  if (!email.value) return t("validation.emailRequired");
  if (!EMAIL_RE.test(email.value)) return t("validation.emailInvalid");
  return "";
});

const passwordError = computed(() => {
  if (!passwordTouched.value) return "";
  if (!password.value) return t("validation.passwordRequired");
  if (password.value.length < 8) return t("validation.passwordMinLength");
  return "";
});

const isFormValid = computed(
  () =>
    email.value.length > 0 &&
    !emailError.value &&
    password.value.length > 0 &&
    !passwordError.value,
);

async function handleRegister() {
  emailTouched.value = true;
  passwordTouched.value = true;
  if (!isFormValid.value) return;

  loading.value = true;
  error.value = "";
  try {
    await auth.register(email.value, password.value, displayName.value || undefined);
    router.push("/");
  } catch (e) {
    if (e instanceof AxiosError && e.response) {
      const status = e.response.status;
      if (status === 409) {
        error.value = t("register.emailTaken");
      } else if (status === 422) {
        const detail = e.response.data?.detail;
        if (Array.isArray(detail)) {
          error.value = detail.map((d: { msg: string }) => d.msg).join("；");
        } else if (typeof detail === "string") {
          error.value = detail;
        } else {
          error.value = t("register.validationError");
        }
      } else if (status === 429) {
        error.value = t("common.rateLimitError");
      } else {
        error.value = t("register.genericError");
      }
    } else {
      error.value = t("common.networkError");
    }
  } finally {
    loading.value = false;
  }
}
```

Complete new `<template>`:

```html
<template>
  <div class="auth-page">
    <div class="auth-card animate-slide-up">
      <div class="auth-brand">
        <span class="brand-icon">&#10022;</span>
        <h1>JARVIS</h1>
        <p class="brand-tagline">{{ $t("register.title") }}</p>
      </div>
      <div class="shimmer-line animate-shimmer"></div>
      <form class="auth-form" @submit.prevent="handleRegister">
        <div class="form-group animate-slide-up-delay-1">
          <label for="email">{{ $t("register.email") }}</label>
          <input
            id="email"
            v-model="email"
            type="email"
            :placeholder="$t('register.email')"
            :class="{ 'input-error': emailError }"
            @blur="emailTouched = true"
            @input="emailTouched && (emailTouched = true)"
          />
          <p class="field-error" :class="{ visible: emailError }">{{ emailError }}</p>
        </div>
        <div class="form-group animate-slide-up-delay-1">
          <label for="displayName">{{ $t("register.displayName") }}</label>
          <input
            id="displayName"
            v-model="displayName"
            type="text"
            :placeholder="$t('register.displayName')"
          />
        </div>
        <div class="form-group animate-slide-up-delay-2">
          <label for="password">{{ $t("register.password") }}</label>
          <div class="password-wrapper">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :placeholder="$t('register.password')"
              :class="{ 'input-error': passwordError }"
              @blur="passwordTouched = true"
              @input="passwordTouched && (passwordTouched = true)"
            />
            <button type="button" class="password-toggle" @click="showPassword = !showPassword">
              <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            </button>
          </div>
          <p class="field-error" :class="{ visible: passwordError }">{{ passwordError }}</p>
        </div>
        <button type="submit" class="btn-primary animate-slide-up-delay-3" :disabled="loading || !isFormValid">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? $t("register.loading") : $t("register.submit") }}
        </button>
        <p v-if="error" class="error-msg">{{ error }}</p>
      </form>
      <p class="auth-footer">
        {{ $t("register.hasAccount") }}
        <router-link to="/login">{{ $t("register.login") }}</router-link>
      </p>
    </div>
  </div>
</template>
```

**Step 2: Verify**

Run: `cd /Users/hyh/code/JARVIS/.worktrees/feature-frontend/frontend && bun run type-check && bun run lint`

Expected: both pass with exit code 0.

**Step 3: Commit**

```bash
git add frontend/src/pages/RegisterPage.vue
git commit -m "feat(register): add password toggle and real-time field validation"
```

---

### Task 5: Final verification — full lint + type-check + build

**Step 1: Run full verification suite**

Run: `cd /Users/hyh/code/JARVIS/.worktrees/feature-frontend/frontend && bun run lint && bun run type-check && bun run build`

Expected: all three pass with exit code 0.

**Step 2: If lint/type-check errors, fix and amend the relevant commit**

**Step 3: Manual smoke test checklist (for developer)**

- [ ] `/login` — email field shows error on blur with empty value
- [ ] `/login` — email field shows "invalid" error with `foo` typed
- [ ] `/login` — password field shows error on blur with empty value
- [ ] `/login` — password field shows "min 8 chars" with `abc` typed
- [ ] `/login` — submit button disabled until both fields valid
- [ ] `/login` — eye icon toggles password visibility
- [ ] `/login` — backend 401 still shows global error banner
- [ ] `/register` — same validation behavior as login
- [ ] `/register` — display name field has no validation
- [ ] `/register` — backend 409 still shows "email taken" error
- [ ] Language switch — validation errors update to selected language
