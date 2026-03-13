<template>
  <div class="h-screen flex flex-col bg-zinc-950 font-sans text-zinc-200">
    <PageHeader :title="$t('workspace.members')" />
    <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
      <div class="max-w-3xl mx-auto space-y-8">
        <!-- No org state -->
        <div
          v-if="!workspace.hasOrganization"
          class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-8 text-center"
        >
          <p class="text-zinc-400 mb-6">{{ $t("workspace.noOrgDesc") }}</p>
          <form class="space-y-4 max-w-sm mx-auto" @submit.prevent="createOrg">
            <input
              v-model="orgName"
              class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
              :placeholder="$t('workspace.orgName')"
              required
            />
            <input
              v-model="orgSlug"
              class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
              :placeholder="$t('workspace.orgSlug')"
              required
              pattern="[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]"
            />
            <button
              type="submit"
              class="w-full py-2.5 bg-white text-black text-sm font-semibold rounded-lg hover:bg-zinc-200 transition-colors"
            >
              {{ $t("workspace.createOrg") }}
            </button>
          </form>
        </div>

        <template v-else>
          <!-- Workspace selector -->
          <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase">
                {{ $t("workspace.title") }}
              </h3>
              <button
                class="text-xs text-zinc-400 hover:text-white transition-colors"
                @click="showCreateWs = !showCreateWs"
              >
                + {{ $t("workspace.createWorkspace") }}
              </button>
            </div>
            <div v-if="showCreateWs" class="flex gap-2 mb-4">
              <input
                v-model="newWsName"
                class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm outline-none focus:border-zinc-600"
                :placeholder="$t('workspace.workspaceName')"
              />
              <button
                class="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors"
                @click="createWs"
              >
                {{ $t("common.confirm") }}
              </button>
            </div>
            <div class="space-y-2">
              <button
                v-for="ws in workspace.workspaces"
                :key="ws.id"
                class="w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-colors"
                :class="
                  selectedWsId === ws.id
                    ? 'border-zinc-500 bg-zinc-800'
                    : 'border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900'
                "
                @click="selectedWsId = ws.id; inviteLink = null; loadMembers(ws.id)"
              >
                <span class="text-sm font-medium">{{ ws.name }}</span>
                <span class="text-xs text-zinc-500">{{ ws.id.slice(0, 8) }}...</span>
              </button>
            </div>
          </section>

          <!-- Members list + invite -->
          <section
            v-if="selectedWsId"
            class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6"
          >
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase">
                {{ $t("workspace.membersList") }}
              </h3>
            </div>
            <form class="flex gap-2 mb-6" @submit.prevent="invite">
              <input
                v-model="inviteEmail"
                type="email"
                class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-sm outline-none focus:border-zinc-600"
                :placeholder="$t('workspace.inviteEmail')"
                required
              />
              <select
                v-model="inviteRole"
                class="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm outline-none"
              >
                <option value="member">{{ $t("workspace.roleMember") }}</option>
                <option value="admin">{{ $t("workspace.roleAdmin") }}</option>
              </select>
              <button
                type="submit"
                class="px-4 py-2 bg-white text-black text-sm font-semibold rounded-lg hover:bg-zinc-200 transition-colors"
              >
                {{ $t("workspace.invite") }}
              </button>
            </form>
            <div
              v-if="inviteLink"
              class="mb-4 p-3 bg-zinc-800 rounded-lg text-xs text-zinc-300 break-all"
            >
              {{ $t("workspace.inviteLink") }}: {{ inviteLink }}
            </div>
            <div class="space-y-2">
              <div
                v-for="m in workspace.members"
                :key="m.user_id"
                class="flex items-center justify-between px-4 py-3 rounded-xl bg-zinc-900 border border-zinc-800"
              >
                <div>
                  <p class="text-sm font-medium">{{ m.display_name || m.email }}</p>
                  <p class="text-xs text-zinc-500">{{ m.email }}</p>
                </div>
                <div class="flex items-center gap-3">
                  <select
                    :value="m.role"
                    class="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1 text-xs"
                    @change="(e) => changeRole(m.user_id, (e.target as HTMLSelectElement).value)"
                  >
                    <option value="member">{{ $t("workspace.roleMember") }}</option>
                    <option value="admin">{{ $t("workspace.roleAdmin") }}</option>
                  </select>
                  <button
                    class="text-xs text-red-400 hover:text-red-300 transition-colors"
                    @click="removeMember(m.user_id)"
                  >
                    {{ $t("workspace.remove") }}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useWorkspaceStore } from "@/stores/workspace";
import PageHeader from "@/components/PageHeader.vue";

const { t } = useI18n();
const workspace = useWorkspaceStore();

const orgName = ref("");
const orgSlug = ref("");
const newWsName = ref("");
const showCreateWs = ref(false);
const selectedWsId = ref<string | null>(null);
const inviteEmail = ref("");
const inviteRole = ref("member");
const inviteLink = ref<string | null>(null);

async function createOrg() {
  try {
    await workspace.createOrganization(orgName.value, orgSlug.value);
    orgName.value = "";
    orgSlug.value = "";
    await workspace.fetchWorkspaces();
  } catch (err: unknown) {
    console.error("Failed to create organization", err);
  }
}

async function createWs() {
  if (!newWsName.value.trim()) return;
  try {
    await workspace.createWorkspace(newWsName.value.trim());
    newWsName.value = "";
    showCreateWs.value = false;
  } catch (err: unknown) {
    console.error("Failed to create workspace", err);
  }
}

async function loadMembers(wsId: string) {
  try {
    await workspace.fetchMembers(wsId);
  } catch (err: unknown) {
    console.error("Failed to load members", err);
  }
}

async function invite() {
  if (!selectedWsId.value) return;
  try {
    const result = await workspace.inviteMember(
      selectedWsId.value,
      inviteEmail.value,
      inviteRole.value
    );
    inviteLink.value = result.token
      ? `${window.location.origin}/invite/${result.token}`
      : null;
    inviteEmail.value = "";
    inviteRole.value = "member";
    await loadMembers(selectedWsId.value);
  } catch (err: unknown) {
    console.error("Failed to invite member", err);
  }
}

async function changeRole(userId: string, role: string) {
  if (!selectedWsId.value) return;
  try {
    await workspace.updateMemberRole(selectedWsId.value, userId, role);
  } catch (err: unknown) {
    console.error("Failed to update member role", err);
  }
}

async function removeMember(userId: string) {
  if (!selectedWsId.value) return;
  if (!confirm(t("workspace.removeConfirm"))) return;
  try {
    await workspace.removeMember(selectedWsId.value, userId);
  } catch (err: unknown) {
    console.error("Failed to remove member", err);
  }
}

onMounted(async () => {
  await workspace.fetchOrganization();
  await workspace.fetchWorkspaces();
});
</script>
