# JARVIS Roadmap

This document outlines planned features and improvements. Items are roughly ordered by priority. Community feedback and contributions are welcome — open an issue to discuss or upvote existing ones.

## Near-term (next 1-2 releases)

- [ ] **Mobile-responsive UI** — Optimize chat and document pages for phone/tablet
- [ ] **Plugin marketplace API** — Public registry endpoint so community skills can be published and discovered
- [ ] **Knowledge base improvements** — Hybrid search (BM25 + vector), re-ranking, chunk-level citations in responses
- [ ] **Agent memory** — Persistent long-term memory extracted from conversations and injected into future sessions
- [ ] **One-click persona sharing** — Export/import persona definitions as JSON; shareable links

## Medium-term

- [ ] **OAuth / SSO** — Google, GitHub, and OIDC login for team deployments
- [ ] **Conversation export** — PDF, Markdown, and JSON export of full conversation history
- [ ] **Fine-tuning pipeline** — Collect RLHF feedback in-app; export to fine-tuning datasets
- [ ] **More channel adapters** — WeChat Work, DingTalk, Line
- [ ] **Scheduled reports** — Cron-triggered agent runs that email or post results to a channel
- [ ] **Multi-modal input** — Image understanding via vision-capable models (GPT-4o, Claude 3)

## Long-term / Exploratory

- [ ] **Self-hosted model support** — Ollama integration for fully local LLM inference
- [ ] **Team knowledge graphs** — Entity extraction from uploaded documents into a queryable graph
- [ ] **A/B testing for prompts** — Run two persona/system-prompt variants against the same input and compare
- [ ] **Billing / usage quotas** — Per-workspace token budgets with alerts

---

Have an idea? Open a [GitHub Issue](https://github.com/hyhmrright/JARVIS/issues) or start a [Discussion](https://github.com/hyhmrright/JARVIS/discussions).
