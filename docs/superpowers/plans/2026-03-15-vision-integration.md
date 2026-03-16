# Vision Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to upload and send images in the chat interface, and pass them to Vision-capable LLMs (like GPT-4o, Claude-3.5-Sonnet) using LangChain's multimodal message format.

**Architecture:** 
1. Database `Message` table adds a JSONB `image_urls` column to store Base64 strings or URLs. 
2. The Chat API transforms HumanMessages with `image_urls` into the `[{"type": "text"...}, {"type": "image_url"...}]` format expected by LangChain. 
3. The Vue frontend adds a file uploader, base64 encoder, preview row, and renders sent images.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Vue 3, Pinia.

---

## Chunk 1: Backend Database & Models

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/api/conversations.py`
- Create: `backend/alembic/versions/XXX_add_image_urls_to_messages.py`

- [ ] **Step 1: Update Database Model**
  Edit `backend/app/db/models.py`. In the `Message` class (around line 245), add:
  ```python
      image_urls: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
  ```

- [ ] **Step 2: Generate Alembic Migration**
  Run: `cd backend && uv run alembic revision --autogenerate -m "add_image_urls_to_messages"`
  Expected: A new file is created in `backend/alembic/versions/`.
  *Note: Make sure the local database is running and `alembic upgrade head` is applied before generating.*

- [ ] **Step 3: Update API Pydantic Models**
  Edit `backend/app/api/chat.py`. In `ChatRequest`, add `image_urls: list[str] | None = None`.
  Edit `backend/app/api/conversations.py`. In `MessageOut`, add `image_urls: list[str] | None = None`.

- [ ] **Step 4: Update Message Creation in Chat API**
  Edit `backend/app/api/chat.py` in `chat_stream`. When creating the `human_msg = Message(...)` (around line 251), add `image_urls=body.image_urls`.

- [ ] **Step 5: Apply Migration and Commit**
  Run: `cd backend && uv run alembic upgrade head`
  Run: `cd backend && uv run ruff check --fix && uv run mypy app`
  Run: `git add backend/app/db/models.py backend/app/api/chat.py backend/app/api/conversations.py backend/alembic/versions/`
  Run: `git commit -m "feat(backend): add image_urls to message schema and api models"`

---

## Chunk 2: Backend LangChain Multimodal Support

**Files:**
- Modify: `backend/app/api/chat.py`

- [ ] **Step 1: Refactor History to LangChain Message Conversion**
  In `backend/app/api/chat.py`, there is a loop `for msg in all_history:` inside `chat_stream` (around line 285) and `chat_regenerate` (around line 618).
  Replace the inner logic for `human` role:
  ```python
          if message_class:
              if msg.role == "human" and getattr(msg, "image_urls", None):
                  content_blocks: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
                  for url in msg.image_urls:
                      content_blocks.append({"type": "image_url", "image_url": {"url": url}})
                  lc_messages.append(message_class(content=content_blocks))
              else:
                  lc_messages.append(message_class(content=msg.content))
  ```
  *(Make sure to import `Any` from `typing` if not present).*

- [ ] **Step 2: Run Backend Tests**
  Run: `cd backend && uv run pytest tests/ -v`
  Expected: PASS

- [ ] **Step 3: Commit**
  Run: `git add backend/app/api/chat.py`
  Run: `git commit -m "feat(backend): convert image_urls to langchain multimodal format"`

---

## Chunk 3: Frontend Store & Type Updates

**Files:**
- Modify: `frontend/src/stores/chat.ts`

- [ ] **Step 1: Update Message Interface**
  Edit `frontend/src/stores/chat.ts`. Update the `Message` interface (around line 12):
  ```typescript
  interface Message {
    id?: string;
    parent_id?: string;
    role: "human" | "ai";
    content: string;
    image_urls?: string[];
    toolCalls?: ToolCall[];
    // ...
  ```

- [ ] **Step 2: Update sendMessage signature**
  In `frontend/src/stores/chat.ts`, update `sendMessage` to accept an optional array of images:
  ```typescript
      async sendMessage(content: string, imageUrls?: string[]) {
        // ...
  ```
  Then, when making the POST request to `/chat/stream`:
  ```typescript
          const { data } = await client.post(
            "/chat/stream",
            {
              conversation_id: this.currentConvId,
              content,
              image_urls: imageUrls,
              parent_message_id: parentId,
            },
  ```
  Also update the local optimistic message push to include `image_urls: imageUrls`.

- [ ] **Step 3: Run Frontend Checks**
  Run: `cd frontend && bun run type-check`
  Expected: PASS

- [ ] **Step 4: Commit**
  Run: `git add frontend/src/stores/chat.ts`
  Run: `git commit -m "feat(frontend): add image_urls to chat store state and API calls"`

---

## Chunk 4: Frontend UI for Image Upload & Rendering

**Files:**
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: Add Hidden File Input & Previews State**
  In `frontend/src/pages/ChatPage.vue` script section, add:
  ```typescript
  const fileInput = ref<HTMLInputElement>();
  const selectedImages = ref<string[]>([]);
  
  const handleImageSelect = (e: Event) => {
    const files = (e.target as HTMLInputElement).files;
    if (!files) return;
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (ev.target?.result) {
          selectedImages.value.push(ev.target.result as string);
        }
      };
      reader.readAsDataURL(file);
    });
    // Reset input
    if (fileInput.value) fileInput.value.value = '';
  };
  
  const removeImage = (idx: number) => {
    selectedImages.value.splice(idx, 1);
  };
  ```

- [ ] **Step 2: Add Attachment Button in UI**
  In `frontend/src/pages/ChatPage.vue` template, inside the `div` containing the `<textarea>` (around line 160):
  Add a paperclip/image icon button before or inside the input container that triggers `fileInput.value?.click()`.
  ```html
  <input type="file" ref="fileInput" class="hidden" multiple accept="image/*" @change="handleImageSelect" />
  <button @click="fileInput?.click()" class="p-2 text-zinc-400 hover:text-zinc-200 transition-colors" title="Attach Image">
    <Image class="w-5 h-5" />
  </button>
  ```
  *(Remember to import `Image` from `lucide-vue-next` if used, or `Paperclip`)*.

- [ ] **Step 3: Add Image Previews UI**
  Above the `<textarea>`, add a container that iterates over `selectedImages`:
  ```html
  <div v-if="selectedImages.length > 0" class="flex flex-wrap gap-2 px-4 pt-2">
    <div v-for="(img, idx) in selectedImages" :key="idx" class="relative group">
      <img :src="img" class="w-16 h-16 object-cover rounded-md border border-zinc-700" />
      <button @click="removeImage(idx)" class="absolute -top-2 -right-2 bg-zinc-800 text-zinc-300 rounded-full p-0.5 opacity-0 group-hover:opacity-100 hover:text-red-400">
        <X class="w-3 h-3" />
      </button>
    </div>
  </div>
  ```
  *(Import `X` from `lucide-vue-next`)*.

- [ ] **Step 4: Update handleSend**
  Update `handleSend` to consume `selectedImages.value`:
  ```typescript
  const handleSend = async function(): Promise<void> {
    if ((!input.value.trim() && selectedImages.value.length === 0) || chat.streaming) return;
    const msg = input.value;
    const images = [...selectedImages.value];
    input.value = "";
    selectedImages.value = [];
    await chat.sendMessage(msg, images.length > 0 ? images : undefined);
  };
  ```

- [ ] **Step 5: Render Images in Messages List**
  In the `v-for="msg in chat.messages"` loop (around line 90):
  ```html
  <div v-if="msg.image_urls && msg.image_urls.length > 0" class="flex flex-wrap gap-2 mb-2">
    <img v-for="(img, idx) in msg.image_urls" :key="idx" :src="img" class="max-w-[300px] max-h-[300px] object-contain rounded-md border border-zinc-700/50" />
  </div>
  ```

- [ ] **Step 6: Run Frontend Checks & Commit**
  Run: `cd frontend && bun run type-check && bun run lint:fix`
  Run: `git add frontend/src/pages/ChatPage.vue`
  Run: `git commit -m "feat(frontend): support vision image upload, preview and rendering"`
  Run: `git push origin HEAD` (Assuming we push to `feature/ai-os-epic`)
