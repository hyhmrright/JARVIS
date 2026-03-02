<template>
  <div v-if="isActive" class="voice-overlay">
    <div class="voice-card">
      <div class="voice-visualizer">
        <div :class="['pulse-ring', status]"></div>
        <div class="pulse-icon">🎤</div>
      </div>
      
      <div class="voice-content">
        <p class="user-transcription">{{ transcription || 'Listening...' }}</p>
        <p class="ai-reply">{{ aiText }}</p>
      </div>

      <div class="voice-footer">
        <span class="status-text">{{ status.toUpperCase() }}</span>
        <button class="btn-stop" @click="endSession">CLOSE</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useVoiceStream } from '@/composables/useVoiceStream';

const { isActive, transcription, aiText, status, startSession, endSession } = useVoiceStream();

// Expose start method to parent
defineExpose({
  start: startSession
});
</script>

<style scoped>
.voice-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.8);
  backdrop-filter: blur(10px);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.voice-card {
  width: 90%;
  max-width: 400px;
  background: var(--bg-secondary);
  border-radius: 20px;
  padding: 2rem;
  text-align: center;
  box-shadow: 0 20px 50px rgba(0,0,0,0.5);
}

.voice-visualizer {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pulse-icon {
  font-size: 2rem;
  z-index: 2;
}

.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.3;
}

.pulse-ring.recording {
  animation: pulse 1.5s infinite;
}

.pulse-ring.playing {
  background: #4caf50;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.5; }
  100% { transform: scale(2); opacity: 0; }
}

.voice-content {
  min-height: 100px;
  margin-bottom: 2rem;
}

.user-transcription {
  font-size: 1.2rem;
  color: var(--text-primary);
  margin-bottom: 1rem;
}

.ai-reply {
  font-size: 1rem;
  color: var(--accent);
  line-height: 1.4;
}

.voice-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-text {
  font-size: 0.8rem;
  color: var(--text-muted);
  letter-spacing: 2px;
}

.btn-stop {
  background: var(--danger);
  color: white;
  border: none;
  padding: 0.5rem 1.5rem;
  border-radius: 30px;
  cursor: pointer;
  font-weight: bold;
}
</style>
