<template>
  <div class="plugins-page">
    <div class="page-header">
      <h1>{{ t("plugins.title") }}</h1>
      <div class="header-actions">
        <button class="install-btn" @click="showInstallModal = true">
          {{ $t("plugins.installFromUrl") }}
        </button>
        <router-link to="/market" class="market-btn">
          {{ t("plugins.browseMarket") }}
        </router-link>
        <button class="reload-btn" @click="handleReload">
          {{ t("plugins.reload") }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">{{ t("common.loading") }}</div>

    <div v-else-if="plugins.length === 0" class="empty-state">
      {{ t("plugins.empty") }}
    </div>

    <div v-else class="plugin-list">
      <div
        v-for="plugin in plugins"
        :key="plugin.plugin_id"
        class="plugin-card"
      >
        <div class="plugin-header">
          <h3>{{ plugin.name }}</h3>
          <span class="version">v{{ plugin.version }}</span>
        </div>

        <p class="description">{{ plugin.description }}</p>

        <div v-if="plugin.requires && plugin.requires.length" class="requires">
          <span class="label">{{ t("plugins.requires") }}:</span>
          <span v-for="req in plugin.requires" :key="req" class="tag req">{{ req }}</span>
        </div>

        <div v-if="plugin.tools.length" class="tools">
          <span class="label">{{ t("plugins.tools") }}:</span>
          <span v-for="tool in plugin.tools" :key="tool" class="tag">{{
            tool
          }}</span>
        </div>

        <button class="configure-btn" @click="openConfig(plugin)">
          {{ t("plugins.configure") }}
        </button>
      </div>
    </div>

    <!-- System Installed Plugins -->
    <section v-if="isAdmin && systemInstalled.length > 0" class="installed-section">
      <h2 class="section-title">{{ $t("plugins.systemInstalledSection") }}</h2>
      <div class="plugin-list">
        <div
          v-for="item in systemInstalled"
          :key="item.id"
          class="plugin-card installed-card"
        >
          <div class="plugin-header">
            <h3>{{ item.name }}</h3>
            <span class="installed-badge system-badge">{{ $t("plugins.badgeSystem") }}</span>
          </div>
          <p class="description">{{ item.type }}</p>
          <p class="description small">{{ item.install_url }}</p>
          <button class="delete-btn uninstall-btn" @click="uninstallInstalledPlugin(item.id)">
            {{ $t("plugins.uninstall") }}
          </button>
        </div>
      </div>
    </section>

    <!-- My Installed Plugins -->
    <section v-if="personalInstalled.length > 0" class="installed-section">
      <h2 class="section-title">{{ $t("plugins.personalInstalledSection") }}</h2>
      <div class="plugin-list">
        <div
          v-for="item in personalInstalled"
          :key="item.id"
          class="plugin-card installed-card"
        >
          <div class="plugin-header">
            <h3>{{ item.name }}</h3>
            <span class="installed-badge personal-badge">{{ $t("plugins.badgePersonal") }}</span>
          </div>
          <p class="description">{{ item.type }}</p>
          <p class="description small">{{ item.install_url }}</p>
          <button class="delete-btn uninstall-btn" @click="uninstallInstalledPlugin(item.id)">
            {{ $t("plugins.uninstall") }}
          </button>
        </div>
      </div>
    </section>

    <!-- Config modal -->
    <Teleport to="body">
      <div v-if="activePlugin" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <h2>
            {{ t("plugins.config_title", { name: activePlugin.name }) }}
          </h2>

          <div v-if="configLoading" class="loading">
            {{ t("common.loading") }}
          </div>

          <template v-else>
            <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
            
            <!-- Schema-based hints -->
            <div v-if="activePlugin.config_schema" class="schema-hints">
              <div v-for="(schema, key) in activePlugin.config_schema.properties" :key="key" class="hint-item">
                <code>{{ key }}</code>: {{ schema.description || t('plugins.noDescription') }}
                <span v-if="activePlugin.config_schema.required?.includes(key)" class="required-mark">*</span>
              </div>
            </div>

            <div class="config-list">
              <div
                v-for="(item, key) in currentConfig"
                :key="key"
                class="config-row"
              >
                <span class="config-key">{{ key }}</span>
                <span class="config-value">{{
                  item.is_secret ? "***" : item.value
                }}</span>
                <button class="delete-btn" @click="removeConfig(String(key))">
                  ✕
                </button>
              </div>
              <p
                v-if="Object.keys(currentConfig).length === 0"
                class="no-config"
              >
                {{ t("plugins.no_config") }}
              </p>
            </div>

            <div class="add-config-form">
              <div class="form-row">
                <input
                  v-model="newKey"
                  :placeholder="t('plugins.key_placeholder')"
                  list="schema-keys"
                />
                <datalist id="schema-keys">
                  <option v-for="(_, key) in activePlugin.config_schema?.properties" :key="key" :value="key" />
                </datalist>
              </div>
              <div class="form-row">
                <input
                  v-model="newValue"
                  :type="newIsSecret ? 'password' : 'text'"
                  :placeholder="t('plugins.value_placeholder')"
                />
              </div>
              <div class="form-footer">
                <label class="secret-label">
                  <input v-model="newIsSecret" type="checkbox" />
                  {{ t("plugins.secret") }}
                </label>
                <button
                  class="add-btn"
                  :disabled="!newKey.trim() || !newValue.trim()"
                  @click="addConfig"
                >
                  {{ t("plugins.add") }}
                </button>
              </div>
            </div>
          </template>

          <button class="close-btn" @click="closeModal">
            {{ t("common.close") }}
          </button>
        </div>
      </div>
    </Teleport>

    <InstallFromUrlModal
      v-if="showInstallModal"
      @close="showInstallModal = false"
      @installed="loadInstalled"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { pluginsApi, marketApi, type PluginInfo, type ConfigItem, type InstalledPluginOut } from "@/api/plugins";
import { useAuthStore } from "@/stores/auth";
import { useToast } from "@/composables/useToast";
import InstallFromUrlModal from "@/components/InstallFromUrlModal.vue";

const { t } = useI18n();
const { error: toastError } = useToast();

const auth = useAuthStore();
const isAdmin = computed(() => auth.isAdmin);

const systemInstalled = ref<InstalledPluginOut[]>([]);
const personalInstalled = ref<InstalledPluginOut[]>([]);

async function loadInstalled() {
  try {
    const { data } = await marketApi.listInstalled();
    systemInstalled.value = data.system;
    personalInstalled.value = data.personal;
  } catch {
    // Non-fatal: installed section just stays empty
  }
}

async function uninstallInstalledPlugin(id: string) {
  if (!confirm(t("plugins.uninstallConfirm"))) return;
  try {
    await marketApi.uninstall(id);
    await loadInstalled();
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
      ?.detail;
    toastError(typeof detail === "string" ? detail : t("plugins.uninstallError"));
  }
}

const plugins = ref<PluginInfo[]>([]);
const loading = ref(true);
const activePlugin = ref<PluginInfo | null>(null);
const currentConfig = ref<Record<string, ConfigItem>>({});
const configLoading = ref(false);
const newKey = ref("");
const newValue = ref("");
const newIsSecret = ref(false);
const errorMsg = ref("");
const showInstallModal = ref(false);

async function loadPlugins() {
  loading.value = true;
  try {
    const resp = await pluginsApi.list();
    plugins.value = resp.data;
  } catch {
    plugins.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void Promise.all([loadPlugins(), loadInstalled()]);
});

async function handleReload() {
  try {
    await pluginsApi.reload();
    await loadPlugins();
  } catch {
    errorMsg.value = t("plugins.reload_error");
  }
}

async function openConfig(plugin: PluginInfo) {
  activePlugin.value = plugin;
  configLoading.value = true;
  errorMsg.value = "";
  try {
    const resp = await pluginsApi.getConfig(plugin.plugin_id);
    currentConfig.value = resp.data;
  } catch {
    errorMsg.value = t("plugins.load_error");
    currentConfig.value = {};
  } finally {
    configLoading.value = false;
  }
}

function closeModal() {
  activePlugin.value = null;
  newKey.value = "";
  newValue.value = "";
  newIsSecret.value = false;
}

async function addConfig() {
  if (!activePlugin.value || !newKey.value.trim() || !newValue.value.trim())
    return;
  try {
    await pluginsApi.setConfig(
      activePlugin.value.plugin_id,
      newKey.value.trim(),
      newValue.value,
      newIsSecret.value,
    );
    await openConfig(activePlugin.value);
    newKey.value = "";
    newValue.value = "";
    newIsSecret.value = false;
  } catch {
    errorMsg.value = t("plugins.save_error");
  }
}

async function removeConfig(key: string) {
  if (!activePlugin.value) return;
  try {
    await pluginsApi.deleteConfig(activePlugin.value.plugin_id, key);
    await openConfig(activePlugin.value);
  } catch {
    errorMsg.value = t("plugins.delete_error");
  }
}
</script>

<style scoped>
.plugins-page {
  padding: 2rem;
  max-width: 960px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.install-btn {
  padding: 0.5rem 1rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
}
.install-btn:hover {
  background: #2563eb;
}
.reload-btn {
  padding: 0.5rem 1rem;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
}
.reload-btn:hover {
  background: #059669;
}
.plugin-list {
  display: grid;
  gap: 1rem;
}
.plugin-card {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  padding: 1.5rem;
  background: white;
}
.plugin-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}
.plugin-header h3 {
  margin: 0;
  font-size: 1.1rem;
}
.version {
  color: #6b7280;
  font-size: 0.875rem;
}
.description {
  color: #4b5563;
  margin: 0.25rem 0 0.75rem;
}
.requires {
  margin-bottom: 0.5rem;
}
.tools {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  align-items: center;
  margin-bottom: 1rem;
}
.label {
  font-size: 0.75rem;
  color: #6b7280;
  margin-right: 0.25rem;
}
.tag {
  background: #f3f4f6;
  border-radius: 4px;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
}
.tag.req {
  background: #fef3c7;
  color: #92400e;
}
.configure-btn {
  padding: 0.375rem 1rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  background: white;
}
.configure-btn:hover {
  background: #f9fafb;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  width: 520px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
}
.modal h2 {
  margin: 0 0 1.5rem;
  font-size: 1.1rem;
}
.schema-hints {
  background: #f9fafb;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  font-size: 0.8125rem;
}
.hint-item {
  margin-bottom: 0.25rem;
  color: #4b5563;
}
.hint-item code {
  background: #e5e7eb;
  padding: 0.125rem 0.25rem;
  border-radius: 4px;
  font-family: monospace;
}
.required-mark {
  color: #ef4444;
  margin-left: 0.125rem;
}
.config-list {
  border: 1px solid #f3f4f6;
  border-radius: 6px;
  margin-bottom: 1rem;
}
.config-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #f3f4f6;
}
.config-row:last-child {
  border-bottom: none;
}
.config-key {
  font-weight: 500;
  flex: 1;
}
.config-value {
  color: #6b7280;
  flex: 2;
  font-family: monospace;
}
.delete-btn {
  background: none;
  border: none;
  color: #ef4444;
  cursor: pointer;
  padding: 0.25rem;
}
.no-config {
  color: #9ca3af;
  text-align: center;
  padding: 1rem;
  margin: 0;
}
.add-config-form {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.form-row {
  margin-bottom: 0.75rem;
}
.form-row input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.875rem;
}
.form-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.secret-label {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  cursor: pointer;
}
.add-btn {
  padding: 0.375rem 1rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
}
.add-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.close-btn {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  background: white;
}
.error-msg {
  color: #ef4444;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}
.market-btn {
  padding: 0.5rem 1rem;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  text-decoration: none;
  display: inline-block;
}
.market-btn:hover {
  background: #4f46e5;
}
.installed-section {
  margin-top: 2.5rem;
}
.section-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #374151;
}
.installed-card {
  position: relative;
}
.installed-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.system-badge {
  background: #dbeafe;
  color: #1e40af;
}
.personal-badge {
  background: #dcfce7;
  color: #166534;
}
.description.small {
  font-size: 0.75rem;
  word-break: break-all;
}
.uninstall-btn {
  margin-top: 0.5rem;
  padding: 0.25rem 0.75rem;
  background: none;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #ef4444;
  cursor: pointer;
  font-size: 0.8125rem;
}
.uninstall-btn:hover {
  background: #fef2f2;
}
</style>
