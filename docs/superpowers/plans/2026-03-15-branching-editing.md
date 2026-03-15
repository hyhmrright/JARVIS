# Branching & Editing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to edit previous messages and create new conversation branches. Implement a branch switcher to navigate between different versions of the conversation.

**Architecture:** 
1. Frontend `ChatPage.vue` adds an "Edit" state for human messages. 
2. Submitting an edit calls `sendMessage` with the `parent_id` of the edited message, creating a fork in the message tree. 
3. A "Branch Switcher" component (e.g., `< 2/2 >`) allows users to toggle `activeLeafId` in the Pinia store to view different paths.

**Tech Stack:** Vue 3, Pinia, Lucide Icons.

---

## Chunk 1: Frontend Store Enhancements

**Files:**
- Modify: `frontend/src/stores/chat.ts`

- [ ] **Step 1: Add switchBranch Action (if not fully implemented)**
  Ensure `switchBranch(messageId: string)` sets `this.activeLeafId = messageId`. (Checked: already exists).

- [ ] **Step 2: Enhance sendMessage to support parentId override**
  Currently `sendMessage` takes `content` and `imageUrls`. Add `parentId?: string`:
  ```typescript
  async sendMessage(content: string, imageUrls?: string[], parentId?: string) {
    // ...
    // If parentId is provided, use it instead of finding the latest message
    const actualParentId = parentId || (this.activeMessages.length > 0 ? this.activeMessages[this.activeMessages.length - 1].id : undefined);
    // ...
  ```
  Update the POST payload to use `parent_message_id: actualParentId`.

- [ ] **Step 3: Update getSiblings Getter**
  Ensure `getSiblings` correctly returns messages with the same `parent_id`. (Checked: already exists).

- [ ] **Step 4: Commit**
  Run: `git add frontend/src/stores/chat.ts`
  Run: `git commit -m "feat(frontend): update chat store to support explicit parentId in sendMessage"`

---

## Chunk 2: Message Editing UI

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Add Editing State**
  Add `const editingMessageId = ref<string | null>(null);` and `const editInput = ref("");`.

- [ ] **Step 2: Add Edit Button to Human Messages**
  In the message loop, for human messages, add an "Edit" icon (Pen) that sets `editingMessageId.value = msg.id` and `editInput.value = msg.content`.

- [ ] **Step 3: Render Edit Textarea**
  If `editingMessageId === msg.id`, show a textarea and "Save & Submit" / "Cancel" buttons instead of the message content.

- [ ] **Step 4: Implement handleEditSubmit**
  ```typescript
  const handleEditSubmit = async (msg: Message) => {
    const content = editInput.value;
    editingMessageId.value = null;
    await chat.sendMessage(content, undefined, msg.parent_id);
  };
  ```

- [ ] **Step 5: Commit**
  Run: `git add frontend/src/pages/ChatPage.vue`
  Run: `git commit -m "feat(frontend): implement human message editing and forking"`

---

## Chunk 3: Branch Switcher Component

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Add Branch Navigation UI**
  For each message in `activeMessages`, if it has siblings (`chat.getSiblings(msg).length > 1`), show a switcher: `< 1 / 2 >`.

- [ ] **Step 2: Implement switchBranch Navigation**
  Clicking arrows should find the next/previous sibling ID and call `chat.switchBranch(siblingId)`.

- [ ] **Step 3: Run Frontend Checks**
  Run: `cd frontend && bun run type-check && bun run lint:fix`
  Expected: PASS

- [ ] **Step 4: Commit & Push**
  Run: `git add frontend/src/pages/ChatPage.vue`
  Run: `git commit -m "feat(frontend): add branch switcher for navigating message forks"`
  Run: `git push origin HEAD`
