/**
 * i18n 配置
 *
 * 语言检测优先级：localStorage 用户选择 > 浏览器语言 > 回退到中文。
 * 支持语言：zh / en / ja / ko / fr / de
 */
import { createI18n } from "vue-i18n";
import zh from "./locales/zh.json";
import en from "./locales/en.json";
import ja from "./locales/ja.json";
import ko from "./locales/ko.json";
import fr from "./locales/fr.json";
import de from "./locales/de.json";

export const SUPPORTED_LOCALES = ["zh", "en", "ja", "ko", "fr", "de"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

/** 语言代码 → 原生名称，用于语言切换 UI */
export const LOCALE_LABELS: Record<SupportedLocale, string> = {
  zh: "中文",
  en: "English",
  ja: "日本語",
  ko: "한국어",
  fr: "Français",
  de: "Deutsch",
};

const LOCALE_STORAGE_KEY = "jarvis-locale";

/** 从浏览器语言偏好中匹配支持的 locale，如 "zh-CN" → "zh"、"en-US" → "en" */
function detectLocale(): SupportedLocale {
  const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
  if (saved && SUPPORTED_LOCALES.includes(saved as SupportedLocale)) {
    return saved as SupportedLocale;
  }
  const browserLang = navigator.language.split("-")[0];
  if (SUPPORTED_LOCALES.includes(browserLang as SupportedLocale)) {
    return browserLang as SupportedLocale;
  }
  return "zh";
}

const detectedLocale = detectLocale();
document.documentElement.lang = detectedLocale;

const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: detectedLocale,
  fallbackLocale: "zh",
  messages: { zh, en, ja, ko, fr, de },
});

/** 切换语言并持久化到 localStorage，同时更新 HTML lang 属性 */
export function setLocale(locale: SupportedLocale) {
  i18n.global.locale.value = locale;
  localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  document.documentElement.lang = locale;
}

export default i18n;
