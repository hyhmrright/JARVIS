import { ref } from 'vue';

export function useVoiceStream() {
  const isActive = ref(false);
  const transcription = ref('');
  const aiText = ref('');
  const status = ref<'idle' | 'recording' | 'processing' | 'playing'>('idle');
  
  let socket: WebSocket | null = null;
  let mediaRecorder: MediaRecorder | null = null;
  const audioContext: AudioContext | null = null;
  const audioQueue: Blob[] = [];
  let isPlaying = false;

  const startSession = async () => {
    const token = localStorage.getItem('token');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    socket = new WebSocket(`${protocol}//${host}/api/voice/stream?token=${token}`);
    socket.binaryType = 'blob';

    socket.onopen = () => {
      isActive.value = true;
      startRecording();
    };

    socket.onmessage = async (event) => {
      if (typeof event.data === 'string') {
        const data = JSON.parse(event.data);
        if (data.type === 'transcription') {
          transcription.value = data.text;
        } else if (data.type === 'ai_text_delta') {
          aiText.value += data.delta;
        } else if (data.type === 'done') {
          status.value = 'idle';
        }
      } else {
        // Binary audio response
        audioQueue.push(event.data);
        if (!isPlaying) playNextInQueue();
      }
    };

    socket.onclose = () => {
      isActive.value = false;
      stopRecording();
    };
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0 && socket?.readyState === WebSocket.OPEN) {
        socket.send(event.data);
      }
    };

    mediaRecorder.start(500); // Send chunks every 500ms
    status.value = 'recording';
  };

  const stopRecording = () => {
    mediaRecorder?.stop();
    mediaRecorder?.stream.getTracks().forEach(t => t.stop());
    status.value = 'processing';
  };

  const playNextInQueue = async () => {
    if (audioQueue.length === 0) {
      isPlaying = false;
      return;
    }

    isPlaying = true;
    status.value = 'playing';
    const blob = audioQueue.shift()!;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    
    audio.onended = () => {
      URL.revokeObjectURL(url);
      playNextInQueue();
    };
    
    await audio.play();
  };

  const endSession = () => {
    socket?.close();
    isActive.value = false;
    status.value = 'idle';
  };

  return {
    isActive,
    transcription,
    aiText,
    status,
    startSession,
    endSession
  };
}
