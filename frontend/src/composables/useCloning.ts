import { reactive } from 'vue';

export function useCloning() {
  const cloning = reactive(new Set<string>());

  const isCloning = (id: string) => cloning.has(id);

  const withCloning = async (id: string, fn: () => Promise<void>) => {
    if (cloning.has(id)) return;
    cloning.add(id);
    try {
      await fn();
    } finally {
      cloning.delete(id);
    }
  };

  return { isCloning, withCloning };
}
