# Phase 15: Experience Upgrade & Knowledge Base Management Design

## Objective
Elevate the JARVIS platform experience by introducing a dedicated Knowledge Base management interface, expanding workflow capabilities with AI image generation, and refining the frontend UX with drag-and-drop interactions and code quality improvements.

## 1. RAG Knowledge Base Management Center
Currently, document uploads are supported via the Chat interface, but users lack a centralized view to manage their uploaded RAG context.

- **Frontend Route**: `/knowledge`
- **UI Component**: `frontend/src/pages/KnowledgePage.vue`
- **Features**:
  - Data Table displaying `filename`, `file_size_bytes`, `status` (indexed/failed), and `created_at`.
  - Action column with a "Delete" button.
  - Utilize existing backend endpoints: `GET /api/documents` and `DELETE /api/documents/{doc_id}`.
  - State management via a new Pinia store or localized fetch logic.

## 2. Image Generation Workflow Node
Expand the visual orchestration capabilities in Workflow Studio.

- **Backend Tool**: `backend/app/tools/image_gen_tool.py`
  - Utilizes `openai.AsyncOpenAI(api_key=...)`.
  - Model: `dall-e-3`.
  - Output: Returns the generated image URL.
- **Workflow Executor**: Update `backend/app/workflows/executor.py` to natively support the `image_gen` node type.
- **Frontend Studio**:
  - Add `ImageGenNode.vue`.
  - Update `WorkflowStudioPage.vue` palette to include the "Image Generation" block.

## 3. Sidebar UX: Drag and Drop
Enhance the folder management experience built in Phase 14.

- **Implementation**: HTML5 Drag and Drop API in `ChatPage.vue`.
- **Interactions**:
  - Conversations (`draggable="true"`).
  - Folders (`@dragover.prevent`, `@drop="handleDrop"`).
  - Visual feedback when dragging over a folder (e.g., highlight border).

## 4. Code Quality & Security Polish
Address remaining ESLint warnings from Phase 14.
- **v-html XSS Risk**: Ensure `v-html` directives in `LiveCanvas.vue` and `SharedChatPage.vue` use `sanitizeHtml`.
- **TypeScript `any`**: Refine types in `notification.ts` and `plugins.ts`.
