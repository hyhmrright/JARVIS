import { ref } from 'vue';

export interface Toast {
  id: number;
  type: 'success' | 'error' | 'info';
  message: string;
}

const toasts = ref<Toast[]>([]);
let toastId = 0;

function show(message: string, type: Toast['type'] = 'info', duration = 3000): void {
  const id = ++toastId;
  toasts.value.push({ id, type, message });
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id);
  }, duration);
}

export function useToast() {
  return {
    toasts,
    success: (msg: string): void => show(msg, 'success'),
    error: (msg: string): void => show(msg, 'error'),
    info: (msg: string): void => show(msg, 'info'),
  };
}
