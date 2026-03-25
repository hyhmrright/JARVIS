import { defineStore } from "pinia";
import client from "@/api/client";

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  action_url?: string | null;
  created_at: string;
  metadata_json: Record<string, any>;
}

export const useNotificationStore = defineStore("notification", {
  state: () => ({
    notifications: [] as Notification[],
    unreadCount: 0,
    loading: false,
    pollInterval: null as ReturnType<typeof setInterval> | null,
  }),

  actions: {
    async fetchNotifications(includeRead = false) {
      this.loading = true;
      try {
        const { data } = await client.get<Notification[]>(`/notifications?include_read=${includeRead}`);
        this.notifications = data;
        await this.fetchUnreadCount();
      } catch (err) {
        console.error("[notification] fetch failed", err);
      } finally {
        this.loading = false;
      }
    },

    async fetchUnreadCount() {
      try {
        const { data } = await client.get<{ count: number }>("/notifications/unread-count");
        this.unreadCount = data.count;
      } catch (err) {
        console.error("[notification] fetch count failed", err);
      }
    },

    async markAsRead(id: string) {
      try {
        await client.patch(`/notifications/${id}/read`);
        const n = this.notifications.find((notif) => notif.id === id);
        if (n && !n.is_read) {
          n.is_read = true;
          this.unreadCount = Math.max(0, this.unreadCount - 1);
        }
      } catch (err) {
        console.error("[notification] markAsRead failed", err);
      }
    },

    async markAllRead() {
      try {
        await client.post("/notifications/mark-all-read");
        this.notifications.forEach((n) => (n.is_read = true));
        this.unreadCount = 0;
      } catch (err) {
        console.error("[notification] markAllRead failed", err);
      }
    },

    startPolling(intervalMs = 30000) {
      if (this.pollInterval) return;
      this.fetchUnreadCount();
      this.pollInterval = setInterval(() => {
        this.fetchUnreadCount();
      }, intervalMs);
    },

    stopPolling() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }
    },
  },
});
