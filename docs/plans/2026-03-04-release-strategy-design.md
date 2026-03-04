# JARVIS Release Strategy & GitHub Growth Design

**Date:** 2026-03-04
**Scope:** Tag strategy, release notes format, GitHub About, Labels, growth tactics

---

## Goals

Make JARVIS a popular GitHub project by targeting all audiences:
- Individual developers / hackers (self-host, privacy, zero cost)
- Enterprise / team deployment (RBAC, multi-channel, production infra)
- AI/LLM learners (reference implementation of FastAPI + LangGraph + Vue 3)

**Core differentiators (priority order):**
1. Extreme simplicity — one `docker compose up` gets everything
2. Full-stack reference implementation
3. Developer extensibility via Plugin SDK

---

## GitHub About

### Description
> Self-hosted AI assistant — one `docker compose up` gets you RAG, multi-LLM, plugin SDK, multi-channel (Slack/Discord/Telegram/Feishu), RBAC, and full observability. FastAPI + LangGraph + Vue 3.

### Topics
`ai`, `fastapi`, `langgraph`, `llm`, `python`, `rag`, `vue3`,
`self-hosted`, `docker`, `openai`, `anthropic`, `deepseek`, `plugin-system`

**Removed:** `chatbot` (too generic), `langchain` (not primary), `typescript` (not a search term)

---

## Version Naming Convention

```
v<MAJOR>.<MINOR>.<PATCH> — <Theme Phrase>
```

### Roadmap

| Version | Theme | Milestone |
|---------|-------|-----------|
| v0.4.0 | Plugin SDK & Multi-Channel Platform | Current — platform |
| v0.5.0 | Security & Production Hardening | RBAC complete, Audit Log, API Keys |
| v0.6.0 | Frontend UX & WebSocket | Branching, file upload, mobile |
| v1.0.0 | Stable Release | E2E tested, Docker images on GHCR |

> v1.0 = "feature complete + production verified" — reserve for maximum impact.

---

## Release Note Format (Two-Layer)

```markdown
## JARVIS vX.Y.Z — <Theme>

> One-line summary.

---

## ✨ Highlights

### 🧩 Feature Name
User-facing description of what's now possible.

---

## 🛠️ Under the Hood

| Area | Change |
|------|--------|
| ... | ... |

---

## 📦 Upgrade from vX.Y.Z-1

```bash
git pull && docker compose down && docker compose build --no-cache && docker compose up -d
```

Database migrations run automatically on startup.
```

---

## Labels

### New Labels

| Label | Color | Purpose |
|-------|-------|---------|
| `plugin` | `#7c3aed` | Plugin SDK issues/PRs |
| `channels` | `#0891b2` | Multi-channel gateway |
| `security` | `#dc2626` | Security fixes |
| `performance` | `#d97706` | Performance improvements |
| `hacktoberfest` | `#ff6600` | October contribution event |

### Remove
- `invalid` — redundant with `wontfix`

---

## Growth Tactics

### Immediate (with v0.4.0 release)
1. Add Hero GIF to README top
2. Add screenshot gallery (Chat, Admin, Grafana, Plugins)
3. Add comparison table vs Open WebUI / Dify
4. Add more badges (stars, last-commit, CI, docker pulls)
5. Submit to awesome-selfhosted, awesome-langchain, awesome-llm-apps
6. Post "Show HN" on Hacker News (Monday–Wednesday, US morning)
7. Post on Reddit r/selfhosted and r/LocalLLaMA
8. Enable GitHub Discussions
9. Create public GitHub Project board as roadmap

### Medium-term (v0.5.0)
1. Publish Docker images to GHCR (allow `curl + compose` deploy)
2. Write dev.to / Medium article on architecture
3. Create 3–5 `good first issue` with file paths and clear instructions
4. Add CHANGELOG.md

### Long-term (v1.0.0)
1. Product Hunt launch
2. Documentation site (MkDocs or VitePress)
