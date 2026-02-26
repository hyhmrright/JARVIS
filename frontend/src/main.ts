import { createApp } from "vue";
import { createPinia } from "pinia";
import router from "./router";
import i18n from "./i18n";
import App from "./App.vue";
import "./assets/styles/global.css";
import "./assets/styles/animations.css";
import "./assets/styles/components.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(i18n);
app.mount("#app");

function reportError(message: string, source: string, stack?: string): void {
  const traceId = (document.cookie.match(/X-Trace-ID=([^;]+)/) ?? [])[1];
  fetch("/api/logs/client-error", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: String(message).slice(0, 500),
      source,
      trace_id: traceId ?? null,
      url: window.location.href,
      stack: stack?.slice(0, 1000) ?? null,
    }),
  }).catch(() => {
    // best-effort, silently ignore
  });
}

app.config.errorHandler = (err, _instance, info) => {
  console.error("[Vue error]", err, info);
  reportError(String(err), `vue:${info}`);
};

window.onerror = (message, source, lineno, colno, error) => {
  reportError(String(message), `window:${source ?? ""}:${lineno ?? 0}:${colno ?? 0}`, error?.stack);
  return false;
};

window.addEventListener("unhandledrejection", (event) => {
  reportError(String(event.reason), "unhandledrejection", (event.reason as Error)?.stack);
});
