/**
 * Composable for Web Speech API voice input.
 * Allows the user to dictate text into chat input using the microphone.
 */
import { ref } from "vue";

// Web Speech API types are not in all TS lib.dom.d.ts versions; use any for compatibility
type SpeechRecognitionCtor = new () => any;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

export function useSpeechInput(onResult: (text: string) => void) {
  const isListening = ref(false);
  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);


  let recognition: any = null;

  const start = () => {
    if (!isSupported || isListening.value) return;

    const SpeechRecognitionAPI =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) return;

    recognition = new SpeechRecognitionAPI();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = navigator.language || "zh-CN";

    recognition.onresult = (event: any) => {
      // event.results[0][0].transcript contains the recognized text
      const transcript: string = event.results?.[0]?.[0]?.transcript ?? "";
      if (transcript) {
        onResult(transcript);
      }
      isListening.value = false;
    };

    recognition.onerror = () => {
      isListening.value = false;
    };

    recognition.onend = () => {
      isListening.value = false;
    };

    recognition.start();
    isListening.value = true;
  };

  const stop = () => {
    recognition?.stop();
    recognition = null;
    isListening.value = false;
  };

  const toggle = () => {
    if (isListening.value) {
      stop();
    } else {
      start();
    }
  };

  return { isListening, isSupported, start, stop, toggle };
}
