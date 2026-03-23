# RAG Knowledge Base

Upload documents so JARVIS can cite them when answering questions.

**Prerequisites:**
- JARVIS running, logged in, and an OpenAI API key configured in Settings (required for embeddings via `text-embedding-3-small`)

---

## Upload a Document

1. Click **Documents** in the left sidebar.
2. Click **Upload Document**.
3. Select a file — supported formats: **PDF, TXT, MD, DOCX**.
4. Wait for processing. JARVIS chunks the document (500 words / 50-word overlap) and indexes it in Qdrant using `text-embedding-3-small` (1536 dimensions).

---

## Ingest from a URL

1. In the **Documents** panel, click **Add from URL**.
2. Paste a public URL (HTML page, PDF link, etc.).
3. JARVIS fetches, extracts, chunks, and indexes the content automatically.

---

## Ask a Question

After uploading, start a new conversation and ask a question related to your documents:

> "Summarize the key findings in my Q4 report."

JARVIS performs a hybrid vector + keyword search, retrieves the top-5 matching chunks, and injects them as context before the LLM call. Sources are cited inline: `[1] "document-name"`.

---

## Workspace Collections

Within a Workspace, all members share a common knowledge base:

1. Go to **Workspace Settings** → **Documents**.
2. Upload documents — they are stored in a shared `workspace_{id}` Qdrant collection.
3. All members' conversations in that workspace automatically search both their personal collection and the workspace collection.

Personal and workspace results are merged and re-ranked by combined score (70% vector, 30% keyword overlap) before being passed to the LLM.

---

## Remove a Document

1. Go to **Documents**.
2. Click the trash icon next to the document.
3. The document and all its indexed chunks are deleted.
