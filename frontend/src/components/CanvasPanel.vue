<template>
  <Transition name="canvas-slide">
    <div v-if="isOpen" class="canvas-panel">
      <div class="canvas-header">
        <span class="canvas-title">{{ currentTitle || 'Canvas' }}</span>
        <button class="canvas-close" title="关闭" @click="isOpen = false">&#10005;</button>
      </div>
      <iframe
        class="canvas-frame"
        sandbox="allow-scripts allow-forms"
        :srcdoc="currentHtml"
        title="Agent Canvas"
      />
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps<{
  conversationId: string
}>()

const isOpen = ref(false)
const currentHtml = ref('')
const currentTitle = ref('')
let streamController: AbortController | null = null

const connectCanvas = async (convId: string) => {
  if (streamController) {
    streamController.abort()
    streamController = null
  }
  if (!convId) return

  const token = localStorage.getItem('token')
  if (!token) return

  const controller = new AbortController()
  streamController = controller

  try {
    const response = await fetch(`/api/canvas/stream/${convId}`, {
      headers: {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      signal: controller.signal,
    })
    if (!response.ok || !response.body) return

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''

      for (const rawEvent of events) {
        for (const line of rawEvent.split('\n')) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6)) as Record<string, unknown>
            if (event.type === 'canvas_render') {
              currentHtml.value = String(event.html ?? '')
              currentTitle.value = String(event.title ?? 'Canvas')
              isOpen.value = true
            }
          } catch {
            // Ignore malformed events
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return
    }
  } finally {
    if (streamController === controller) {
      streamController = null
    }
  }
}

watch(
  () => props.conversationId,
  (newId) => {
    if (newId) connectCanvas(newId)
  },
  { immediate: true },
)

onUnmounted(() => {
  streamController?.abort()
  streamController = null
})

defineExpose({ isOpen })
</script>

<style scoped>
.canvas-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 480px;
  max-width: 45vw;
  background: var(--color-surface, #1e293b);
  border-left: 1px solid var(--color-border, #334155);
  display: flex;
  flex-direction: column;
  z-index: 100;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.3);
}

.canvas-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border, #334155);
  font-weight: 600;
}

.canvas-title {
  font-size: 0.9rem;
}

.canvas-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.6;
  font-size: 1rem;
}

.canvas-close:hover {
  opacity: 1;
}

.canvas-frame {
  flex: 1;
  border: none;
  background: white;
}

.canvas-slide-enter-active,
.canvas-slide-leave-active {
  transition: transform 0.25s ease;
}

.canvas-slide-enter-from,
.canvas-slide-leave-to {
  transform: translateX(100%);
}
</style>
