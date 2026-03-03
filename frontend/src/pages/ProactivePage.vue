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
          <div v-for="job in jobs" :key="job.id" class="group relative flex flex-col bg-zinc-900/50 border border-zinc-800 hover:border-zinc-700/80 rounded-2xl p-6 transition-all hover:-translate-y-1 shadow-sm">
            
            <div class="flex justify-between items-start mb-4">
              <div class="flex flex-wrap items-center gap-2">
                <span :class="[
                  'text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full',
                  job.trigger_type === 'cron' ? 'bg-zinc-800 text-zinc-400' :
                  job.trigger_type === 'web_watcher' ? 'bg-indigo-500/20 text-indigo-400' :
                  'bg-amber-500/20 text-amber-400'
                ]">
                  {{ job.trigger_type }}
                </span>
                <span class="text-[10px] font-mono text-zinc-500 bg-zinc-950 px-1.5 py-0.5 rounded">{{ job.schedule }}</span>
              </div>
              
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" class="sr-only peer" :checked="job.is_active" @change="toggleJob(job.id)">
                <div class="w-8 h-4.5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-zinc-400 peer-checked:after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-zinc-300"></div>
              </label>
            </div>

            <h3 class="text-sm font-semibold text-zinc-200 mb-4 line-clamp-2 flex-1">{{ job.task }}</h3>
            
            <div v-if="job.trigger_metadata" class="bg-zinc-950/50 border border-zinc-800/50 rounded-lg p-3 text-xs mb-4 break-all">
              <span class="text-zinc-500 font-medium mr-2">Target:</span>
              <code class="text-zinc-300 font-mono text-[10px]">{{ job.trigger_metadata.url || job.trigger_metadata.imap_user }}</code>
            </div>

            <div class="flex items-center justify-between mt-auto pt-4 border-t border-zinc-800/50">
              <div class="text-[10px] text-zinc-500 flex items-center gap-1.5 font-medium">
                <span>🕒</span>
                {{ job.last_run_at ? new Date(job.last_run_at).toLocaleString() : 'Never run' }}
              </div>
              
              <button class="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition-all text-sm p-1" @click="deleteJob(job.id)" title="Delete Task">
                🗑
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Task Modal -->
    <div v-if="showAddModal" class="fixed inset-0 bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in" @click.self="showAddModal = false">
      <div class="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div class="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h3 class="text-sm font-bold text-zinc-100 tracking-wide">{{ $t('proactive.addTask') }}</h3>
          <button class="text-zinc-500 hover:text-zinc-300 transition-colors" @click="showAddModal = false">✕</button>
        </div>
        
        <div class="p-6 space-y-5">
          <div class="flex flex-col gap-2">
            <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.taskPrompt') }}</label>
            <textarea v-model="newJob.task" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-sm outline-none focus:border-zinc-600 transition-colors resize-none h-24" placeholder="e.g. Check for new Apple news and summarize"></textarea>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.schedule') }} (Cron)</label>
              <input v-model="newJob.schedule" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm font-mono outline-none focus:border-zinc-600 transition-colors" placeholder="*/30 * * * *" />
            </div>

            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">{{ $t('proactive.triggerType') }}</label>
              <select v-model="newJob.trigger_type" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors">
                <option value="cron">Cron (Always fire)</option>
                <option value="web_watcher">Web Watcher</option>
                <option value="email">Email (IMAP)</option>
              </select>
            </div>
          </div>

          <div v-if="newJob.trigger_type === 'web_watcher'" class="flex flex-col gap-2 animate-in fade-in slide-in-from-top-2">
            <label class="text-xs font-semibold text-zinc-400">URL to watch</label>
            <input v-model="newJob.trigger_metadata.url" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="https://..." />
          </div>

          <div v-if="newJob.trigger_type === 'email'" class="space-y-4 animate-in fade-in slide-in-from-top-2">
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">IMAP Host</label>
              <input v-model="newJob.trigger_metadata.imap_host" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="imap.gmail.com" />
            </div>
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">Email User</label>
              <input v-model="newJob.trigger_metadata.imap_user" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" placeholder="user@example.com" />
            </div>
            <div class="flex flex-col gap-2">
              <label class="text-xs font-semibold text-zinc-400">App Password</label>
              <input type="password" v-model="newJob.trigger_metadata.imap_password" class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600 transition-colors" />
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-800 bg-zinc-950/50">
          <button class="px-5 py-2.5 text-xs font-bold text-zinc-400 hover:text-zinc-200 transition-colors" @click="showAddModal = false">{{ $t('common.cancel') }}</button>
          <button class="px-5 py-2.5 bg-white text-black text-xs font-bold rounded-lg hover:bg-zinc-200 transition-colors disabled:opacity-50" :disabled="!newJob.task" @click="saveJob">{{ $t('common.confirm') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import client from '@/api/client';
import PageHeader from '@/components/PageHeader.vue';

const jobs = ref<any[]>([]);
const showAddModal = ref(false);
const newJob = ref({
  task: '',
  schedule: '*/30 * * * *',
  trigger_type: 'cron',
  trigger_metadata: {} as any
});

const fetchJobs = async () => {
  const { data } = await client.get('/cron');
  jobs.value = data;
};

const toggleJob = async (id: string) => {
  await client.patch(`/cron/${id}/toggle`);
  await fetchJobs();
};

const deleteJob = async (id: string) => {
  if (confirm('Delete this monitoring task?')) {
    await client.delete(`/cron/${id}`);
    await fetchJobs();
  }
};

const saveJob = async () => {
  await client.post('/cron', newJob.value);
  showAddModal.value = false;
  newJob.value = { task: '', schedule: '*/30 * * * *', trigger_type: 'cron', trigger_metadata: {} };
  await fetchJobs();
};

onMounted(fetchJobs);
</script>
