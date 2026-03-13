import { defineStore } from "pinia";
import client from "@/api/client";

interface Workspace {
  id: string;
  name: string;
  organization_id: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

interface Organization {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  created_at: string;
}

interface WorkspaceMember {
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: string;
  joined_at: string;
}

export const useWorkspaceStore = defineStore("workspace", {
  state: () => ({
    organization: null as Organization | null,
    workspaces: [] as Workspace[],
    currentWorkspaceId: localStorage.getItem("currentWorkspaceId") as string | null,
    members: [] as WorkspaceMember[],
  }),
  getters: {
    currentWorkspace: (s): Workspace | null =>
      s.workspaces.find((w) => w.id === s.currentWorkspaceId) ?? null,
    hasOrganization: (s) => !!s.organization,
  },
  actions: {
    async fetchOrganization() {
      try {
        const { data } = await client.get("/organizations/me");
        this.organization = data;
      } catch {
        this.organization = null;
      }
    },
    async fetchWorkspaces() {
      try {
        const { data } = await client.get("/workspaces");
        this.workspaces = data;
        if (
          this.currentWorkspaceId &&
          !this.workspaces.find((w) => w.id === this.currentWorkspaceId)
        ) {
          this.switchWorkspace(null);
        }
      } catch {
        this.workspaces = [];
      }
    },
    switchWorkspace(id: string | null) {
      this.currentWorkspaceId = id;
      if (id) {
        localStorage.setItem("currentWorkspaceId", id);
      } else {
        localStorage.removeItem("currentWorkspaceId");
      }
    },
    async createOrganization(name: string, slug: string) {
      const { data } = await client.post("/organizations", { name, slug });
      this.organization = data;
      return data;
    },
    async createWorkspace(name: string) {
      const { data } = await client.post("/workspaces", { name });
      this.workspaces.push(data);
      return data;
    },
    async fetchMembers(workspaceId: string) {
      this.members = [];
      try {
        const { data } = await client.get(`/workspaces/${workspaceId}/members`);
        this.members = data;
      } catch {
        // members stays empty on network failure
      }
    },
    async inviteMember(workspaceId: string, email: string, role: string) {
      const { data } = await client.post(
        `/workspaces/${workspaceId}/members/invite`,
        { email, role }
      );
      return data;
    },
    async removeMember(workspaceId: string, userId: string) {
      await client.delete(`/workspaces/${workspaceId}/members/${userId}`);
      this.members = this.members.filter((m) => m.user_id !== userId);
    },
    async updateMemberRole(workspaceId: string, userId: string, role: string) {
      await client.put(`/workspaces/${workspaceId}/members/${userId}`, { role });
      const m = this.members.find((m) => m.user_id === userId);
      if (m) m.role = role;
    },
  },
});
