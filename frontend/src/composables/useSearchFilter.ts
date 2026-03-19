import { ref, computed, type Ref } from 'vue';

export function useSearchFilter<T extends { name: string; description?: string | null }>(
  source: Ref<T[]>,
) {
  const query = ref('');
  const filtered = computed(() => {
    if (!query.value.trim()) return source.value;
    const q = query.value.toLowerCase();
    return source.value.filter(
      (item) => item.name.toLowerCase().includes(q) || (item.description ?? '').toLowerCase().includes(q),
    );
  });
  return { query, filtered };
}
