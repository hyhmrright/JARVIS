# Getting Started with JARVIS

This guide walks you from a fresh checkout to your first AI conversation in under ten minutes.

**Prerequisites:**
- Docker Desktop (or Docker Engine + Compose v2)
- An OpenAI, DeepSeek, or Anthropic API key
- Git

---

## 1. Clone and Configure

```bash
git clone https://github.com/your-org/JARVIS.git
cd JARVIS
bash scripts/init-env.sh
```

`init-env.sh` generates a `.env` file with random passwords and encryption keys. Open `.env` and fill in at least one API key:

```bash
# .env — fill in one of these
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 2. Start the Stack

```bash
docker compose up -d
```

Wait until all containers are healthy:

```bash
docker compose ps
# Every row should show "healthy" or "running"
```

Open **http://localhost** in your browser.

---

## 3. Register and Log In

1. Click **Register** on the login page.
2. Enter an email and password (minimum 8 characters).
3. You are automatically logged in after registration.

---

## 4. Configure Your LLM Provider

1. Click your avatar (top-right) → **Settings**.
2. Under **AI Model Config**, select your provider (DeepSeek / OpenAI / Anthropic / ZhipuAI / Ollama).
3. Choose or enter a model name.
4. In the **API Keys** section, paste your API key and click **Save**.

JARVIS encrypts all API keys at rest using Fernet symmetric encryption.

---

## 5. Send Your First Message

1. Click **New Conversation** in the sidebar.
2. Type a message and press **Enter**.
3. The assistant streams its reply token by token.

**Try a tool call:** Ask "What time is it?" — JARVIS invokes the `datetime` tool and returns the current time.

---

## Next Steps

- [Plugins & Skills](./plugins-and-skills.md) — extend your assistant with new capabilities
- [RAG Knowledge Base](./rag-knowledge-base.md) — upload documents for context-aware answers
- [Workflow Studio](./workflows.md) — automate multi-step tasks
