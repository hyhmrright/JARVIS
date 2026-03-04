<template>
  <div class="page-container">
    <PageHeader :title="$t('admin.title')">
      <template #actions>
        <button v-if="currentTab === 'plugins'" class="btn-accent" @click="showAddModal = true">
          + {{ $t('admin.plugins.install') }}
        </button>
      </template>
    </PageHeader>

    <div class="page-content custom-scrollbar">
      <nav class="tab-nav">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="{ active: currentTab === tab.id }"
          @click="currentTab = tab.id"
        >
          {{ $t(`admin.tabs.${tab.id}`) }}
        </button>
      </nav>

      <!-- Users Tab -->
      <section v-if="currentTab === 'users'" class="tab-panel animate-fade-in">
        <div class="table-card">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ $t('admin.users.email') }}</th>
                <th>{{ $t('admin.users.name') }}</th>
                <th>{{ $t('admin.users.role') }}</th>
                <th>{{ $t('admin.users.status') }}</th>
                <th>{{ $t('admin.users.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td class="email-cell">{{ user.email }}</td>
                <td>{{ user.display_name || '-' }}</td>
                <td>
                  <select
                    class="role-select"
                    :value="user.role"
                    @change="handleRoleChange(user.id, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="superadmin">Superadmin</option>
                  </select>
                </td>
                <td>
                  <span :class="['badge', user.is_active ? 'success' : 'danger']">
                    {{ user.is_active ? $t('admin.users.active') : $t('admin.users.disabled') }}
                  </span>
                </td>
                <td>
                  <button class="btn-ghost" @click="toggleUserStatus(user)">
                    {{ user.is_active ? $t('admin.users.disable') : $t('admin.users.enable') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pagination">
          <button class="btn-nav" :disabled="page === 1" @click="page--">←</button>
          <span class="page-info">{{ page }} / {{ Math.ceil(totalUsers / limit) }}</span>
          <button class="btn-nav" :disabled="page * limit >= totalUsers" @click="page++">→</button>
        </div>
      </section>

      <!-- Plugins Tab -->
      <section v-if="currentTab === 'plugins'" class="tab-panel animate-fade-in">
        <div class="grid-layout">
          <div v-for="plugin in plugins" :key="plugin.id" class="glass-card plugin-card">
            <div class="plugin-main">
              <div class="plugin-header">
                <h3>{{ plugin.name }}</h3>
                <span class="version-tag">v{{ plugin.version }}</span>
              </div>
              <p class="plugin-desc">{{ plugin.description }}</p>
              <div class="plugin-stats">
                <span class="stat-pill">{{ plugin.tools.length }} tools</span>
              </div>
            </div>
            <div class="plugin-ctrl">
              <label class="switch">
                <input type="checkbox" checked @change="togglePlugin(plugin.id, ($event.target as HTMLInputElement).checked)" />
                <span class="slider round"></span>
              </label>
            </div>
          </div>
        </div>
      </section>

      <!-- Stats Tab -->
      <section v-if="currentTab === 'stats'" class="tab-panel animate-fade-in">
        <div v-if="stats" class="grid-layout stats-grid">
          <div class="glass-card stat-item">
            <label>{{ $t('admin.stats.users') }}</label>
            <div class="value">{{ stats.user_count }}</div>
          </div>
          <div class="glass-card stat-item">
            <label>{{ $t('admin.stats.conversations') }}</label>
            <div class="value">{{ stats.conversation_count }}</div>
          </div>
          <div class="glass-card stat-item">
            <label>{{ $t('admin.stats.messages') }}</label>
            <div class="value">{{ stats.message_count }}</div>
          </div>
          <div class="glass-card stat-item featured">
            <label>{{ $t('admin.stats.tokens') }}</label>
            <div class="value">{{ (stats.total_tokens_input + stats.total_tokens_output).toLocaleString() }}</div>
            <div class="sub-value">
              In: {{ stats.total_tokens_input.toLocaleString() }} · Out: {{ stats.total_tokens_output.toLocaleString() }}
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Modal -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal-content glass-card animate-zoom-in">
        <div class="modal-header">
          <h3>{{ $t('admin.plugins.installTitle') }}</h3>
          <button class="btn-close" @click="showAddModal = false">×</button>
        </div>
        <p class="modal-desc">{{ $t('admin.plugins.installDesc') }}</p>
        <input
          v-model="installUrl"
          type="text"
          placeholder="https://github.com/..."
          class="modern-input"
        />
        <div class="modal-footer">
          <button class="btn-ghost" @click="showAddModal = false">{{ $t('common.cancel') }}</button>
          <button class="btn-accent" :disabled="!installUrl" @click="handleInstall">
            {{ $t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import adminApi, { AdminUser, SystemStats } from '@/api/admin';
import PageHeader from '@/components/PageHeader.vue';

interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  tools: unknown[];
}

const tabs = [
  { id: 'users', label: 'Users' },
  { id: 'plugins', label: 'Plugins' },
  { id: 'stats', label: 'Stats' },
];

const currentTab = ref('users');
const users = ref<AdminUser[]>([]);
const totalUsers = ref(0);
const page = ref(1);
const limit = 20;
const plugins = ref<PluginInfo[]>([]);
const stats = ref<SystemStats | null>(null);
const showAddModal = ref(false);
const installUrl = ref('');

const fetchUsers = async () => {
  const data = await adminApi.getUsers(page.value, limit);
  users.value = data.users;
  totalUsers.value = data.total;
};

const fetchPlugins = async () => { plugins.value = await adminApi.getPlugins(); };
const fetchStats = async () => { stats.value = await adminApi.getStats(); };

const handleRoleChange = async (userId: string, role: string) => {
  try {
    await adminApi.updateUser(userId, { role });
    await fetchUsers();
  } catch (err) { console.error(err); }
};

const toggleUserStatus = async (user: AdminUser) => {
  try {
    await adminApi.updateUser(user.id, { is_active: !user.is_active });
    await fetchUsers();
  } catch (err) { console.error(err); }
};

const togglePlugin = async (pluginId: string, enable: boolean) => {
  try { await adminApi.enablePlugin(pluginId, enable); } catch (err) { console.error(err); }
};

const handleInstall = async () => {
  try {
    await adminApi.installPlugin(installUrl.value);
    showAddModal.value = false;
    installUrl.value = '';
    await fetchPlugins();
  } catch { alert('Failed to install plugin'); }
};

watch(currentTab, (newTab) => {
  if (newTab === 'users') fetchUsers();
  if (newTab === 'plugins') fetchPlugins();
  if (newTab === 'stats') fetchStats();
});
watch(page, fetchUsers);
onMounted(fetchUsers);
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
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}

.tab-nav {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 1rem;
}

.tab-nav button {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 1rem;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.tab-nav button.active {
  color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
  font-weight: 600;
}

/* ── Table Card ── */
.table-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.data-table th {
  background: rgba(255,255,255,0.02);
  padding: 1rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 1px;
}

.data-table td {
  padding: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.9rem;
}

.email-cell { font-weight: 500; color: var(--text-primary); }

.role-select {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 0.3rem 0.6rem;
  border-radius: 4px;
  outline: none;
}

.badge {
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 600;
}
.badge.success { background: rgba(76, 175, 80, 0.1); color: #4caf50; }
.badge.danger { background: rgba(244, 67, 54, 0.1); color: #f44336; }

/* ── Grid Layout ── */
.grid-layout {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.glass-card {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 1.5rem;
  transition: transform 0.2s;
}

.plugin-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.plugin-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.version-tag {
  font-size: 0.7rem;
  color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
}

.plugin-desc {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 1rem;
}

.stat-pill {
  font-size: 0.75rem;
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: 10px;
}

/* ── Stats ── */
.stats-grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.stat-item label { color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; }
.stat-item .value { font-size: 2rem; font-weight: 800; margin: 0.5rem 0; }
.stat-item.featured { border-color: var(--accent); grid-column: span 2; }
.stat-item.featured .value { color: var(--accent); }

/* ── Buttons ── */
.btn-accent {
  background: var(--accent);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: var(--radius-full);
  font-weight: 600;
  cursor: pointer;
}

.btn-ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
}

.btn-ghost:hover { border-color: var(--accent); color: var(--text-primary); }

.pagination {
  margin-top: 2rem;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1.5rem;
}

.btn-nav {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
}

.btn-nav:disabled { opacity: 0.3; cursor: not-allowed; }

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}

.modal-content {
  width: 100%;
  max-width: 500px;
  position: relative;
}

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 1.5rem;
}

.btn-close {
  background: none; border: none; font-size: 1.5rem; color: var(--text-muted); cursor: pointer;
}

.modern-input {
  width: 100%;
  padding: 0.8rem 1rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-bright);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  margin: 1rem 0;
  outline: none;
}

.modern-input:focus { border-color: var(--accent); }

.modal-footer { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem; }

.animate-fade-in { animation: fadeIn 0.3s ease; }
.animate-zoom-in { animation: zoomIn 0.2s ease; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes zoomIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
</style>
