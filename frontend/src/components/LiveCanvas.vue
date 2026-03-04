<template>
  <div v-if="htmlContent" class="live-canvas-container">
    <div class="canvas-header">
      <span class="canvas-title">Live Canvas</span>
      <div class="canvas-actions">
        <button title="Pop out" @click="popOut">↗</button>
      </div>
    </div>
    <iframe
      ref="iframe"
      :srcdoc="wrappedHtml"
      sandbox="allow-scripts allow-forms allow-popups"
      class="canvas-iframe"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps<{
  content: string;
}>();

const htmlContent = computed(() => {
  const match = props.content.match(/<html>([\s\S]*?)<\/html>/);
  return match ? match[1] : null;
});

const wrappedHtml = computed(() => {
  if (!htmlContent.value) return '';
  
  // Wrap in basic boilerplate if not present
  let html = htmlContent.value;
  if (!html.includes('<body')) {
    html = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            body { 
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
              margin: 0; 
              padding: 1rem;
              color: #333;
              background: #fff;
            }
          </style>
        </head>
        <body>${html}</body>
      </html>
    `;
  }
  return html;
});

const popOut = () => {
  const win = window.open('', '_blank');
  if (win) {
    win.document.write(wrappedHtml.value);
    win.document.close();
  }
};
</script>

<style scoped>
.live-canvas-container {
  margin-top: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.canvas-header {
  background: #f8fafc;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.canvas-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: #64748b;
  letter-spacing: 0.05em;
}

.canvas-actions button {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  padding: 0.25rem;
  border-radius: 4px;
}

.canvas-actions button:hover {
  background: #e2e8f0;
  color: #64748b;
}

.canvas-iframe {
  width: 100%;
  height: 400px;
  border: none;
  display: block;
}
</style>
