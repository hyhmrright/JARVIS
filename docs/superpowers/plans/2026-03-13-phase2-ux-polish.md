# Phase 2: UX Polish — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the product demo-ready: streaming cancel, real upload progress, unified toast notifications, complete i18n, and frontend form validation.

**Architecture:** Four independent frontend+backend tasks. Task 2.2 creates the shared toast infrastructure that Tasks 2.2/2.3/2.4 all use. Task 2.1 touches both frontend (store + page) and backend (chat.py). Tasks 2.3 and 2.4 are frontend-only.

**Tech Stack:** Vue 3 + Pinia + TypeScript + Vite + vue-i18n, FastAPI + asyncio

---

## Task 2.1 — Chat Streaming Cancel

**Files:**
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/pages/ChatPage.vue`
- Modify: `backend/app/api/chat.py`

**Steps:**

- [ ] Step 1: Update `chat.ts` state and sendMessage
  - Add `abortController: null as AbortController | null` to state
  - In `sendMessage()`, create `const controller = new AbortController(); this.abortController = controller;` before fetch
  - Pass `signal: controller.signal` to the fetch options
  - In the catch block, handle AbortError: `if (err.name === 'AbortError') { const aiMsg = this.messages[this.messages.length - 1]; if (aiMsg?.role === 'ai' && aiMsg.content) { aiMsg.content += '\n\n*[已中断]*'; } }` — do NOT show the generic system warning for abort
  - In `finally` block, add `this.abortController = null`
  - Add new `cancelStream()` action: `if (this.abortController) { this.abortController.abort(); }`
  - Add `"stopGenerating": "停止生成"` to `frontend/src/locales/zh.json` under `chat`
  - Add `"stopGenerating": "Stop generating"` to `frontend/src/locales/en.json` under `chat`

- [ ] Step 2: Update ChatPage.vue — swap send button for stop button during streaming

  Replace the single send button (line 230-236) with a conditional:
  ```html
  <!-- Stop button during streaming -->
  <button
    v-if="chat.streaming"
    class="p-2.5 bg-zinc-800 text-white rounded-lg transition-all active:scale-95 hover:bg-zinc-700"
    :title="$t('chat.stopGenerating')"
    @click="chat.cancelStream()"
  >
    <Square class="w-4 h-4" />
  </button>
  <!-- Send button otherwise -->
  <button
    v-else
    :disabled="!input.trim()"
    class="p-2.5 bg-white text-black rounded-lg disabled:opacity-10 transition-all active:scale-95"
    @click="handleSend"
  >
    <ArrowUp class="w-4 h-4 stroke-[3px]" />
  </button>
  ```
  Add `Square` to the lucide-vue-next import list.

- [ ] Step 3: Backend — add `is_disconnected()` check in `backend/app/api/chat.py`

  In the expert graph streaming loop (after `for event in events: yield event`), add:
  ```python
  if await request.is_disconnected():
      break
  ```
  In the supervisor fake-streaming loop (after `yield _format_sse(sse_event)`), add:
  ```python
  if await request.is_disconnected():
      break
  ```
  Note: `stream_completed` stays `False` when the loop breaks early. The `finally` block already saves partial `full_content` to DB if non-empty. No other changes needed — partial saves work out of the box.

- [ ] Step 4: Run static checks
  ```bash
  cd frontend && bun run type-check
  cd ../backend && uv run ruff check --fix && uv run ruff format && uv run pytest --collect-only -q
  ```
  Expected: type-check passes, ruff clean, no import errors

- [ ] Step 5: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add frontend/src/stores/chat.ts frontend/src/pages/ChatPage.vue \
          frontend/src/locales/zh.json frontend/src/locales/en.json \
          backend/app/api/chat.py
  git commit -m "feat: add chat streaming cancel with AbortController and stop button"
  ```

---

## Task 2.2 — Document Upload Progress + Unified Error Toasts

**Files:**
- Create: `frontend/src/composables/useToast.ts`
- Create: `frontend/src/components/ToastContainer.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/pages/DocumentsPage.vue`
- Modify: `frontend/src/pages/ProactivePage.vue`
- Modify: `frontend/src/locales/zh.json` (new keys)
- Modify: `frontend/src/locales/en.json` (new keys)

**Steps:**

- [ ] Step 1: Create `frontend/src/composables/useToast.ts`

  Exact content:
  ```typescript
  import { ref } from 'vue'

  export interface Toast {
    id: number
    type: 'success' | 'error' | 'info'
    message: string
  }

  const toasts = ref<Toast[]>([])
  let _nextId = 0

  export function useToast() {
    function show(message: string, type: Toast['type'] = 'info', duration = 3000) {
      const id = ++_nextId
      toasts.value.push({ id, type, message })
      setTimeout(() => {
        toasts.value = toasts.value.filter(t => t.id !== id)
      }, duration)
    }

    return {
      toasts,
      success: (msg: string) => show(msg, 'success'),
      error: (msg: string) => show(msg, 'error'),
      info: (msg: string) => show(msg, 'info'),
    }
  }
  ```

- [ ] Step 2: Create `frontend/src/components/ToastContainer.vue`

  Exact content:
  ```html
  <template>
    <div class="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="[
            'px-4 py-3 rounded-lg text-sm font-medium shadow-lg pointer-events-auto max-w-xs',
            toast.type === 'success' ? 'bg-emerald-900/90 text-emerald-200 border border-emerald-800' :
            toast.type === 'error' ? 'bg-red-900/90 text-red-200 border border-red-800' :
            'bg-zinc-800/90 text-zinc-200 border border-zinc-700'
          ]"
        >
          {{ toast.message }}
        </div>
      </TransitionGroup>
    </div>
  </template>

  <script setup lang="ts">
  import { useToast } from '@/composables/useToast'
  const { toasts } = useToast()
  </script>

  <style scoped>
  .toast-enter-active, .toast-leave-active { transition: all 0.2s ease; }
  .toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(0.5rem); }
  </style>
  ```

- [ ] Step 3: Mount ToastContainer globally in `frontend/src/App.vue`

  ```html
  <template>
    <div class="min-h-screen w-full bg-zinc-950 text-zinc-50 antialiased selection:bg-zinc-50/10">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
      <ToastContainer />
    </div>
  </template>

  <script setup lang="ts">
  import ToastContainer from '@/components/ToastContainer.vue'
  </script>

  <style>
  .fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
  .fade-enter-from, .fade-leave-to { opacity: 0; }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }
  </style>
  ```

- [ ] Step 4: Add new i18n keys to `zh.json` and `en.json`

  Add to `documents` section in both files:
  - `"uploadZoneText"`: zh="将文件拖到此处或点击上传", en="Drop files here or click to upload"
  - `"uploadZoneHint"`: zh="支持 PDF、TXT、MD、DOCX（最大 50MB）", en="Supports PDF, TXT, MD, DOCX (max 50MB)"
  - `"uploadedTitle"`: zh="已上传文档", en="Uploaded Documents"
  - `"deleteConfirm"`: zh="确定要删除此文档？", en="Delete this document?"
  - `"deleteSuccess"`: zh="文档已删除", en="Document deleted"
  - `"deleteError"`: zh="删除失败，请重试", en="Delete failed, please try again"

  Add to `proactive` section in both files:
  - `"deleteConfirm"`: zh="删除此监控任务？", en="Delete this monitoring task?"
  - `"neverRun"`: zh="从未运行", en="Never run"
  - `"duration"`: zh="耗时", en="Duration"
  - `"triggeredYes"`: zh="是", en="Yes"
  - `"triggeredNo"`: zh="否（未触发）", en="No (not triggered)"
  - `"changeSummary"`: zh="变化摘要", en="Change Summary"
  - `"agentReply"`: zh="Agent 回复", en="Agent Reply"
  - `"saveError"`: zh="创建失败，请稍后重试", en="Failed to create task, please try again"

- [ ] Step 5: Update `frontend/src/pages/DocumentsPage.vue`
  - Add `import { useToast } from '@/composables/useToast'` and `const { success, error: toastError } = useToast()`
  - Add `const uploadProgress = ref(0)` (alongside other refs)
  - Remove `const result = ref('')` and `const resultType = ref<'success' | 'error'>('success')` — these are no longer needed
  - Update `processFile`: add `onUploadProgress` to axios call, use `toastError`/`success` instead of setting `result`/`resultType`, reset `uploadProgress` in finally
  - Update `deleteDocument`: use `toastError(t('documents.deleteError'))` instead of `alert()`, add success toast
  - In template: replace `Drop your files here or click to browse` with `{{ $t('documents.uploadZoneText') }}`, replace `Supports PDF...` with `{{ $t('documents.uploadZoneHint') }}`, replace `Uploaded Documents` with `{{ $t('documents.uploadedTitle') }}`
  - In template: remove the inline result message div (`<div v-if="result" ...>`)
  - In template: change progress bar from shimmer to real: `<div class="progress-bar-fill" :style="{ width: uploadProgress + '%' }"></div>` and update CSS to remove shimmer animation

  Exact processFile function:
  ```typescript
  async function processFile(file: File) {
    if (file.size > 50 * 1024 * 1024) {
      toastError(t('documents.fileTooLarge'))
      return
    }
    uploading.value = true
    uploadProgress.value = 0
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await client.post('/documents', form, {
        onUploadProgress(e) {
          if (e.total) uploadProgress.value = Math.round((e.loaded / e.total) * 100)
        },
      })
      success(t('documents.uploadSuccess', { count: data.chunk_count }))
      await fetchDocuments()
    } catch {
      toastError(t('documents.uploadError'))
    } finally {
      uploading.value = false
      uploadProgress.value = 0
    }
  }
  ```

  Exact deleteDocument function:
  ```typescript
  async function deleteDocument(id: string) {
    if (!confirm(t('documents.deleteConfirm'))) return
    try {
      await client.delete(`/documents/${id}`)
      await fetchDocuments()
      success(t('documents.deleteSuccess'))
    } catch {
      toastError(t('documents.deleteError'))
    }
  }
  ```

- [ ] Step 6: Update `frontend/src/pages/ProactivePage.vue`
  - Add `import { useToast } from '@/composables/useToast'` and `const { error: toastError } = useToast()`
  - In `testTrigger()` catch block: replace `alert(t('proactive.testFailed'))` with `toastError(t('proactive.testFailed'))`
  - In `deleteJob()`: replace `confirm('Delete this monitoring task?')` with `confirm(t('proactive.deleteConfirm'))`
  - In template test result modal:
    - Replace `'是'` with `$t('proactive.triggeredYes')`, `'否（未触发）'` with `$t('proactive.triggeredNo')`
    - Replace hardcoded `'耗时'` with `$t('proactive.duration')`
    - Replace hardcoded `'变化摘要'` with `$t('proactive.changeSummary')`
    - Replace hardcoded `'Agent 回复'` with `$t('proactive.agentReply')`
  - In job card: replace `'Never run'` with `$t('proactive.neverRun')`

- [ ] Step 7: Run static checks
  ```bash
  cd frontend && bun run type-check && bun run lint:fix
  ```
  Expected: type-check passes, no lint errors

- [ ] Step 8: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add frontend/src/composables/useToast.ts frontend/src/components/ToastContainer.vue \
          frontend/src/App.vue frontend/src/pages/DocumentsPage.vue \
          frontend/src/pages/ProactivePage.vue \
          frontend/src/locales/zh.json frontend/src/locales/en.json
  git commit -m "feat: add useToast composable, real upload progress, replace alerts with toasts"
  ```

---

## Task 2.3 — i18n Completeness

**Files:**
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/locales/ja.json`
- Modify: `frontend/src/locales/ko.json`
- Modify: `frontend/src/locales/fr.json`
- Modify: `frontend/src/locales/de.json`
- Create: `frontend/scripts/check-i18n.ts`
- Modify: `frontend/package.json` (add `i18n:check` script)

**Missing key analysis:**
- All locales (en/ja/ko/fr/de): missing `common.prev`, `common.next`, `common.confirm`
- All locales: missing `chat.stopGenerating` (added to zh/en in Task 2.1, now add to ja/ko/fr/de)
- en/ja/ko/fr/de: missing entire `admin` section
- ja/ko/fr/de: missing entire `proactive` section
- All locales: missing new keys from Task 2.2 (`documents.uploadZoneText/Hint/uploadedTitle/deleteConfirm/deleteSuccess/deleteError`, `proactive.deleteConfirm/neverRun/duration/triggeredYes/triggeredNo/changeSummary/agentReply/saveError`)

**Steps:**

- [ ] Step 1: Add missing keys to `en.json`
  - In `common`: add `"prev": "Previous"`, `"next": "Next"`, `"confirm": "Confirm"`
  - In `chat`: add `"stopGenerating": "Stop generating"` (if not added in Task 2.1)
  - In `documents`: add the 6 new keys from Task 2.2
  - In `proactive`: add the 8 new keys from Task 2.2
  - Add entire `admin` section:
    ```json
    "admin": {
      "title": "Admin Panel",
      "tabs": {
        "users": "Users",
        "plugins": "Plugins",
        "stats": "Statistics"
      },
      "users": {
        "email": "Email",
        "name": "Name",
        "role": "Role",
        "status": "Status",
        "actions": "Actions",
        "active": "Active",
        "disabled": "Disabled",
        "enable": "Enable",
        "disable": "Disable"
      },
      "plugins": {
        "tools": "Tools",
        "install": "Install Plugin",
        "installTitle": "Install Plugin",
        "installDesc": "Enter the raw URL of the plugin Python file (e.g. from GitHub)"
      },
      "stats": {
        "users": "Total Users",
        "conversations": "Total Conversations",
        "messages": "Total Messages",
        "tokens": "Total Tokens Used"
      }
    }
    ```

- [ ] Step 2: Add missing keys to `ja.json`
  - In `common`: add `"prev": "前へ"`, `"next": "次へ"`, `"confirm": "確認"`
  - In `chat`: add `"stopGenerating": "生成を停止"`
  - In `documents`: add (Japanese):
    - `uploadZoneText`: "ファイルをここにドロップまたはクリックしてアップロード"
    - `uploadZoneHint`: "PDF、TXT、MD、DOCX をサポート（最大 50MB）"
    - `uploadedTitle`: "アップロード済みドキュメント"
    - `deleteConfirm`: "このドキュメントを削除しますか？"
    - `deleteSuccess`: "ドキュメントが削除されました"
    - `deleteError`: "削除に失敗しました。再試行してください"
  - Add entire `proactive` section (Japanese):
    ```json
    "proactive": {
      "title": "プロアクティブ監視",
      "addTask": "タスクを追加",
      "noTasks": "監視タスクがありません",
      "lastRun": "最終トリガー",
      "schedule": "スケジュール",
      "triggerType": "トリガータイプ",
      "taskPrompt": "AIタスク指示",
      "targetLabel": "監視対象",
      "targetPlaceholder": "製品価格、ニュース見出し、キーワード…",
      "useBrowser": "ブラウザレンダリングを使用（SPA対応）",
      "fireOnInit": "作成後すぐに一度トリガー",
      "imapFolder": "IMAPフォルダ",
      "imapPort": "IMAPポート",
      "triggerTypes": {
        "cron": "定期実行",
        "web_watcher": "ウェブ監視（ハッシュ）",
        "semantic_watcher": "ウェブ監視（セマンティック）",
        "email": "メールトリガー"
      },
      "testTrigger": "テストトリガー",
      "testResult": "テスト結果",
      "triggered": "トリガー済み",
      "testFailed": "テストに失敗しました。再試行してください",
      "history": "実行履歴",
      "noHistory": "実行記録がありません",
      "deleteConfirm": "この監視タスクを削除しますか？",
      "neverRun": "未実行",
      "duration": "所要時間",
      "triggeredYes": "はい",
      "triggeredNo": "いいえ（未トリガー）",
      "changeSummary": "変更サマリー",
      "agentReply": "エージェント応答",
      "saveError": "作成に失敗しました。しばらくしてから再試行してください"
    }
    ```
  - Add `admin` section (Japanese):
    ```json
    "admin": {
      "title": "管理パネル",
      "tabs": { "users": "ユーザー管理", "plugins": "プラグイン管理", "stats": "統計" },
      "users": { "email": "メール", "name": "名前", "role": "役割", "status": "ステータス", "actions": "操作", "active": "有効", "disabled": "無効", "enable": "有効化", "disable": "無効化" },
      "plugins": { "tools": "ツール数", "install": "プラグインをインストール", "installTitle": "プラグインのインストール", "installDesc": "プラグインPythonファイルの生URLを入力してください（例：GitHubから）" },
      "stats": { "users": "総ユーザー数", "conversations": "総会話数", "messages": "総メッセージ数", "tokens": "総トークン使用量" }
    }
    ```

- [ ] Step 3: Add missing keys to `ko.json`
  - In `common`: add `"prev": "이전"`, `"next": "다음"`, `"confirm": "확인"`
  - In `chat`: add `"stopGenerating": "생성 중지"`
  - In `documents`: add (Korean):
    - `uploadZoneText`: "파일을 여기에 드롭하거나 클릭하여 업로드"
    - `uploadZoneHint`: "PDF, TXT, MD, DOCX 지원 (최대 50MB)"
    - `uploadedTitle`: "업로드된 문서"
    - `deleteConfirm`: "이 문서를 삭제하시겠습니까?"
    - `deleteSuccess`: "문서가 삭제되었습니다"
    - `deleteError`: "삭제에 실패했습니다. 다시 시도해 주세요"
  - Add entire `proactive` section (Korean):
    ```json
    "proactive": {
      "title": "프로액티브 모니터링",
      "addTask": "작업 추가",
      "noTasks": "모니터링 작업이 없습니다",
      "lastRun": "마지막 트리거",
      "schedule": "스케줄",
      "triggerType": "트리거 유형",
      "taskPrompt": "AI 작업 지시",
      "targetLabel": "모니터링 대상",
      "targetPlaceholder": "제품 가격, 뉴스 헤드라인, 키워드…",
      "useBrowser": "브라우저 렌더링 사용 (SPA 지원)",
      "fireOnInit": "생성 후 즉시 한 번 트리거",
      "imapFolder": "IMAP 폴더",
      "imapPort": "IMAP 포트",
      "triggerTypes": {
        "cron": "정기 실행",
        "web_watcher": "웹 감시 (해시)",
        "semantic_watcher": "웹 감시 (시맨틱)",
        "email": "이메일 트리거"
      },
      "testTrigger": "트리거 테스트",
      "testResult": "테스트 결과",
      "triggered": "트리거됨",
      "testFailed": "테스트에 실패했습니다. 다시 시도해 주세요",
      "history": "실행 기록",
      "noHistory": "실행 기록이 없습니다",
      "deleteConfirm": "이 모니터링 작업을 삭제하시겠습니까?",
      "neverRun": "실행 없음",
      "duration": "소요 시간",
      "triggeredYes": "예",
      "triggeredNo": "아니오 (트리거되지 않음)",
      "changeSummary": "변경 요약",
      "agentReply": "에이전트 응답",
      "saveError": "작업 생성에 실패했습니다. 잠시 후 다시 시도해 주세요"
    }
    ```
  - Add `admin` section (Korean):
    ```json
    "admin": {
      "title": "관리자 패널",
      "tabs": { "users": "사용자 관리", "plugins": "플러그인 관리", "stats": "통계" },
      "users": { "email": "이메일", "name": "이름", "role": "역할", "status": "상태", "actions": "작업", "active": "활성", "disabled": "비활성", "enable": "활성화", "disable": "비활성화" },
      "plugins": { "tools": "도구 수", "install": "플러그인 설치", "installTitle": "플러그인 설치", "installDesc": "플러그인 Python 파일의 원본 URL을 입력하세요 (예: GitHub에서)" },
      "stats": { "users": "총 사용자 수", "conversations": "총 대화 수", "messages": "총 메시지 수", "tokens": "총 토큰 사용량" }
    }
    ```

- [ ] Step 4: Add missing keys to `fr.json`
  - In `common`: add `"prev": "Précédent"`, `"next": "Suivant"`, `"confirm": "Confirmer"`
  - In `chat`: add `"stopGenerating": "Arrêter la génération"`
  - In `documents`: add (French):
    - `uploadZoneText`: "Déposez vos fichiers ici ou cliquez pour parcourir"
    - `uploadZoneHint`: "Formats supportés : PDF, TXT, MD, DOCX (max 50 Mo)"
    - `uploadedTitle`: "Documents téléchargés"
    - `deleteConfirm`: "Supprimer ce document ?"
    - `deleteSuccess`: "Document supprimé"
    - `deleteError`: "Échec de la suppression, veuillez réessayer"
  - Add entire `proactive` section (French):
    ```json
    "proactive": {
      "title": "Surveillance proactive",
      "addTask": "Ajouter une tâche",
      "noTasks": "Aucune tâche de surveillance",
      "lastRun": "Dernier déclenchement",
      "schedule": "Planification",
      "triggerType": "Type de déclencheur",
      "taskPrompt": "Instruction IA",
      "targetLabel": "Cible de surveillance",
      "targetPlaceholder": "Prix du produit, titre d'actualité, mot-clé…",
      "useBrowser": "Utiliser le rendu navigateur (SPA)",
      "fireOnInit": "Déclencher une fois à la création",
      "imapFolder": "Dossier IMAP",
      "imapPort": "Port IMAP",
      "triggerTypes": {
        "cron": "Planifié",
        "web_watcher": "Surveillance web (hash)",
        "semantic_watcher": "Surveillance web (sémantique)",
        "email": "Déclencheur e-mail"
      },
      "testTrigger": "Tester le déclencheur",
      "testResult": "Résultat du test",
      "triggered": "Déclenché",
      "testFailed": "Échec du test, veuillez réessayer",
      "history": "Historique d'exécution",
      "noHistory": "Aucun historique d'exécution",
      "deleteConfirm": "Supprimer cette tâche de surveillance ?",
      "neverRun": "Jamais exécuté",
      "duration": "Durée",
      "triggeredYes": "Oui",
      "triggeredNo": "Non (non déclenché)",
      "changeSummary": "Résumé des modifications",
      "agentReply": "Réponse de l'agent",
      "saveError": "Échec de la création, veuillez réessayer"
    }
    ```
  - Add `admin` section (French):
    ```json
    "admin": {
      "title": "Panneau d'administration",
      "tabs": { "users": "Utilisateurs", "plugins": "Plugins", "stats": "Statistiques" },
      "users": { "email": "E-mail", "name": "Nom", "role": "Rôle", "status": "Statut", "actions": "Actions", "active": "Actif", "disabled": "Désactivé", "enable": "Activer", "disable": "Désactiver" },
      "plugins": { "tools": "Outils", "install": "Installer un plugin", "installTitle": "Installer un plugin", "installDesc": "Entrez l'URL brute du fichier Python du plugin (ex : depuis GitHub)" },
      "stats": { "users": "Utilisateurs totaux", "conversations": "Conversations totales", "messages": "Messages totaux", "tokens": "Tokens totaux utilisés" }
    }
    ```

- [ ] Step 5: Add missing keys to `de.json`
  - In `common`: add `"prev": "Zurück"`, `"next": "Weiter"`, `"confirm": "Bestätigen"`
  - In `chat`: add `"stopGenerating": "Generierung stoppen"`
  - In `documents`: add (German):
    - `uploadZoneText`: "Dateien hierher ziehen oder klicken zum Durchsuchen"
    - `uploadZoneHint`: "Unterstützt PDF, TXT, MD, DOCX (max. 50 MB)"
    - `uploadedTitle`: "Hochgeladene Dokumente"
    - `deleteConfirm`: "Dieses Dokument löschen?"
    - `deleteSuccess`: "Dokument gelöscht"
    - `deleteError`: "Löschen fehlgeschlagen, bitte erneut versuchen"
  - Add entire `proactive` section (German):
    ```json
    "proactive": {
      "title": "Proaktive Überwachung",
      "addTask": "Aufgabe hinzufügen",
      "noTasks": "Keine Überwachungsaufgaben",
      "lastRun": "Letzter Auslöser",
      "schedule": "Zeitplan",
      "triggerType": "Auslösertyp",
      "taskPrompt": "KI-Aufgabenanweisung",
      "targetLabel": "Überwachungsziel",
      "targetPlaceholder": "Produktpreis, Nachrichtenüberschrift, Schlüsselwort…",
      "useBrowser": "Browser-Rendering verwenden (SPA-Unterstützung)",
      "fireOnInit": "Nach Erstellung sofort einmal auslösen",
      "imapFolder": "IMAP-Ordner",
      "imapPort": "IMAP-Port",
      "triggerTypes": {
        "cron": "Geplant",
        "web_watcher": "Web-Überwachung (Hash)",
        "semantic_watcher": "Web-Überwachung (Semantisch)",
        "email": "E-Mail-Auslöser"
      },
      "testTrigger": "Auslöser testen",
      "testResult": "Testergebnis",
      "triggered": "Ausgelöst",
      "testFailed": "Test fehlgeschlagen, bitte erneut versuchen",
      "history": "Ausführungsverlauf",
      "noHistory": "Keine Ausführungsaufzeichnungen",
      "deleteConfirm": "Diese Überwachungsaufgabe löschen?",
      "neverRun": "Nie ausgeführt",
      "duration": "Dauer",
      "triggeredYes": "Ja",
      "triggeredNo": "Nein (nicht ausgelöst)",
      "changeSummary": "Änderungszusammenfassung",
      "agentReply": "Agent-Antwort",
      "saveError": "Erstellung fehlgeschlagen, bitte später erneut versuchen"
    }
    ```
  - Add `admin` section (German):
    ```json
    "admin": {
      "title": "Admin-Bereich",
      "tabs": { "users": "Benutzerverwaltung", "plugins": "Plugin-Verwaltung", "stats": "Statistiken" },
      "users": { "email": "E-Mail", "name": "Name", "role": "Rolle", "status": "Status", "actions": "Aktionen", "active": "Aktiv", "disabled": "Deaktiviert", "enable": "Aktivieren", "disable": "Deaktivieren" },
      "plugins": { "tools": "Werkzeuge", "install": "Plugin installieren", "installTitle": "Plugin installieren", "installDesc": "Geben Sie die URL der Python-Datei des Plugins ein (z. B. von GitHub)" },
      "stats": { "users": "Gesamtbenutzer", "conversations": "Gesamtgespräche", "messages": "Gesamtnachrichten", "tokens": "Verbrauchte Tokens gesamt" }
    }
    ```

- [ ] Step 6: Create `frontend/scripts/check-i18n.ts`

  ```typescript
  import zh from '../src/locales/zh.json' with { type: 'json' }
  import en from '../src/locales/en.json' with { type: 'json' }
  import ja from '../src/locales/ja.json' with { type: 'json' }
  import ko from '../src/locales/ko.json' with { type: 'json' }
  import fr from '../src/locales/fr.json' with { type: 'json' }
  import de from '../src/locales/de.json' with { type: 'json' }

  function collectKeys(obj: Record<string, unknown>, prefix = ''): string[] {
    return Object.entries(obj).flatMap(([key, val]) => {
      const full = prefix ? `${prefix}.${key}` : key
      return val !== null && typeof val === 'object' && !Array.isArray(val)
        ? collectKeys(val as Record<string, unknown>, full)
        : [full]
    })
  }

  const zhKeys = new Set(collectKeys(zh as Record<string, unknown>))
  const locales: Record<string, unknown> = { en, ja, ko, fr, de }
  let failed = false

  for (const [lang, data] of Object.entries(locales)) {
    const langKeys = new Set(collectKeys(data as Record<string, unknown>))
    const missing = [...zhKeys].filter(k => !langKeys.has(k))
    if (missing.length > 0) {
      console.error(`❌ ${lang} is missing ${missing.length} key(s):`)
      missing.forEach(k => console.error(`   - ${k}`))
      failed = true
    } else {
      console.log(`✅ ${lang}: all keys present`)
    }
  }

  if (failed) process.exit(1)
  ```

- [ ] Step 7: Add `i18n:check` to `frontend/package.json` scripts section

  Add `"i18n:check": "bun scripts/check-i18n.ts"` to the scripts object.

- [ ] Step 8: Run CI check
  ```bash
  cd frontend && bun scripts/check-i18n.ts
  ```
  Expected: `✅ en: all keys present`, `✅ ja: all keys present`, etc.

- [ ] Step 9: Run type-check + lint
  ```bash
  cd frontend && bun run type-check && bun run lint:fix
  ```
  Expected: all pass

- [ ] Step 10: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add frontend/src/locales/ frontend/scripts/check-i18n.ts frontend/package.json
  git commit -m "feat: fill missing i18n keys across all locales, add CI completeness check"
  ```

---

## Task 2.4 — Trigger Metadata Schema Validation (Frontend)

**Files:**
- Modify: `frontend/src/pages/ProactivePage.vue`
- Modify: `frontend/src/locales/zh.json` (add validation keys)
- Modify: `frontend/src/locales/en.json` (add validation keys)
- Modify: `frontend/src/locales/ja.json`, `ko.json`, `fr.json`, `de.json` (same keys)

**Steps:**

- [ ] Step 1: Add validation i18n keys to ALL locale files

  Add under `proactive` section a new `validation` sub-object in each file:

  - zh.json:
    ```json
    "validation": {
      "taskRequired": "请输入任务指令",
      "urlRequired": "请输入监控 URL",
      "urlInvalid": "请输入有效的 URL（以 https:// 开头）",
      "targetRequired": "请输入监控目标",
      "imapHostRequired": "请输入 IMAP 主机地址",
      "emailAddressRequired": "请输入邮件地址"
    }
    ```
  - en.json:
    ```json
    "validation": {
      "taskRequired": "Task prompt is required",
      "urlRequired": "URL is required",
      "urlInvalid": "Please enter a valid URL (starting with https://)",
      "targetRequired": "Monitor target is required",
      "imapHostRequired": "IMAP host is required",
      "emailAddressRequired": "Email address is required"
    }
    ```
  - ja.json:
    ```json
    "validation": {
      "taskRequired": "タスク指示を入力してください",
      "urlRequired": "URLを入力してください",
      "urlInvalid": "有効なURL（https://で始まる）を入力してください",
      "targetRequired": "監視対象を入力してください",
      "imapHostRequired": "IMAPホストを入力してください",
      "emailAddressRequired": "メールアドレスを入力してください"
    }
    ```
  - ko.json:
    ```json
    "validation": {
      "taskRequired": "작업 지시를 입력해 주세요",
      "urlRequired": "URL을 입력해 주세요",
      "urlInvalid": "유효한 URL(https://로 시작)을 입력해 주세요",
      "targetRequired": "모니터링 대상을 입력해 주세요",
      "imapHostRequired": "IMAP 호스트를 입력해 주세요",
      "emailAddressRequired": "이메일 주소를 입력해 주세요"
    }
    ```
  - fr.json:
    ```json
    "validation": {
      "taskRequired": "L'instruction de tâche est requise",
      "urlRequired": "L'URL est requise",
      "urlInvalid": "Veuillez saisir une URL valide (commençant par https://)",
      "targetRequired": "La cible de surveillance est requise",
      "imapHostRequired": "L'hôte IMAP est requis",
      "emailAddressRequired": "L'adresse e-mail est requise"
    }
    ```
  - de.json:
    ```json
    "validation": {
      "taskRequired": "Aufgabenanweisung ist erforderlich",
      "urlRequired": "URL ist erforderlich",
      "urlInvalid": "Bitte geben Sie eine gültige URL ein (beginnend mit https://)",
      "targetRequired": "Überwachungsziel ist erforderlich",
      "imapHostRequired": "IMAP-Host ist erforderlich",
      "emailAddressRequired": "E-Mail-Adresse ist erforderlich"
    }
    ```

- [ ] Step 2: Add form validation logic to `ProactivePage.vue`

  In `<script setup>`, add after existing refs:
  ```typescript
  interface FormErrors {
    task?: string
    url?: string
    target?: string
    imap_host?: string
    email_address?: string
  }
  const formErrors = ref<FormErrors>({})

  function validateForm(): boolean {
    const errors: FormErrors = {}
    const meta = newJob.value.trigger_metadata

    if (!newJob.value.task.trim()) {
      errors.task = t('proactive.validation.taskRequired')
    }

    if (newJob.value.trigger_type === 'web_watcher') {
      if (!meta.url) {
        errors.url = t('proactive.validation.urlRequired')
      } else {
        try { new URL(meta.url as string) } catch {
          errors.url = t('proactive.validation.urlInvalid')
        }
      }
    }

    if (newJob.value.trigger_type === 'semantic_watcher') {
      if (!meta.url) {
        errors.url = t('proactive.validation.urlRequired')
      } else {
        try { new URL(meta.url as string) } catch {
          errors.url = t('proactive.validation.urlInvalid')
        }
      }
      if (!meta.target) {
        errors.target = t('proactive.validation.targetRequired')
      }
    }

    if (newJob.value.trigger_type === 'email') {
      if (!meta.imap_host) {
        errors.imap_host = t('proactive.validation.imapHostRequired')
      }
      if (!meta.email_address) {
        errors.email_address = t('proactive.validation.emailAddressRequired')
      }
    }

    formErrors.value = errors
    return Object.keys(errors).length === 0
  }
  ```

- [ ] Step 3: Update `saveJob` in ProactivePage.vue

  Replace the current `saveJob` function:
  ```typescript
  const saveJob = async () => {
    if (!validateForm()) return
    try {
      await client.post('/cron', newJob.value)
      showAddModal.value = false
      newJob.value = { task: '', schedule: '*/30 * * * *', trigger_type: 'cron', trigger_metadata: {} }
      formErrors.value = {}
      await fetchJobs()
    } catch (err: any) {
      if (err.response?.status === 422) {
        // Show the specific API validation error message
        const detail = err.response.data?.detail
        const msg = typeof detail === 'string' ? detail.split('\n')[0] : t('proactive.saveError')
        toastError(msg)
      } else {
        toastError(t('proactive.saveError'))
      }
    }
  }
  ```

  Also add a `closeModal` helper to reset form state on cancel:
  ```typescript
  function closeModal() {
    showAddModal.value = false
    formErrors.value = {}
    newJob.value = { task: '', schedule: '*/30 * * * *', trigger_type: 'cron', trigger_metadata: {} }
  }
  ```
  Replace `@click="showAddModal = false"` on the cancel button and X button with `@click="closeModal()"`.

- [ ] Step 4: Add error display to the form template

  After the task textarea, add:
  ```html
  <span v-if="formErrors.task" class="text-red-400 text-xs">{{ formErrors.task }}</span>
  ```

  After the `web_watcher` URL input, add:
  ```html
  <span v-if="formErrors.url" class="text-red-400 text-xs">{{ formErrors.url }}</span>
  ```

  After the `semantic_watcher` URL input, add:
  ```html
  <span v-if="formErrors.url" class="text-red-400 text-xs">{{ formErrors.url }}</span>
  ```

  After the `semantic_watcher` target input, add:
  ```html
  <span v-if="formErrors.target" class="text-red-400 text-xs">{{ formErrors.target }}</span>
  ```

  After the email `imap_host` input, add:
  ```html
  <span v-if="formErrors.imap_host" class="text-red-400 text-xs">{{ formErrors.imap_host }}</span>
  ```

  After the email address (`imap_user`) input, add:
  ```html
  <span v-if="formErrors.email_address" class="text-red-400 text-xs">{{ formErrors.email_address }}</span>
  ```

  > Note: The email form binds the address field to `trigger_metadata.imap_user` in the template. The validation error key is `email_address` but is displayed below the `imap_user` input. If the backend `EmailWatcherMetadata` uses `email_address` as its field name, verify alignment between what the form sends (`imap_user`) and what the backend expects (`email_address`) — they may need to be reconciled in a follow-up.

- [ ] Step 5: Run type-check + CI check
  ```bash
  cd frontend
  bun run type-check
  bun run lint:fix
  bun scripts/check-i18n.ts
  ```
  Expected: all pass

- [ ] Step 6: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add frontend/src/pages/ProactivePage.vue frontend/src/locales/
  git commit -m "feat: add frontend form validation for trigger metadata with field-level errors"
  ```

---

## Final Verification

- [ ] Run full frontend type-check: `cd frontend && bun run type-check`
- [ ] Run i18n completeness check: `cd frontend && bun scripts/check-i18n.ts`
- [ ] Run backend checks: `cd backend && uv run ruff check && uv run pytest --collect-only -q`
- [ ] Push: `git push origin dev`
