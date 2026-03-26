import { onBeforeUnmount, onMounted, type Ref } from 'vue'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useFocusTrap(containerRef: Ref<HTMLElement | null>) {
  function getFocusable() {
    return containerRef.value
      ? Array.from(containerRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      : []
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== 'Tab' || !containerRef.value) return

    const focusable = getFocusable()
    if (!focusable.length) return

    const activeElement = e.target as HTMLElement
    if (!containerRef.value.contains(activeElement)) return

    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (e.shiftKey) {
      if (activeElement === first) {
        e.preventDefault()
        last.focus()
      }
    } else {
      if (activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }

  onMounted(() => {
    containerRef.value?.addEventListener('keydown', handleKeydown)
  })
  onBeforeUnmount(() => {
    containerRef.value?.removeEventListener('keydown', handleKeydown)
  })
}
