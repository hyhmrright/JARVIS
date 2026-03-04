# Phase 5: RAG × Agent Integration — Design

## Goal

Wire the existing RAG pipeline into the agent conversation flow so that:
1. Every user message automatically retrieves relevant chunks from the user's knowledge base and injects them as context before the agent runs.
2. The agent can proactively call a `search_knowledge_base` tool for follow-up queries.
3. Retrieved document names are surfaced as citations in the agent's reply.
4. The feature works across both the web chat interface (SSE) and the multi-channel gateway (Telegram/Discord).

## Background

The RAG pipeline (upload → chunk → embed → Qdrant upsert) was implemented in Phase 1 and stores vectors in per-user collections (`user_{id}`). However, retrieval was never wired into the agent conversation flow — the agent has no awareness of uploaded documents.

## Architecture

```
User message
    │
    ▼
retrieve_context(query, user_id)          ← new: app/rag/retriever.py
    │  (Qdrant similarity search, score > 0.7)
    │
    ▼ if chunks found
prepend SystemMessage([Knowledge Base Context] …)
    │
    ▼
create_graph(…, user_id=user_id)
    ├── tool: search_knowledge_base(query)  ← new: app/tools/rag_tool.py
    └── existing tools
    │
    ▼
Agent inference → response with natural citations
```

## Components

### New files

| File | Responsibility |
|------|---------------|
| `backend/app/rag/retriever.py` | `retrieve_context(query, user_id, top_k, score_threshold)` — embeds query, searches Qdrant, returns `list[RetrievedChunk]` |
| `backend/app/tools/rag_tool.py` | `create_rag_tool(user_id, openai_api_key)` factory — returns `search_knowledge_base` LangChain tool |

### Modified files

| File | Change |
|------|--------|
| `backend/app/agent/graph.py` | `_resolve_tools()` accepts `user_id` + `openai_api_key`; adds `rag_search` tool when enabled. `create_graph()` adds `user_id` param. |
| `backend/app/api/chat.py` | Before `create_graph()` call in `generate()`: call `retrieve_context()`, prepend context `SystemMessage` if results found. |
| `backend/app/gateway/router.py` | In `_invoke_agent()`: same auto-retrieval before graph invocation. |
| `backend/app/core/permissions.py` | Add `rag_search` to `TOOL_REGISTRY` (default enabled). |
| `backend/tests/rag/test_retriever.py` | Unit tests for retriever. |
| `backend/tests/tools/test_rag_tool.py` | Unit tests for RAG tool. |

## Data Model

```python
@dataclass
class RetrievedChunk:
    document_name: str   # original filename from documents table
    content: str         # chunk text
    score: float         # cosine similarity score
```

## Context Injection Format

A `SystemMessage` prepended to the message list:

```
[Knowledge Base Context]
Document: "project_whitepaper.pdf" (relevance: 0.92)
<chunk text>

Document: "FAQ.md" (relevance: 0.81)
<chunk text>

Use the above context to answer the user's question. Cite document names when referencing this content.
```

## RAG Tool Return Format

```
Found 2 relevant chunks:

[1] Document: "project_whitepaper.pdf" (relevance: 0.87)
<content>

[2] Document: "FAQ.md" (relevance: 0.74)
<content>
```

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| User has no Qdrant collection (no documents uploaded) | `retrieve_context()` catches the error, returns `[]` — agent runs normally |
| Qdrant unreachable | Same silent fallback — log warning, return `[]` |
| OpenAI embedding fails | Same silent fallback — log warning, return `[]` |
| No chunks above threshold | Inject nothing; agent may still call the tool |

## Retrieval Parameters (defaults, configurable later)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `top_k` | 5 | Balance between context richness and token cost |
| `score_threshold` | 0.7 | Filters irrelevant noise; cosine similarity on normalized embeddings |

## Testing Strategy

- **`test_retriever.py`**: mock Qdrant client + embeddings; verify threshold filtering, empty-collection handling, error fallback.
- **`test_rag_tool.py`**: mock `retrieve_context`; verify formatted output, empty-result case.
- **`test_chat.py`**: mock retriever in `generate()` flow; verify context injection when results present and absence when empty.
- **`test_gateway_agent.py`**: extend existing gateway agent tests to verify retrieval is called.

## Scope

- **In scope**: web chat SSE flow, gateway router, both retrieval modes (auto + tool).
- **Out of scope**: frontend citation UI (citations are embedded in the AI text response), cross-user knowledge base search, embedding model selection per user.
