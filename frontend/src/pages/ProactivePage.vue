<template>
  <div class="proactive-page">
    <header class="page-header">
      <h1>{{ $t('proactive.title') }}</h1>
      <button class="btn-primary" @click="showAddModal = true">
        + {{ $t('proactive.addTask') }}
      </button>
    </header>

    <main class="jobs-list">
      <div v-if="jobs.length === 0" class="empty-state">
        <p>{{ $t('proactive.noTasks') }}</p>
      </div>

      <div v-for="job in jobs" :key="job.id" class="job-card">
        <div class="job-info">
          <div class="job-header">
            <span :class="['type-badge', job.trigger_type]">
              {{ job.trigger_type.toUpperCase() }}
            </span>
            <span class="schedule">{{ job.schedule }}</span>
          </div>
          <h3>{{ job.task }}</h3>
          <div v-if="job.trigger_metadata" class="job-meta">
            <code v-if="job.trigger_type === 'web_watcher'">{{ job.trigger_metadata.url }}</code>
            <code v-if="job.trigger_type === 'email'">{{ job.trigger_metadata.imap_user }}</code>
          </div>
          <div class="last-run">
            {{ $t('proactive.lastRun') }}: {{ job.last_run_at ? new Date(job.last_run_at).toLocaleString() : '-' }}
          </div>
        </div>
        
        <div class="job-actions">
          <label class="switch">
            <input
              type="checkbox"
              :checked="job.is_active"
              @change="toggleJob(job.id)"
            />
            <span class="slider round"></span>
          </label>
          <button class="btn-delete" @click="deleteJob(job.id)">🗑</button>
        </div>
      </div>
    </main>

    <!-- Add Task Modal -->
    <div v-if="showAddModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ $t('proactive.addTask') }}</h3>
        
        <div class="form-group">
          <label>{{ $t('proactive.taskPrompt') }}</label>
          <textarea v-model="newJob.task" placeholder="e.g. Check for new Apple news and summarize"></textarea>
        </div>

        <div class="form-group">
          <label>{{ $t('proactive.schedule') }} (Cron)</label>
          <input v-model="newJob.schedule" placeholder="*/30 * * * * (Every 30m)" />
        </div>

        <div class="form-group">
          <label>{{ $t('proactive.triggerType') }}</label>
          <select v-model="newJob.trigger_type">
            <option value="cron">Cron (Always fire)</option>
            <option value="web_watcher">Web Watcher (Content change)</option>
            <option value="email">Email (New unread)</option>
          </select>
        </div>

        <div v-if="newJob.trigger_type === 'web_watcher'" class="form-group">
          <label>URL to watch</label>
          <input v-model="newJob.trigger_metadata.url" placeholder="https://..." />
        </div>

        <div v-if="newJob.trigger_type === 'email'" class="form-group">
          <label>IMAP Host</label>
          <input v-model="newJob.trigger_metadata.imap_host" />
          <label>Email</label>
          <input v-model="newJob.trigger_metadata.imap_user" />
          <label>Password (App Password)</label>
          <input type="password" v-model="newJob.trigger_metadata.imap_password" />
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="showAddModal = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="saveJob">{{ $t('common.confirm') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import client from '@/api/client';

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
.proactive-page {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.job-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.job-header {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.5rem;
}

.type-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: #eee;
  color: #666;
}

.type-badge.web_watcher { background: #e0f2fe; color: #0369a1; }
.type-badge.email { background: #fef3c7; color: #92400e; }

.schedule { font-size: 0.8rem; color: var(--text-muted); }

.job-meta {
  margin: 0.5rem 0;
  font-size: 0.85rem;
  opacity: 0.8;
}

.last-run {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}

.job-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.btn-delete {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
}

.btn-delete:hover { opacity: 1; color: var(--danger); }

/* Form styling */
.form-group {
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-group label { font-size: 0.9rem; font-weight: 600; }
.form-group textarea, .form-group input, .form-group select {
  padding: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
}

/* Modal from previous Admin Page applies or redefine if needed */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--bg-secondary);
  padding: 2rem; border-radius: 12px;
  width: 100%; max-width: 500px;
}
.modal-footer {
  margin-top: 1.5rem;
  display: flex; justify-content: flex-end; gap: 1rem;
}
</style>
