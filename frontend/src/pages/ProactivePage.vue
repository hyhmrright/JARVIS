<template>
  <div class="h-screen flex flex-col bg-zinc-950 font-sans text-zinc-200">
    <PageHeader :title="$t('proactive.title')">
      <template #actions>
        <button class="px-4 py-2 bg-white text-black text-xs font-bold rounded-lg hover:bg-zinc-200 transition-colors" @click="showAddModal = true">
          + {{ $t('proactive.addTask') }}
        </button>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
      <div class="max-w-6xl mx-auto pb-20">

        <div v-if="jobs.length === 0" class="flex flex-col items-center justify-center py-32 text-zinc-500 animate-in fade-in duration-500">
          <div class="text-6xl mb-6 opacity-30">🔔</div>
          <p class="text-sm font-medium">{{ $t('proactive.noTasks') }}</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div v-for="job in jobs" :key="job.id" class="group relative flex flex-col bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700/80 rounded-2xl p-6 transition-all shadow-sm">

            <div class="flex justify-between items-start mb-4">
              <div class="flex flex-wrap items-center gap-2">
                <span
:class="[
                  'text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full',
                  job.trigger_type === 'cron' ? 'bg-zinc-800 text-zinc-400' :
                  job.trigger_type === 'web_watcher' ? 'bg-indigo-500/20 text-indigo-400' :
                  job.trigger_type === 'semantic_watcher' ? 'bg-violet-500/20 text-violet-400' :
                  'bg-amber-500/20 text-amber-400'
                ]">
                  {{ $t(`proactive.triggerTypes.${job.trigger_type}`) || job.trigger_type }}
                </span>
                <span class="text-[10px] font-mono text-zinc-500 bg-zinc-950 px-1.5 py-0.5 rounded">{{ job.schedule }}</span>
              </div>

              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" class="sr-only peer" :checked="job.is_active" @change="toggleJob(job.id)">
                <div class="w-8 h-4.5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-zinc-400 peer-checked:after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-zinc-300"></div>
              </label>
            </div>

            <!-- Job title (click to toggle history) -->
            <h3
              class="text-sm font-semibold text-zinc-200 mb-4 flex-1 cursor-pointer hover:text-zinc-100 transition-colors flex items-center justify-between"
              @click="toggleHistory(job.id)"
            >
              <span class="line-clamp-2">{{ job.task }}</span>
              <span class="text-zinc-600 text-xs ml-2 shrink-0">{{ expandedJobId === job.id ? '▲' : '▼' }}</span>
            </h3>

            <div v-if="job.trigger_metadata" class="bg-zinc-950/50 border border-zinc-800/50 rounded-lg p-3 text-xs mb-4 break-all">
              <span class="text-zinc-500 font-medium mr-2">Target:</span>
              <code class="text-zinc-300 font-mono text-[10px]">{{ job.trigger_metadata.url || job.trigger_metadata.imap_user }}</code>
            </div>

            <!-- Execution history panel -->
            <div v-if="expandedJobId === job.id" class="mb-4 border border-zinc-800/50 rounded-lg overflow-hidden">
              <div class="px-3 py-2 bg-zinc-950/50 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                {{ $t('proactive.history') }}
              </div>
              <div v-if="loadingHistory[job.id]" class="px-3 py-4 text-xs text-zinc-500 text-center">
                {{ $t('common.loading') }}
              </div>
              <div v-else-if="!historyMap[job.id]?.length" class="px-3 py-4 text-xs text-zinc-600 text-center">
                {{ $t('proactive.noHistory') }}
              </div>
              <div v-else class="divide-y divide-zinc-800/50">
                <div v-for="exec in historyMap[job.id]" :key="exec.id" class="px-3 py-2 flex items-center gap-2 text-[11px]">
                  <span
:class="[
                    'shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold',
                    exec.status === 'fired' ? 'bg-green-500/20 text-green-400' :
                    exec.status === 'skipped' ? 'bg-zinc-800 text-zinc-500' :
                    'bg-red-500/20 text-red-400'
                  ]">
                    {{ exec.status === 'fired' ? '✅' : exec.status === 'skipped' ? '⏭' : '❌' }}
                  </span>
                  <span class="text-zinc-500 shrink-0">{{ formatDate(exec.fired_at) }}</span>
                  <span class="text-zinc-400 truncate flex-1">{{ exec.trigger_ctx?.changed_summary || exec.error_msg || '—' }}</span>
                  <span v-if="exec.duration_ms" class="text-zinc-600 shrink-0">{{ (exec.duration_ms / 1000).toFixed(1) }}s</span>
                </div>
              </div>
            </div>

            <div class="flex items-center justify-between mt-auto pt-4 border-t border-zinc-800/50">
              <div class="text-[10px] text-zinc-500 flex items-center gap-1.5 font-medium">
                <span>🕒</span>
                {{ job.last_run_at ? new Date(job.last_run_at).toLocaleString() : $t('proactive.neverRun') }}
              </div>

              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                <!-- Test trigger button -->
                <button
                  class="text-zinc-500 hover:text-indigo-400 transition-colors text-sm p-1"
                  :title="$t('proactive.testTrigger')"
                  :disabled="testing[job.id]"
                  @click.stop="testTrigger(job)"
                >
                  <span v-if="testing[job.id]">⏳</span>
                  <span v-else>▶</span>
                </button>
                <button class="text-zinc-500 hover:text-red-400 transition-colors text-sm p-1" title="Delete Task" @click.stop="deleteJob(job.id)">
                  🗑
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Task Modal -->
    <div v-if="showAddModal" class="fixed inset-0 bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in" @click.self="closeModal()">
      <div class="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h3 class="text-sm font-bold text-zinc-100 tracking-wide">{{ $t('proactive.addTask') }}</h3>
          <button class="text-zinc-500 hover:text-zinc-300 transition-colors" @click="closeModal()">✕</button>
        </div>

        <div class="p-6 space-y-5">
          <div class="flex flex-col gap-2">
            <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.taskPrompt') }}</label>
            <textarea v-model="newJob.task" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-sm outline-none focus:border-zinc-600 transition-colors resize-none h-24" placeholder="e.g. Check for new Apple news and summarize"></textarea>
            <span v-if="formErrors.task" class="text-red-400 text-xs mt-1 block">{{ formErrors.task }}</span>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.schedule') }} (Cron)</label>
              <input v-model="newJob.schedule" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm font-mono outline-none focus:border-zinc-600 transition-colors" placeholder="*/30 * * * *" />
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.triggerType') }}</label>
              <select v-model="newJob.trigger_type" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors">
                <option value="cron">{{ $t('proactive.triggerTypes.cron') }}</option>
                <option value="web_watcher">{{ $t('proactive.triggerTypes.web_watcher') }}</option>
                <option value="semantic_watcher">{{ $t('proactive.triggerTypes.semantic_watcher') }}</option>
                <option value="email">{{ $t('proactive.triggerTypes.email') }}</option>
              </select>
            </div>
          </div>

          <!-- web_watcher fields -->
          <div v-if="newJob.trigger_type === 'web_watcher'" class="flex flex-col gap-2 animate-in fade-in slide-in-from-top-2">
            <label class="text-xs font-semibold text-zinc-400">URL to watch</label>
            <input v-model="newJob.trigger_metadata.url" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="https://..." />
            <span v-if="formErrors.url" class="text-red-400 text-xs mt-1 block">{{ formErrors.url }}</span>
          </div>

          <!-- semantic_watcher fields -->
          <div v-if="newJob.trigger_type === 'semantic_watcher'" class="space-y-4 animate-in fade-in slide-in-from-top-2">
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">URL to watch</label>
              <input v-model="newJob.trigger_metadata.url" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="https://..." />
              <span v-if="formErrors.url" class="text-red-400 text-xs mt-1 block">{{ formErrors.url }}</span>
            </div>
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.targetLabel') }}</label>
              <input v-model="newJob.trigger_metadata.target" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" :placeholder="$t('proactive.targetPlaceholder')" />
              <span v-if="formErrors.target" class="text-red-400 text-xs mt-1 block">{{ formErrors.target }}</span>
            </div>
            <label class="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
              <input v-model="newJob.trigger_metadata.fire_on_init" type="checkbox" class="rounded" />
              {{ $t('proactive.fireOnInit') }}
            </label>
          </div>

          <!-- email fields -->
          <div v-if="newJob.trigger_type === 'email'" class="space-y-4 animate-in fade-in slide-in-from-top-2">
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">IMAP Host</label>
              <input v-model="newJob.trigger_metadata.imap_host" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="imap.gmail.com" />
              <span v-if="formErrors.imap_host" class="text-red-400 text-xs mt-1 block">{{ formErrors.imap_host }}</span>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="flex flex-col gap-2">
                <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.imapFolder') }}</label>
                <input v-model="newJob.trigger_metadata.imap_folder" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="INBOX" />
              </div>
              <div class="flex flex-col gap-2">
                <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.imapPort') }}</label>
                <input v-model.number="newJob.trigger_metadata.imap_port" type="number" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="993" />
              </div>
            </div>
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">Email User</label>
              <input v-model="newJob.trigger_metadata.imap_user" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="user@example.com" />
              <span v-if="formErrors.imap_user" class="text-red-400 text-xs mt-1 block">{{ formErrors.imap_user }}</span>
            </div>
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">App Password</label>
              <input v-model="newJob.trigger_metadata.imap_password" type="password" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" />
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-800 bg-zinc-950/50">
          <button class="px-5 py-2.5 text-xs font-bold text-zinc-400 hover:text-zinc-200 transition-colors" @click="closeModal()">{{ $t('common.cancel') }}</button>
          <button :disabled="!newJob.task.trim()" class="px-5 py-2.5 bg-white text-black text-xs font-bold rounded-lg hover:bg-zinc-200 transition-colors disabled:opacity-40" @click="saveJob">{{ $t('common.confirm') }}</button>
        </div>
      </div>
    </div>

    <!-- Test Result Modal -->
    <div v-if="testResultModal.show" class="fixed inset-0 bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4" @click.self="testResultModal.show = false">
      <div class="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden max-h-[80vh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h3 class="text-sm font-bold text-zinc-100">{{ $t('proactive.testResult') }}</h3>
          <button class="text-zinc-500 hover:text-zinc-300" @click="testResultModal.show = false">✕</button>
        </div>
        <div class="p-6 space-y-4 text-sm">
          <div class="flex items-center gap-3">
            <span class="text-zinc-500 text-xs">{{ $t('proactive.triggered') }}</span>
            <span>{{ testResultModal.triggered ? `✅ ${$t('proactive.triggeredYes')}` : `⏭ ${$t('proactive.triggeredNo')}` }}</span>
          </div>
          <div v-if="testResultModal.durationMs" class="flex items-center gap-3">
            <span class="text-zinc-500 text-xs">{{ $t('proactive.duration') }}</span>
            <span>{{ (testResultModal.durationMs / 1000).toFixed(1) }}s</span>
          </div>
          <template v-if="testResultModal.triggered">
            <div v-if="testResultModal.triggerCtx?.changed_summary" class="flex items-start gap-3">
              <span class="text-zinc-500 text-xs shrink-0">{{ $t('proactive.changeSummary') }}</span>
              <span class="text-zinc-200">{{ testResultModal.triggerCtx.changed_summary }}</span>
            </div>
            <div v-if="testResultModal.agentResult" class="flex flex-col gap-2">
              <span class="text-zinc-500 text-xs">{{ $t('proactive.agentReply') }}</span>
              <div :class="['bg-zinc-950 rounded-lg p-3 text-xs text-zinc-300 whitespace-pre-wrap', testResultModal.isError && 'text-red-400']">
                {{ testResultModal.agentResult }}
              </div>
            </div>
          </template>
        </div>
        <div class="px-6 py-4 border-t border-zinc-800">
          <button class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 text-xs font-bold rounded-lg transition-colors" @click="testResultModal.show = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import client from '@/api/client'
import PageHeader from '@/components/PageHeader.vue'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const { error: toastError } = useToast()

interface CronJob {
  id: string
  schedule: string
  task: string
  trigger_type: string
  trigger_metadata: Record<string, unknown> | null
  is_active: boolean
  last_run_at: string | null
}

interface JobExecution {
  id: string
  run_group_id: string
  fired_at: string
  status: 'fired' | 'skipped' | 'error'
  trigger_ctx: Record<string, unknown> | null
  agent_result: string | null
  duration_ms: number | null
  error_msg: string | null
  attempt: number
}

const jobs = ref<CronJob[]>([])
const showAddModal = ref(false)
const newJob = ref({
  task: '',
  schedule: '*/30 * * * *',
  trigger_type: 'cron',
  trigger_metadata: {} as Record<string, unknown>,
})

interface FormErrors {
  task?: string
  url?: string
  target?: string
  imap_host?: string
  imap_user?: string
}
const formErrors = ref<FormErrors>({})

watch(() => newJob.value.trigger_type, () => {
  formErrors.value = {}
})

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
      try {
        new URL(meta.url as string)
      } catch {
        errors.url = t('proactive.validation.urlInvalid')
      }
    }
  }

  if (newJob.value.trigger_type === 'semantic_watcher') {
    if (!meta.url) {
      errors.url = t('proactive.validation.urlRequired')
    } else {
      try {
        new URL(meta.url as string)
      } catch {
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
    if (!meta.imap_user) {
      errors.imap_user = t('proactive.validation.emailAddressRequired')
    }
  }

  formErrors.value = errors
  return Object.keys(errors).length === 0
}

function closeModal() {
  showAddModal.value = false
  formErrors.value = {}
  newJob.value = { task: '', schedule: '*/30 * * * *', trigger_type: 'cron', trigger_metadata: {} }
}

// Test trigger state
const testing = ref<Record<string, boolean>>({})
const testResultModal = ref<{
  show: boolean
  triggered: boolean
  triggerCtx: Record<string, unknown> | null
  agentResult: string | null
  isError: boolean
  durationMs: number
}>({
  show: false,
  triggered: false,
  triggerCtx: null,
  agentResult: null,
  isError: false,
  durationMs: 0,
})

// History state
const expandedJobId = ref<string | null>(null)
const historyMap = ref<Record<string, JobExecution[]>>({})
const loadingHistory = ref<Record<string, boolean>>({})

const fetchJobs = async () => {
  try {
    const { data } = await client.get('/cron')
    jobs.value = data
  } catch {
    // silently fail - jobs list stays as-is
  }
}

const toggleJob = async (id: string) => {
  try {
    await client.patch(`/cron/${id}/toggle`)
    await fetchJobs()
  } catch {
    toastError(t('proactive.saveError'))
  }
}

const deleteJob = async (id: string) => {
  if (!confirm(t('proactive.deleteConfirm'))) return
  try {
    await client.delete(`/cron/${id}`)
    await fetchJobs()
  } catch {
    toastError(t('proactive.saveError'))
  }
}

const saveJob = async () => {
  if (!validateForm()) return
  try {
    await client.post('/cron', newJob.value)
    closeModal()
    await fetchJobs()
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 422) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail.split('\n')[0] : t('proactive.saveError')
      toastError(msg)
    } else {
      toastError(t('proactive.saveError'))
    }
  }
}

async function testTrigger(job: CronJob) {
  testing.value[job.id] = true
  try {
    const res = await client.post(`/cron/${job.id}/test`)
    testResultModal.value = {
      show: true,
      triggered: res.data.triggered,
      triggerCtx: res.data.trigger_ctx,
      agentResult: res.data.agent_result,
      isError: res.data.is_error,
      durationMs: res.data.duration_ms,
    }
  } catch {
    toastError(t('proactive.testFailed'))
  } finally {
    testing.value[job.id] = false
  }
}

async function toggleHistory(jobId: string) {
  if (expandedJobId.value === jobId) {
    expandedJobId.value = null
    return
  }
  expandedJobId.value = jobId
  if (historyMap.value[jobId]) return // cached

  loadingHistory.value[jobId] = true
  try {
    const res = await client.get(`/cron/${jobId}/history?limit=10`)
    historyMap.value[jobId] = res.data
  } catch {
    historyMap.value[jobId] = []
  } finally {
    loadingHistory.value[jobId] = false
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(fetchJobs)
</script>
