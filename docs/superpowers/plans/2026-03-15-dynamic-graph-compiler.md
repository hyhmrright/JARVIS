# Dynamic Graph Compiler Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a backend engine that dynamically compiles visual workflow JSON into executable LangGraph StateGraphs. This enables custom Agent logic defined in the Studio.

**Architecture:** 
1. `GraphCompiler` class in `backend/app/agent/compiler.py` parses the JSON DSL (nodes and edges).
2. It maps Studio node types (`llm`, `tool`, `condition`) to LangGraph nodes and conditional edges.
3. Use a generic `GraphState` to hold inputs, outputs, and intermediate results.
4. The Chat API is updated to optionally route to a `WorkflowAgent` instead of the hardcoded expert graphs.

**Tech Stack:** Python, LangGraph, FastAPI.

---

## Chunk 1: DSL Parser & Node Implementation

**Files:**
- Create: `backend/app/agent/compiler.py`
- Modify: `backend/app/agent/graph.py`

- [ ] **Step 1: Define Workflow DSL Schema**
  In `compiler.py`, use Pydantic to define the expected JSON structure from the frontend.

- [ ] **Step 2: Implement Base Node Logic**
  Create functions for `llm_node_handler` and `tool_node_handler` that can be wrapped by LangGraph.

- [ ] **Step 3: Implement GraphCompiler**
  Add logic to iterate over nodes and edges, calling `.add_node()` and `.add_edge()` on a `StateGraph`.

- [ ] **Step 4: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): implement dynamic graph compiler for workflow orchestration"`

---

## Chunk 2: Integration with Chat API

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/XXX_add_workflow_to_conversation.py`

- [ ] **Step 1: Add workflow_id to Conversation**
  Allow linking a conversation to a specific workflow definition (or store the DSL blob).

- [ ] **Step 2: Update chat_stream to use Compiler**
  If a conversation has a workflow, use `GraphCompiler` to build the graph and run it instead of the default ReAct loop.

- [ ] **Step 3: Commit**
  Run: `git add backend/ && git commit -m "feat(backend): integrate workflow compiler with chat streaming API"`

---

## Chunk 3: Workflow CRUD & Validation

**Files:**
- Create: `backend/app/api/workflows.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement Workflow CRUD API**
  Endpoints to save and retrieve workflow DSLs.

- [ ] **Step 2: Register Workflow Router**
  In `backend/app/main.py`.

- [ ] **Step 3: Run Backend Tests**
  Run: `cd backend && uv run pytest tests/`
  *Note: Critical to test basic cycles and branching in the compiled graph.*

- [ ] **Step 4: Final Checks & Push**
  Run: `cd backend && uv run ruff check . --fix && uv run mypy app`
  Run: `git add backend/ && git commit -m "feat(backend): implement workflow management API and validation"`
  Run: `git push origin HEAD`
