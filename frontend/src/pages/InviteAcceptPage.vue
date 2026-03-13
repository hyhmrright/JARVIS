<template>
  <div class="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div v-if="loading" class="text-center text-zinc-400">
        {{ $t("common.loading") }}
      </div>
      <div
        v-else-if="error"
        class="bg-zinc-900 border border-red-800/50 rounded-2xl p-8 text-center"
      >
        <p class="text-red-400">{{ error }}</p>
        <button
          class="mt-4 px-6 py-2 bg-white text-black text-sm font-semibold rounded-lg"
          @click="$router.push('/')"
        >
          {{ $t("common.backToChat") }}
        </button>
      </div>
      <div v-else-if="invitation" class="bg-zinc-900 border border-zinc-800 rounded-2xl p-8">
        <h1 class="text-xl font-bold text-white mb-2">{{ $t("workspace.inviteTitle") }}</h1>
        <p class="text-zinc-400 mb-6">
          {{
            $t("workspace.inviteDesc", {
              workspace: invitation.workspace_name,
              role: invitation.role,
            })
          }}
        </p>
        <div v-if="!auth.isLoggedIn" class="space-y-3">
          <p class="text-sm text-zinc-500">{{ $t("workspace.inviteLoginRequired") }}</p>
          <button
            class="w-full py-2.5 bg-white text-black font-semibold rounded-lg hover:bg-zinc-200 transition-colors"
            @click="$router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)"
          >
            {{ $t("login.submit") }}
          </button>
        </div>
        <div v-else>
          <button
            class="w-full py-2.5 bg-white text-black font-semibold rounded-lg hover:bg-zinc-200 transition-colors disabled:opacity-50"
            :disabled="accepting"
            @click="accept"
          >
            {{ accepting ? $t("common.loading") : $t("workspace.acceptInvite") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import client from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const auth = useAuthStore();
const workspace = useWorkspaceStore();

interface InvitationInfo {
  workspace_name: string;
  role: string;
  workspace_id: string;
}

const token = route.params.token as string;
const loading = ref(true);
const accepting = ref(false);
const error = ref<string | null>(null);
const invitation = ref<InvitationInfo | null>(null);

onMounted(async () => {
  try {
    const { data } = await client.get(`/invitations/${token}`);
    invitation.value = data;
  } catch (e: unknown) {
    error.value =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      t("workspace.inviteInvalid");
  } finally {
    loading.value = false;
  }
});

async function accept() {
  accepting.value = true;
  try {
    const { data } = await client.post(`/invitations/${token}/accept`);
    await workspace.fetchOrganization();
    await workspace.fetchWorkspaces();
    workspace.switchWorkspace(data.workspace_id);
    router.push("/");
  } catch (e: unknown) {
    error.value =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      t("workspace.inviteAcceptError");
  } finally {
    accepting.value = false;
  }
}
</script>
