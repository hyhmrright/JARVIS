<template>
  <div class="h-screen bg-[#0a0a0a] flex flex-col overflow-hidden text-zinc-300">
    <!-- Studio Header -->
    <header class="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-zinc-950/50 backdrop-blur-md z-10">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 bg-white text-black flex items-center justify-center rounded font-black text-[10px]">J</div>
          <h1 class="text-[13px] font-bold text-white tracking-tight">{{ $t('workflowStudio.title') }}</h1>
        </div>
        <div class="h-4 w-px bg-zinc-800"></div>
        <input
          v-model="workflowName"
          class="bg-transparent border-none outline-none text-[12px] font-medium text-zinc-400 focus:text-white transition-colors"
          :placeholder="$t('workflowStudio.untitledWorkflow')"
        />
      </div>
      <div class="flex items-center gap-3">
        <button
          v-if="workflowId"
          class="px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-[11px] font-bold uppercase tracking-widest hover:bg-indigo-500 transition-all flex items-center gap-2 disabled:opacity-50"
          :disabled="running"
          @click="onRun"
        >
          <Play class="w-3.5 h-3.5 fill-current" />
          {{ running ? 'Running...' : 'Run' }}
        </button>
        <button
          class="px-4 py-1.5 bg-white text-black rounded-lg text-[11px] font-bold uppercase tracking-widest hover:bg-zinc-200 transition-all flex items-center gap-2 disabled:opacity-50"
          :disabled="saving || loadFailed"
          @click="onSave"
        >
          <Save class="w-3.5 h-3.5" />
          {{ saving ? $t('common.saving') : $t('workflowStudio.saveWorkflow') }}
        </button>
        <router-link to="/" class="text-[11px] font-bold text-zinc-500 hover:text-white transition-colors">{{ $t('common.close') }}</router-link>
      </div>
    </header>

    <!-- Studio Main Area -->
    <div class="flex-1 flex relative">
      <!-- Node Sidebar -->
      <aside class="w-64 border-r border-white/5 bg-zinc-950/30 p-6 space-y-8 overflow-y-auto">
        <div class="space-y-4">
          <p class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em]">{{ $t('workflowStudio.addNodes') }}</p>
          <div class="grid grid-cols-1 gap-2">
            <div
              v-for="node in nodeTypes"
              :key="node.type"
              class="flex items-center gap-3 p-3 rounded-xl border border-zinc-800 bg-zinc-900/50 cursor-grab hover:border-zinc-600 hover:bg-zinc-800 transition-all group"
              draggable="true"
              @dragstart="onDragStart($event, node.type)"
            >
              <div class="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center text-zinc-400 group-hover:bg-white group-hover:text-black transition-colors">
                <component :is="node.icon" class="w-4 h-4" />
              </div>
              <div>
                <p class="text-[11px] font-bold text-zinc-200 uppercase tracking-tight">{{ node.label }}</p>
                <p class="text-[9px] text-zinc-500 truncate">{{ node.description }}</p>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Flow Canvas -->
      <div class="flex-1 relative" @drop="onDrop" @dragover.prevent>
        <VueFlow
          v-model="elements"
          :node-types="nodeTypeComponents"
          fit-view-on-init
          class="bg-zinc-950"
          @connect="onConnect"
        >
          <Background pattern-color="#27272a" :gap="20" />
          <Controls />
        </VueFlow>

        <!-- Execution Drawer Toggle -->
        <button
          v-if="workflowId"
          class="absolute top-4 right-4 z-20 p-2 bg-zinc-900/80 border border-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-all shadow-xl backdrop-blur-md"
          @click="showRunDrawer = !showRunDrawer; if(showRunDrawer) fetchHistory()"
        >
          <History v-if="!showRunDrawer" class="w-4 h-4" />
          <X v-else class="w-4 h-4" />
        </button>
      </div>

      <!-- Run Drawer (Overlay) -->
      <aside
        v-if="showRunDrawer"
        class="absolute inset-y-0 right-0 w-96 bg-zinc-950 border-l border-white/5 shadow-2xl z-30 flex flex-col animate-in slide-in-from-right duration-300"
      >
        <div class="h-14 border-b border-white/5 flex items-center px-6 gap-6">
          <button
            v-for="tab in (['input', 'log', 'history'] as const)" :key="tab"
            class="text-[10px] font-bold uppercase tracking-widest transition-colors relative h-full"
            :class="activeRunTab === tab ? 'text-white' : 'text-zinc-500 hover:text-zinc-300'"
            @click="activeRunTab = tab"
          >
            {{ tab }}
            <div v-if="activeRunTab === tab" class="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500"></div>
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <!-- Input Tab -->
          <div v-if="activeRunTab === 'input'" class="space-y-6">
            <p class="text-[10px] text-zinc-500 leading-relaxed uppercase tracking-wider font-bold">Execution Inputs</p>
            <div v-for="node in elements.filter(e => 'type' in e && e.type === 'input')" :key="node.id" class="space-y-2">
              <label class="text-[11px] font-medium text-zinc-400">{{ node.data?.label || node.id }}</label>
              <textarea
                v-model="runInputs[node.data?.variable || node.id]"
                rows="3"
                class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white focus:border-indigo-500 outline-none transition-colors"
                placeholder="Enter value..."
              ></textarea>
            </div>
            <button
              class="w-full py-3 bg-white text-black text-[11px] font-black uppercase tracking-widest rounded-xl hover:bg-zinc-200 transition-all mt-4"
              @click="onRun"
            >Execute Workflow</button>
          </div>

          <!-- Log Tab -->
          <div v-if="activeRunTab === 'log'" class="space-y-4">
            <div v-if="runLogs.length === 0" class="py-20 text-center">
              <div class="w-10 h-10 bg-zinc-900 rounded-full flex items-center justify-center mx-auto mb-4">
                <Play class="w-4 h-4 text-zinc-700" />
              </div>
              <p class="text-[11px] text-zinc-600">No logs yet. Start an execution.</p>
            </div>
            <div v-for="(log, idx) in runLogs" :key="idx" class="p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold text-zinc-400 uppercase tracking-tight">{{ log.node_id }}</span>
                <span class="text-[9px] font-mono text-zinc-600">{{ log.duration_ms }}ms</span>
              </div>
              <p class="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">{{ log.output }}</p>
            </div>
            <div v-if="running" class="flex items-center gap-3 p-4">
              <div class="w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
              <span class="text-[10px] text-zinc-500 font-bold uppercase animate-pulse">Running node...</span>
            </div>
          </div>

          <!-- History Tab -->
          <div v-if="activeRunTab === 'history'" class="space-y-3">
            <div v-for="run in runHistory" :key="run.id" class="p-4 bg-zinc-900/30 border border-zinc-800/50 rounded-xl hover:bg-zinc-900 transition-colors cursor-pointer group">
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <CheckCircle2 v-if="run.status === 'completed'" class="w-3.5 h-3.5 text-emerald-500" />
                  <AlertCircle v-else-if="run.status === 'failed'" class="w-3.5 h-3.5 text-red-500" />
                  <div v-else class="w-3 h-3 border-2 border-zinc-700 border-t-transparent rounded-full animate-spin"></div>
                  <span class="text-[11px] font-bold text-zinc-300 uppercase tracking-tight">{{ run.status }}</span>
                </div>
                <span class="text-[9px] font-mono text-zinc-600">{{ new Date(run.started_at).toLocaleString() }}</span>
              </div>
              <div class="text-[10px] text-zinc-500 line-clamp-1 group-hover:text-zinc-400 transition-colors">
                ID: {{ run.id }}
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Property Panel (Right) -->
      <aside v-if="selectedNode" class="w-80 border-l border-white/5 bg-zinc-950/30 p-6 overflow-y-auto animate-in slide-in-from-right-4 duration-300">
        <div class="space-y-6">
          <div class="flex items-center justify-between">
            <p class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em]">{{ $t('workflowStudio.nodeProperties') }}</p>
            <button class="text-zinc-500 hover:text-white" @click="selectedNode = null"><X class="w-4 h-4" /></button>
          </div>

          <div class="space-y-4">
            <div class="space-y-1.5">
              <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ $t('workflowStudio.labelField') }}</label>
              <input v-model="selectedNode.data.label" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white" />
            </div>

            <div v-if="selectedNode.type === 'llm'" class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ $t('workflowStudio.modelField') }}</label>
                <select v-model="selectedNode.data.model" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white">
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                  <option value="deepseek-chat">DeepSeek Chat</option>
                </select>
              </div>
              <div class="space-y-1.5">
                <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ $t('workflowStudio.promptTemplateField') }}</label>
                <textarea v-model="selectedNode.data.prompt" rows="6" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono"></textarea>
              </div>
            </div>

            <div v-else-if="selectedNode.type === 'condition'" class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">条件表达式 (Jinja2)</label>
                <textarea
                  v-model="selectedNode.data.condition_expression"
                  rows="3"
                  class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono"
                  placeholder="{{ nodes.node_id.output | length > 0 }}"
                ></textarea>
                <p class="text-[9px] text-zinc-600 leading-relaxed">使用 Jinja2 模板，通过 nodes.&lt;id&gt;.output 访问节点输出</p>
              </div>
            </div>

            <div v-else-if="selectedNode.type === 'output'" class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">输出格式</label>
                <select v-model="selectedNode.data.format" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white">
                  <option value="text">文本</option>
                  <option value="markdown">Markdown</option>
                  <option value="json">JSON</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, markRaw, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { VueFlow, useVueFlow, type Elements, type Connection, type Edge, type Node } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { Save, Box, Target, GitFork, X, MessageSquare, Play, History, CheckCircle2, AlertCircle, Image as ImageIcon } from 'lucide-vue-next';
import LLMNode from '@/components/workflow/LLMNode.vue';
import ToolNode from '@/components/workflow/ToolNode.vue';
import ImageGenNode from '@/components/workflow/ImageGenNode.vue';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import { useToast } from '@/composables/useToast';
import client from '@/api/client';

const { t } = useI18n();
const { success: toastSuccess, error: toastError } = useToast();
const route = useRoute();
const router = useRouter();

const workflowId = ref<string | null>(null);
const saving = ref(false);
const loadFailed = ref(false);
const workflowName = ref('');
const running = ref(false);
const showRunDrawer = ref(false);
const activeRunTab = ref<'input' | 'log' | 'history'>('input');
const runInputs = ref<Record<string, string>>({});
const runLogs = ref<Array<{ node_id: string; output: string; duration_ms: number; status: string }>>([]);
const runHistory = ref<any[]>([]);
const currentRunId = ref<string | null>(null);
let runTimeoutId: ReturnType<typeof setTimeout> | null = null;

function resetRunTimeout() {
  if (runTimeoutId) clearTimeout(runTimeoutId);
  runTimeoutId = setTimeout(() => {
    runLogs.value.push({ node_id: 'system', output: '30秒无响应，工作流可能已超时', duration_ms: 0, status: 'warning' });
  }, 30000);
}

const elements = ref<Elements>([
  { id: '1', type: 'input', label: t('workflowStudio.nodeStart'), position: { x: 250, y: 100 }, data: { label: t('workflowStudio.workflowStart') } }
]);

const { addNodes, addEdges, onNodeClick, project, toObject, updateNodeData } = useVueFlow();
const selectedNode = ref<Node | null>(null);

// Static part — icons never change; separate from reactive translations to avoid
// reconstructing the array (and invalidating v-for keying) on every locale change.
const nodeTypeMeta = [
  { type: 'llm', icon: markRaw(MessageSquare) },
  { type: 'tool', icon: markRaw(Box) },
  { type: 'condition', icon: markRaw(GitFork) },
  { type: 'output', icon: markRaw(Target) },
  { type: 'image_gen', icon: markRaw(ImageIcon) },
] as const;

const nodeTypes = computed(() => nodeTypeMeta.map(({ type, icon }) => ({
  type,
  icon,
  label: t(`workflowStudio.node${type.charAt(0).toUpperCase() + type.slice(1)}`),
  description: t(`workflowStudio.node${type.charAt(0).toUpperCase() + type.slice(1)}Desc`),
})));

const nodeTypeComponents = {
  llm: markRaw(LLMNode),
  tool: markRaw(ToolNode),
  image_gen: markRaw(ImageGenNode),
} as any;

onNodeClick(({ node }) => {
  selectedNode.value = node;
});

const onConnect = (params: Connection | Edge) => {
  addEdges([params]);
};

const onDragStart = (event: DragEvent, nodeType: string) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  }
};

const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/vueflow');
  if (!type) return;

  // Subtract the canvas bounding rect so project() receives canvas-relative
  // coordinates rather than screen-absolute coordinates.
  const canvasEl = document.querySelector('.vue-flow') as HTMLElement | null;
  const { left = 0, top = 0 } = canvasEl?.getBoundingClientRect() ?? {};
  const position = project({ x: event.clientX - left, y: event.clientY - top });
  const nodeLabel = nodeTypes.value.find((n) => n.type === type)?.label ?? type.toUpperCase();
  addNodes([{
    id: `node_${Date.now()}`,
    type,
    position,
    label: nodeLabel,
    data: { label: nodeLabel, model: 'gpt-4o', prompt: '' },
  }]);
};

const onRun = async () => {
  if (running.value || !workflowId.value) return;

  // 提取输入变量
  const { nodes } = toObject();
  const inputNodes = nodes.filter(n => n.type === 'input');

  if (activeRunTab.value === 'input' && inputNodes.length > 0) {
    // 检查是否填写了所有输入
    const missing = inputNodes.filter(n => !runInputs.value[n.data.variable || n.id]);
    if (missing.length > 0 && Object.keys(runInputs.value).length < inputNodes.length) {
      activeRunTab.value = 'input';
      showRunDrawer.value = true;
      return;
    }
  }

  running.value = true;
  runLogs.value = [];
  activeRunTab.value = 'log';
  showRunDrawer.value = true;

  // 重置节点状态
  nodes.forEach(n => updateNodeData(n.id, { status: 'pending' }));

  try {
    const token = localStorage.getItem('token');
    const response = await fetch(`/api/workflows/${workflowId.value}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ inputs: runInputs.value })
    });

    if (!response.ok) throw new Error('Execution failed');

    const reader = response.body?.getReader();
    if (!reader) return;

    resetRunTimeout();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.trim().startsWith('data: ')) {
          resetRunTimeout();
          try {
            const event = JSON.parse(line.substring(6));
            if (event.type === 'node_done') {
              runLogs.value.push(event);
              updateNodeData(event.node_id, { status: 'completed', output: event.output });
            } else if (event.type === 'run_done') {
              if (runTimeoutId) { clearTimeout(runTimeoutId); runTimeoutId = null; }
              currentRunId.value = event.run_id;
              running.value = false;
              toastSuccess(`Workflow ${event.status}`);
              fetchHistory();
            }
          } catch (e) {
            console.warn("SSE parse error", e);
          }
        }
      }
    }
  } catch (err) {
    console.error('Run failed:', err);
    toastError('Workflow execution failed');
    running.value = false;
  }
};

const fetchHistory = async () => {
  if (!workflowId.value) return;
  try {
    const { data } = await client.get(`/workflows/${workflowId.value}/runs`);
    runHistory.value = data;
  } catch (err) {
    console.error('Failed to fetch history:', err);
  }
};

const onSave = async () => {
  if (saving.value || loadFailed.value) return;
  saving.value = true;
  try {
    // toObject() returns clean Node/Edge DTOs, stripping VueFlow-internal runtime
    // fields (handleBounds, computedPosition, dragging, selected, etc.).
    const { nodes, edges } = toObject();
    const payload = {
      name: workflowName.value || t('workflowStudio.untitledWorkflow'),
      dsl: { nodes, edges },
    };
    if (workflowId.value) {
      await client.put(`/workflows/${workflowId.value}`, payload);
    } else {
      const { data } = await client.post('/workflows', payload);
      workflowId.value = data.id;
      router.replace({ query: { id: data.id } });
    }
    toastSuccess(t('workflowStudio.saved'));
  } catch (err) {
    console.error('Workflow save failed:', err);
    toastError(t('workflowStudio.saveError'));
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  const id = route.query.id as string | undefined;
  if (!id) return;
  try {
    const { data } = await client.get(`/workflows/${id}`);
    workflowId.value = data.id;
    workflowName.value = data.name;
    // Restore from the clean nodes/edges DSL written by onSave.
    if (data.dsl?.nodes?.length) {
      elements.value = [...data.dsl.nodes, ...(data.dsl.edges ?? [])];
    }
  } catch (err) {
    console.error('Workflow load failed:', err);
    toastError(t('workflowStudio.loadError'));
    // Prevent onSave from silently creating a new workflow when the requested
    // workflow failed to load (e.g. deleted or belongs to another user).
    loadFailed.value = true;
  }
});
</script>

<style>
.vue-flow__node {
  border-radius: 12px;
  border: 1px solid #27272a;
  background: #09090b;
  color: white;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.vue-flow__node.selected {
  border-color: white;
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.05);
}
.vue-flow__handle {
  width: 8px;
  height: 8px;
  background: #52525b;
  border: 2px solid #09090b;
}
.vue-flow__edge-path {
  stroke: #3f3f46;
  stroke-width: 2;
}
</style>
