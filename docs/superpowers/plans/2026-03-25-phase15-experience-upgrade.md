# Implementation Plan: Phase 15 - Experience Upgrade

## Objective
Implement a Knowledge Base management UI, Image Generation workflow node, Drag-and-Drop folder organization, and resolve codebase linting warnings.

## Feature 1: RAG Knowledge Base Management
### Task 1 & 2: Frontend Routing & Component
- [x] Verified that `/documents` route and `DocumentsPage.vue` already serve this exact purpose with comprehensive features (workspace scoping, upload, delete, chunk stats). No further action needed here.

## Feature 2: Image Generation Node
### Task 3: Backend Tool & Executor
- [ ] Create `backend/app/tools/image_gen_tool.py` wrapping `openai.images.generate`.
- [ ] Register the tool in `backend/app/agent/graph.py` `_TOOL_MAP`.
- [ ] (Optional) Ensure `executor.py` can parse and route `image_gen` tool calls natively if needed, or rely on standard tool dispatch.

### Task 4: Frontend Studio Integration
- [ ] Create `frontend/src/components/workflow/ImageGenNode.vue` with prompt input.
- [ ] Register the node in `WorkflowStudioPage.vue`.
- [ ] Update locale files (`zh.json`, `en.json`) with node descriptions.

## Feature 3: Drag and Drop UX
### Task 5: ChatPage Sidebar
- [ ] Add `draggable="true"` and `@dragstart` to unassigned and folder conversation items.
- [ ] Add `@dragover.prevent`, `@dragenter`, `@dragleave`, and `@drop` to folder headers.
- [ ] Wire the drop event to the existing `chat.moveConversationToFolder` action.

## Feature 4: Code Quality & Security Polish
### Task 6: ESLint Fixes
- [ ] Replace `v-html` with sanitized HTML rendering in `LiveCanvas.vue` and `SharedChatPage.vue`.
- [ ] Remove unused `any` types in `notification.ts` and API clients.

### Task 7: Quality Loop & Push
- [ ] Run backend tests and ruff.
- [ ] Run frontend lint and type-check.
- [ ] Git commit and push.
