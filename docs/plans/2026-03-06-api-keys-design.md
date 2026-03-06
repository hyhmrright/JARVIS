# Phase 12.4 — Personal API Keys (PAT) Design

## Goal

Allow users to create long-lived Personal Access Tokens (PATs) that can authenticate to the JARVIS API without session-based JWTs — enabling programmatic access from scripts, third-party tools, and CI pipelines.

## Architecture

### Authentication Flow

The existing `Bearer <jwt>` auth path in `deps.py` is extended to detect PAT tokens by their `jv_` prefix. When a `jv_` token is detected, the system looks up the sha256 hash in the `api_keys` table instead of decoding a JWT. The resolved `User` object flows through the same dependency chain — all downstream handlers remain unchanged.

```
Request: Authorization: Bearer jv_<token>
                                    ↓
                         starts with "jv_"?
                        ↙ yes          ↘ no
             sha256(token)           jwt.decode(token)
             lookup in api_keys      get user_id from sub
                   ↓                        ↓
             update last_used_at       query users table
                   ↓                        ↓
                 User object           User object (unchanged)
                   ↓                        ↓
             existing dependencies   existing dependencies
```

### Data Model

New `api_keys` table:

```sql
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,            -- human label, e.g. "My script"
    key_hash    VARCHAR(64) NOT NULL UNIQUE,       -- sha256 hex of the raw token
    prefix      VARCHAR(8) NOT NULL,              -- first 8 chars, for display only
    scope       VARCHAR(20) NOT NULL DEFAULT 'full',  -- 'full' | 'readonly'
    expires_at  TIMESTAMPTZ,                      -- NULL = never expires
    last_used_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Key format: `jv_` + 32 random bytes hex-encoded = `jv_` + 64 chars = 67 chars total.
The raw key is displayed **once** at creation; only the sha256 hash is stored.

### Scopes

| Scope | Access |
|-------|--------|
| `full` | Same as a logged-in user — all read/write endpoints |
| `readonly` | GET endpoints only; POST/PUT/DELETE return 403 |

Scope checking is enforced in `_resolve_user` after the key lookup. The resolved user carries scope information via a lightweight wrapper (not mutating the User model).

### API Endpoints

New router: `POST/GET/DELETE /api/keys` (registered under existing APIRouter pattern).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/keys` | Create key — returns raw token (only time it's shown) |
| GET | `/api/keys` | List keys for current user (no raw tokens, prefix only) |
| DELETE | `/api/keys/{id}` | Revoke a key |

Constraints:
- Max 10 active keys per user (enforced at create time)
- Keys expire if `expires_at` is set and passed (401 returned)
- Rate limiting applies the same as JWT-authenticated requests

### Frontend

New "API 密钥" tab in the Settings page (alongside existing tabs). The tab shows:
- Key list: name, prefix (`jv_xxxxxxxx...`), scope, created date, last used
- "创建密钥" button → modal form (name, scope, optional expiry)
- After creation: one-time reveal modal with copy button
- Revoke button per key (with confirmation)

### Security Properties

- Raw token never stored — only sha256 hash. DB compromise doesn't expose tokens.
- `key_hash` column has a UNIQUE constraint — prevents hash collisions being exploitable.
- `last_used_at` updated on each auth — visible to user for anomaly detection.
- Scope enforcement prevents read-only keys from mutating state.
- Cascade delete: all keys deleted when user is deleted.

## Files to Create/Modify

| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add `ApiKey` model |
| `backend/alembic/versions/011_add_api_keys.py` | Migration |
| `backend/app/api/keys.py` | New CRUD router |
| `backend/app/api/deps.py` | Extend `_resolve_user` for PAT auth |
| `backend/app/main.py` | Register keys router |
| `backend/tests/api/test_keys.py` | API tests |
| `frontend/src/pages/Settings.vue` | Add API Keys tab |
| `frontend/src/api/index.ts` | Add key management API calls |
| `frontend/src/locales/*.json` | i18n strings |

## Decision Log

- **sha256 over bcrypt**: PATs are 32-byte random — entropy is already cryptographically sufficient. bcrypt adds latency with zero security benefit here (bcrypt's benefit is slowing brute-force on low-entropy passwords).
- **Scopes `full`/`readonly` only**: YAGNI — per-resource scope granularity can be added later if needed.
- **Prefix stored separately**: Allows display of `jv_xxxxxxxx...` to users without any hash-reverse risk.
- **Max 10 keys**: Prevents unbounded growth; covers all practical use cases.
- **`Bearer` detection by prefix**: No new auth scheme header needed; backwards-compatible.
