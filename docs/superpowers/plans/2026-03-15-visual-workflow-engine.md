# Visual Workflow Engine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a node-based visual editor for designing AI workflows. This allows users to orchestrate complex Agent logic without writing code.

**Architecture:** 
1. Integrate `@vue-flow/core` and `@vue-flow/background`, `@vue-flow/controls`.
2. Define custom node components: `LLMNode`, `ToolNode`, `ConditionNode`, `StartNode`, `EndNode`.
3. Create a `WorkflowStudio.vue` page.
4. Implement a state manager to handle graph serialization to JSON DSL.

**Tech Stack:** Vue 3, Vue Flow, Tailwind CSS.

---

## Chunk 1: Integration & Basic Canvas

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/pages/WorkflowStudioPage.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Install Vue Flow**
  Run: `cd frontend && bun add @vue-flow/core @vue-flow/background @vue-flow/controls @vue-flow/node-resizer`

- [ ] **Step 2: Add Workflow Studio Route**
  In `frontend/src/router/index.ts`, add `/studio`.

- [ ] **Step 3: Setup Basic Canvas**
  In `WorkflowStudioPage.vue`, initialize a basic Vue Flow canvas with background and controls.

- [ ] **Step 4: Commit**
  Run: `git add frontend/ && git commit -m "feat(frontend): integrate vue-flow and setup basic studio canvas"`

---

## Chunk 2: Custom Nodes & Toolbar

**Files:**
- Create: `frontend/src/components/workflow/LLMNode.vue`
- Create: `frontend/src/components/workflow/ToolNode.vue`
- Create: `frontend/src/components/workflow/NodeToolbar.vue`
- Modify: `frontend/src/pages/WorkflowStudioPage.vue`

- [ ] **Step 1: Implement custom node UI**
  Design `LLMNode` (with model selection, prompt input) and `ToolNode` (with tool selection).

- [ ] **Step 2: Implement Node Toolbar**
  Add a sidebar or floating menu to drag new nodes onto the canvas.

- [ ] **Step 3: Implement Configuration Sidebar**
  When a node is selected, show a property panel to edit its parameters (e.g. system prompt, tool arguments).

- [ ] **Step 4: Commit**
  Run: `git add frontend/ && git commit -m "feat(frontend): implement custom workflow nodes and property panel"`

---

## Chunk 3: Serialization & Validation

**Files:**
- Modify: `frontend/src/pages/WorkflowStudioPage.vue`

- [ ] **Step 1: Implement JSON Export**
  Add a "Save" button that validates the graph (e.g. must have a Start node) and converts it to the JARVIS JSON DSL.

- [ ] **Step 2: Mock Workflow API**
  (Note: Backend Track 3.2 will handle the actual compilation).
  For now, just log the JSON to console or save to a temporary state.

- [ ] **Step 3: Final Checks & Push**
  Run: `cd frontend && bun run type-check && bun run lint:fix`
  Run: `git add frontend/ && git commit -m "feat(frontend): implement workflow serialization and validation"`
  Run: `git push origin HEAD`
