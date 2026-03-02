<template>
  <div class="admin-page">
    <header class="admin-header">
      <h1>{{ $t('admin.title') }}</h1>
      <nav class="admin-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="{ active: currentTab === tab.id }"
          @click="currentTab = tab.id"
        >
          {{ $t(`admin.tabs.${tab.id}`) }}
        </button>
      </nav>
    </header>

    <main class="admin-content">
      <!-- Users Tab -->
      <section v-if="currentTab === 'users'" class="tab-panel">
        <div class="table-container">
          <table class="admin-table">
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
                <td>{{ user.email }}</td>
                <td>{{ user.display_name || '-' }}</td>
                <td>
                  <select
                    :value="user.role"
                    @change="handleRoleChange(user.id, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="superadmin">Superadmin</option>
                  </select>
                </td>
                <td>
                  <span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
                    {{ user.is_active ? $t('admin.users.active') : $t('admin.users.disabled') }}
                  </span>
                </td>
                <td>
                  <button class="btn-toggle" @click="toggleUserStatus(user)">
                    {{ user.is_active ? $t('admin.users.disable') : $t('admin.users.enable') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pagination">
          <button :disabled="page === 1" @click="page--">{{ $t('common.prev') }}</button>
          <span>{{ page }} / {{ Math.ceil(totalUsers / limit) }}</span>
          <button :disabled="page * limit >= totalUsers" @click="page++">{{ $t('common.next') }}</button>
        </div>
      </section>

      <!-- Plugins Tab -->
      <section v-if="currentTab === 'plugins'" class="tab-panel">
        <div class="tab-actions">
          <button class="btn-primary" @click="showInstallModal = true">
            + {{ $t('admin.plugins.install') }}
          </button>
        </div>
        <div class="plugin-grid">
          <div v-for="plugin in plugins" :key="plugin.id" class="plugin-card">
            <div class="plugin-info">
              <h3>{{ plugin.name }} <span class="version">v{{ plugin.version }}</span></h3>
              <p>{{ plugin.description }}</p>
              <div class="plugin-meta">
                <span>{{ $t('admin.plugins.tools') }}: {{ plugin.tools.length }}</span>
              </div>
            </div>
            <div class="plugin-actions">
              <label class="switch">
                <input
                  type="checkbox"
                  checked
                  @change="togglePlugin(plugin.id, ($event.target as HTMLInputElement).checked)"
                />
                <span class="slider round"></span>
              </label>
            </div>
          </div>
        </div>
      </section>

      <!-- Stats Tab -->
      <section v-if="currentTab === 'stats'" class="tab-panel">
        <div v-if="stats" class="stats-grid">
          <div class="stat-card">
            <h4>{{ $t('admin.stats.users') }}</h4>
            <div class="stat-value">{{ stats.user_count }}</div>
          </div>
          <div class="stat-card">
            <h4>{{ $t('admin.stats.conversations') }}</h4>
            <div class="stat-value">{{ stats.conversation_count }}</div>
          </div>
          <div class="stat-card">
            <h4>{{ $t('admin.stats.messages') }}</h4>
            <div class="stat-value">{{ stats.message_count }}</div>
          </div>
          <div class="stat-card">
            <h4>{{ $t('admin.stats.tokens') }}</h4>
            <div class="stat-value">
              {{ (stats.total_tokens_input + stats.total_tokens_output).toLocaleString() }}
            </div>
            <small>In: {{ stats.total_tokens_input.toLocaleString() }} | Out: {{ stats.total_tokens_output.toLocaleString() }}</small>
          </div>
        </div>
      </section>
    </main>

    <!-- Install Modal -->
    <div v-if="showInstallModal" class="modal-overlay">
      <div class="modal-content">
        <h3>{{ $t('admin.plugins.installTitle') }}</h3>
        <p>{{ $t('admin.plugins.installDesc') }}</p>
        <input
          v-model="installUrl"
          type="text"
          placeholder="https://github.com/.../plugin.py"
          class="modal-input"
        />
        <div class="modal-footer">
          <button class="btn-secondary" @click="showInstallModal = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!installUrl" @click="handleInstall">
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

const plugins = ref<any[]>([]);
const stats = ref<SystemStats | null>(null);

const showInstallModal = ref(false);
const installUrl = ref('');

const fetchUsers = async () => {
  const data = await adminApi.getUsers(page.value, limit);
  users.value = data.users;
  totalUsers.value = data.total;
};

const fetchPlugins = async () => {
  plugins.value = await adminApi.getPlugins();
};

const fetchStats = async () => {
  stats.value = await adminApi.getStats();
};

const handleRoleChange = async (userId: string, role: string) => {
  try {
    await adminApi.updateUser(userId, { role });
    await fetchUsers();
  } catch (err) {
    console.error('Failed to change role:', err);
  }
};

const toggleUserStatus = async (user: AdminUser) => {
  try {
    await adminApi.updateUser(user.id, { is_active: !user.is_active });
    await fetchUsers();
  } catch (err) {
    console.error('Failed to toggle status:', err);
  }
};

const togglePlugin = async (pluginId: string, enable: boolean) => {
  try {
    await adminApi.enablePlugin(pluginId, enable);
  } catch (err) {
    console.error('Failed to toggle plugin:', err);
  }
};

const handleInstall = async () => {
  try {
    await adminApi.installPlugin(installUrl.value);
    showInstallModal.value = false;
    installUrl.value = '';
    await fetchPlugins();
  } catch (err) {
    alert('Failed to install plugin');
  }
};

watch(currentTab, (newTab) => {
  if (newTab === 'users') fetchUsers();
  if (newTab === 'plugins') fetchPlugins();
  if (newTab === 'stats') fetchStats();
});

watch(page, fetchUsers);

onMounted(() => {
  fetchUsers();
});
</script>

<style scoped>
.admin-page {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.admin-header {
  margin-bottom: 2rem;
}

.admin-tabs {
  display: flex;
  gap: 1rem;
  border-bottom: 1px solid #ddd;
  padding-bottom: 1rem;
}

.admin-tabs button {
  padding: 0.5rem 1rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 1rem;
  color: #666;
}

.admin-tabs button.active {
  color: #2c3e50;
  font-weight: bold;
  border-bottom: 2px solid #2c3e50;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.admin-table th, .admin-table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.status-badge.active {
  background: #e6fffa;
  color: #38a169;
}

.status-badge.inactive {
  background: #fff5f5;
  color: #e53e3e;
}

.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-top: 1rem;
}

.plugin-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.5rem;
}

.stat-card {
  background: #f8fafc;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  margin: 0.5rem 0;
}

.tab-actions {
  margin-bottom: 1.5rem;
  display: flex;
  justify-content: flex-end;
}

.btn-primary {
  background: #2c3e50;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 500px;
}

.modal-input {
  width: 100%;
  padding: 0.75rem;
  margin: 1rem 0;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.btn-secondary {
  background: #eee;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

/* Switch styling */
.switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .4s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .4s;
}

input:checked + .slider {
  background-color: #2c3e50;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.slider.round {
  border-radius: 34px;
}

.slider.round:before {
  border-radius: 50%;
}
</style>
