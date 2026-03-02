<template>
  <div class="page-container">
    <PageHeader :title="$t('proactive.title')">
      <template #actions>
        <button class="btn-accent" @click="showAddModal = true">
          + {{ $t('proactive.addTask') }}
        </button>
      </template>
    </PageHeader>

    <div class="page-content custom-scrollbar">
      <div v-if="jobs.length === 0" class="empty-state animate-fade-in">
        <div class="empty-icon">🔔</div>
        <p>{{ $t('proactive.noTasks') }}</p>
      </div>

      <div class="grid-layout">
        <div v-for="job in jobs" :key="job.id" class="glass-card job-card animate-fade-in">
          <div class="job-main">
            <div class="job-badge-row">
              <span :class="['type-badge', job.trigger_type]">
                {{ job.trigger_type.toUpperCase() }}
              </span>
              <span class="cron-text">{{ job.schedule }}</span>
            </div>
            <h3 class="job-task">{{ job.task }}</h3>
            <div v-if="job.trigger_metadata" class="job-meta">
              <span class="meta-label">Target:</span>
              <code class="meta-value">{{ job.trigger_metadata.url || job.trigger_metadata.imap_user }}</code>
            </div>
            <div class="last-run">
              <span class="clock-icon">🕒</span>
              {{ $t('proactive.lastRun') }}: {{ job.last_run_at ? new Date(job.last_run_at).toLocaleString() : '-' }}
            </div>
          </div>
          
          <div class="job-ctrl">
            <label class="switch">
              <input
                type="checkbox"
                :checked="job.is_active"
                @change="toggleJob(job.id)"
              />
              <span class="slider round"></span>
            </label>
            <button class="btn-delete" @click="deleteJob(job.id)" title="Delete Task">🗑</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Task Modal -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal-content glass-card animate-zoom-in">
        <div class="modal-header">
          <h3>{{ $t('proactive.addTask') }}</h3>
          <button class="btn-close" @click="showAddModal = false">×</button>
        </div>
        
        <div class="form-body">
          <div class="form-group">
            <label>{{ $t('proactive.taskPrompt') }}</label>
            <textarea v-model="newJob.task" class="modern-input" placeholder="e.g. Check for new Apple news and summarize"></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ $t('proactive.schedule') }} (Cron)</label>
              <input v-model="newJob.schedule" class="modern-input" placeholder="*/30 * * * *" />
            </div>

            <div class="form-group">
              <label>{{ $t('proactive.triggerType') }}</label>
              <select v-model="newJob.trigger_type" class="modern-input">
                <option value="cron">Cron (Always fire)</option>
                <option value="web_watcher">Web Watcher</option>
                <option value="email">Email (IMAP)</option>
              </select>
            </div>
          </div>

          <div v-if="newJob.trigger_type === 'web_watcher'" class="form-group animate-fade-in">
            <label>URL to watch</label>
            <input v-model="newJob.trigger_metadata.url" class="modern-input" placeholder="https://..." />
          </div>

          <div v-if="newJob.trigger_type === 'email'" class="form-group animate-fade-in">
            <label>IMAP Host</label>
            <input v-model="newJob.trigger_metadata.imap_host" class="modern-input" placeholder="imap.gmail.com" />
            <label>Email User</label>
            <input v-model="newJob.trigger_metadata.imap_user" class="modern-input" />
            <label>App Password</label>
            <input type="password" v-model="newJob.trigger_metadata.imap_password" class="modern-input" />
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn-ghost" @click="showAddModal = false">{{ $t('common.cancel') }}</button>
          <button class="btn-accent" :disabled="!newJob.task" @click="saveJob">{{ $t('common.confirm') }}</button>
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

<style scoped>
.page-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.page-content {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  max-width: 1000px;
  width: 100%;
  margin: 0 auto;
}

.grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.glass-card {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
}

.job-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  transition: transform 0.2s, border-color 0.2s;
}

.job-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

.job-badge-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.type-badge {
  font-size: 0.65rem;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}
.type-badge.cron { background: rgba(255,255,255,0.1); color: var(--text-secondary); }
.type-badge.web_watcher { background: rgba(99, 102, 241, 0.15); color: var(--accent-light); }
.type-badge.email { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }

.cron-text { font-size: 0.8rem; color: var(--text-muted); font-family: monospace; }

.job-task {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-primary);
}

.job-meta {
  background: rgba(0,0,0,0.2);
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-size: 0.8rem;
  display: flex;
  gap: 0.5rem;
}

.meta-label { color: var(--text-muted); }
.meta-value { color: var(--accent-light); font-family: monospace; word-break: break-all; }

.last-run {
  font-size: 0.75rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.job-ctrl {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}

.btn-delete {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  opacity: 0.4;
  transition: all 0.2s;
}
.btn-delete:hover { opacity: 1; color: var(--danger); }

/* ── Form ── */
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  margin-bottom: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.modern-input {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-bright);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 0.75rem;
  font-size: 0.95rem;
  outline: none;
}
.modern-input:focus { border-color: var(--accent); }

textarea.modern-input { height: 80px; resize: none; }

.empty-state {
  height: 60vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.empty-icon { font-size: 4rem; margin-bottom: 1.5rem; opacity: 0.3; }

.animate-fade-in { animation: fadeIn 0.3s ease; }
.animate-zoom-in { animation: zoomIn 0.2s ease; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes zoomIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }

/* Switch UI */
.switch { position: relative; display: inline-block; width: 36px; height: 20px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
  position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
  background-color: #333; transition: .4s;
}
.slider:before {
  position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px;
  background-color: white; transition: .4s;
}
input:checked + .slider { background-color: var(--accent); }
input:checked + .slider:before { transform: translateX(16px); }
.slider.round { border-radius: 34px; }
.slider.round:before { border-radius: 50%; }
</style>
