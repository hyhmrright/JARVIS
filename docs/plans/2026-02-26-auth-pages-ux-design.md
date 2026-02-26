# Auth Pages UX Enhancement Design

**Date**: 2026-02-26
**Branch**: feature/frontend
**Scope**: Frontend only (no backend changes)

## Goal

Improve the Login and Register pages with password visibility toggle, real-time field-level validation, and better error presentation, while keeping the existing dark luxury visual style.

## Context

### Current State

- Login: email + password, HTML5 `required` only, global error banner
- Register: email + optional display name + password, same minimal validation
- Backend: bcrypt + JWT, rate limiting via slowapi (login 5/min, register 3/min)
- Style: dark navy (#0a0a12) background, gold (#d4a574) accent, glassmorphism cards

### What We Decided NOT to Do

- CAPTCHA — overkill for self-hosted, IP rate limiting is sufficient
- Email verification — not needed until forgot-password flow is added
- Social login (OAuth) — unnecessary external dependency
- Password strength indicator (zxcvbn) — deferred for simplicity
- Confirm password field — replaced by show/hide toggle per NIST guidance
- No new dependencies (no VeeValidate, no icon library)

## Design

### 1. Password Show/Hide Toggle

- Eye icon button inside the password input (right-aligned)
- Toggles `type="password"` ↔ `type="text"`
- Icon: inline SVG (eye-open / eye-off), color `#5a5a6a`, hover brightens
- `type="button"` to prevent form submission
- Applied to: LoginPage password, RegisterPage password

### 2. Real-Time Field Validation

**Rules:**

| Page | Field | Rule | Error Key |
|------|-------|------|-----------|
| Both | email | Non-empty + email regex | `validation.emailRequired` / `validation.emailInvalid` |
| Both | password | Non-empty + ≥8 chars | `validation.passwordRequired` / `validation.passwordMinLength` |
| Register | displayName | Optional, no validation | — |

**Trigger Timing:**

- **First trigger on blur**: validation starts after the field loses focus (avoids premature errors)
- **Then real-time on input**: once a field is "touched", every keystroke re-validates
- **Full validation on submit**: all required fields validated before API call

**Error Display:**

- Per-field red text below input (14px, `#e85d5d`), slide-in transition
- Input border turns red on error (`rgba(232,93,93,0.3)`)
- Global error banner retained for backend errors only (401/409/429/network)

**Submit Button:**

- Disabled (greyed out) until all required fields pass validation
- Re-enabled once validation passes

### 3. i18n

New validation keys added to all 6 locale files (zh/en/ja/ko/fr/de):

```json
{
  "validation": {
    "emailRequired": "...",
    "emailInvalid": "...",
    "passwordRequired": "...",
    "passwordMinLength": "..."
  }
}
```

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/pages/LoginPage.vue` | Password toggle, validation logic, field-level errors, button disabled binding |
| `frontend/src/pages/RegisterPage.vue` | Same as above |
| `frontend/src/assets/global.css` | `.field-error` text style, `.input-error` border style |
| `frontend/src/locales/zh.json` | Add `validation.*` keys |
| `frontend/src/locales/en.json` | Add `validation.*` keys |
| `frontend/src/locales/ja.json` | Add `validation.*` keys |
| `frontend/src/locales/ko.json` | Add `validation.*` keys |
| `frontend/src/locales/fr.json` | Add `validation.*` keys |
| `frontend/src/locales/de.json` | Add `validation.*` keys |

## Out of Scope

- Backend changes (no per-account lockout in this iteration)
- Forgot password flow (requires SMTP)
- Password strength meter
- New npm dependencies
