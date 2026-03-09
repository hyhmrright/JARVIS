<template>
  <aside 
    v-if="isVisible"
    :class="[
      'fixed right-0 top-0 h-screen bg-zinc-900 border-l border-zinc-800 transition-all duration-300 ease-in-out z-50 flex flex-col shadow-2xl',
      collapsed ? 'w-0 opacity-0 invisible' : 'w-[450px] lg:w-[600px] opacity-100 visible'
    ]"
  >
    <!-- Header -->
    <div class="h-14 flex items-center px-4 justify-between border-b border-zinc-800 bg-zinc-950/50 backdrop-blur">
      <div class="flex items-center gap-2">
        <Layout class="w-4 h-4 text-zinc-400" />
        <span class="text-xs font-bold uppercase tracking-widest text-zinc-300">Live Canvas</span>
      </div>
      <div class="flex items-center gap-1">
        <button 
          class="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-zinc-200 transition-colors"
          title="Pop out"
          @click="popOut"
        >
          <ExternalLink class="w-4 h-4" />
        </button>
        <button 
          class="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-zinc-200 transition-colors"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-auto custom-scrollbar bg-white">
      <!-- HTML Preview -->
      <iframe
        v-if="type === 'html'"
        ref="iframe"
        :srcdoc="wrappedHtml"
        sandbox="allow-scripts allow-forms allow-popups"
        class="w-full h-full border-none"
      ></iframe>

      <!-- Chart Container -->
      <div v-else-if="type === 'chart'" ref="chartRef" class="w-full h-full p-6"></div>

      <!-- Form Container -->
      <div v-else-if="type === 'form'" class="p-8 text-zinc-900">
        <h3 class="text-lg font-bold mb-6 border-b pb-2">{{ formData.title || 'Interactive Form' }}</h3>
        <form class="space-y-6" @submit.prevent="submitForm">
          <div v-for="field in formData.fields" :key="field.name" class="space-y-2">
            <label class="block text-sm font-semibold text-zinc-700">{{ field.label }}</label>
            
            <input 
              v-if="field.type === 'text' || field.type === 'number'"
              v-model="formValues[field.name]"
              :type="field.type"
              class="w-full px-3 py-2 border border-zinc-300 rounded-md focus:ring-2 focus:ring-zinc-500 outline-none"
              :placeholder="field.placeholder"
              :required="field.required"
            />
            
            <select
              v-else-if="field.type === 'select'"
              v-model="formValues[field.name]"
              class="w-full px-3 py-2 border border-zinc-300 rounded-md outline-none"
            >
              <option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>

            <textarea
              v-else-if="field.type === 'textarea'"
              v-model="formValues[field.name]"
              class="w-full px-3 py-2 border border-zinc-300 rounded-md outline-none min-h-[100px]"
              :placeholder="field.placeholder"
            ></textarea>
          </div>
          
          <button 
            type="submit" 
            class="w-full py-3 bg-zinc-900 text-white font-bold rounded-lg hover:bg-zinc-800 transition-colors"
          >
            Submit to JARVIS
          </button>
        </form>
      </div>

      <div v-else class="flex flex-col items-center justify-center h-full text-zinc-400 gap-4">
        <div class="w-12 h-12 rounded-full border-2 border-zinc-800 border-t-zinc-500 animate-spin"></div>
        <span class="text-xs font-medium tracking-tight">Rendering workspace...</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { Layout, X, ExternalLink } from 'lucide-vue-next';
import * as echarts from 'echarts';

const props = defineProps<{
  content: string;
  isVisible: boolean;
  collapsed: boolean;
}>();

const emit = defineEmits(['close', 'submit']);

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

// Determine content type
const type = computed(() => {
  if (props.content.includes('<html')) return 'html';
  try {
    const data = JSON.parse(props.content);
    if (data.type === 'chart') return 'chart';
    if (data.type === 'form') return 'form';
  } catch {
    // Not JSON
  }
  // Fallback check for ECharts JSON inside markdown
  if (props.content.includes('"type": "chart"') || props.content.includes('"xAxis"')) return 'chart';
  return 'html';
});

// HTML Logic
const htmlContent = computed(() => {
  const match = props.content.match(/<html>([\s\S]*?)<\/html>/);
  return match ? match[1] : (type.value === 'html' ? props.content : null);
});

const wrappedHtml = computed(() => {
  if (!htmlContent.value) return '';
  let html = htmlContent.value;
  if (!html.includes('<body')) {
    html = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body { font-family: sans-serif; padding: 2rem; color: #111; }</style></head><body>${html}</body></html>`;
  }
  return html;
});

// Form Logic
interface FormField {
  name: string;
  label: string;
  type: string;
  placeholder?: string;
  required?: boolean;
  default?: any;
  options?: Array<{ label: string; value: any }>;
}

interface FormData {
  title?: string;
  fields: FormField[];
}

const formData = computed<FormData>(() => {
  try {
    return JSON.parse(props.content);
  } catch {
    return { title: 'Interactive Form', fields: [] };
  }
});

const formValues = ref<Record<string, any>>({});

watch(formData, (newVal) => {
  if (newVal.fields) {
    newVal.fields.forEach((f: FormField) => {
      if (formValues.value[f.name] === undefined) {
        formValues.value[f.name] = f.default || '';
      }
    });
  }
}, { immediate: true });

const submitForm = () => {
  emit('submit', formValues.value);
};

// Chart Logic
const initChart = () => {
  if (!chartRef.value) return;
  if (chartInstance) chartInstance.dispose();
  
  chartInstance = echarts.init(chartRef.value);
  try {
    const option = JSON.parse(props.content);
    chartInstance.setOption(option);
  } catch (e) {
    console.error("Failed to parse chart option", e);
  }
};

watch([type, () => props.isVisible, () => props.collapsed], () => {
  if (type.value === 'chart' && props.isVisible && !props.collapsed) {
    setTimeout(initChart, 100);
  }
});

onMounted(() => {
  window.addEventListener('resize', () => chartInstance?.resize());
});

onUnmounted(() => {
  chartInstance?.dispose();
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
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #e4e4e7; border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
</style>
