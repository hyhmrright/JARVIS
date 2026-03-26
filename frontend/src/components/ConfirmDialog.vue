<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      @keydown.escape="$emit('update:modelValue', false)"
    >
      <div ref="dialogRef" class="bg-gray-800 rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
        <h2 class="text-lg font-semibold text-white mb-2">{{ title }}</h2>
        <p v-if="message" class="text-gray-400 text-sm mb-6">{{ message }}</p>
        <div class="flex justify-end gap-3">
          <button
            class="focus-default px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm transition-colors"
            @click="$emit('update:modelValue', false)"
          >
            {{ cancelLabel || $t('common.cancel', 'Cancel') }}
          </button>
          <button
            class="px-4 py-2 rounded bg-red-600 hover:bg-red-500 text-white text-sm transition-colors"
            @click="$emit('confirm')"
          >
            {{ confirmLabel || $t('common.confirm', 'Confirm') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useFocusTrap } from '@/composables/useFocusTrap'

const props = defineProps<{
  modelValue: boolean
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
}>()

const dialogRef = ref<HTMLElement | null>(null)
useFocusTrap(dialogRef)

watch(
  () => props.modelValue,
  async (isOpen) => {
    if (isOpen) {
      await nextTick()
      dialogRef.value?.querySelector<HTMLElement>('.focus-default')?.focus()
    }
  },
)
</script>
