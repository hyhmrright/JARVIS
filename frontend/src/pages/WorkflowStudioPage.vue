<template>
  <div class="h-screen bg-[#0a0a0a] flex flex-col overflow-hidden text-zinc-300">
    <!-- Studio Header -->
    <header class="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-zinc-950/50 backdrop-blur-md z-10">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 bg-white text-black flex items-center justify-center rounded font-black text-[10px]">J</div>
          <h1 class="text-[13px] font-bold text-white tracking-tight">Workflow Studio</h1>
        </div>
        <div class="h-4 w-px bg-zinc-800"></div>
        <input 
          v-model="workflowName" 
          class="bg-transparent border-none outline-none text-[12px] font-medium text-zinc-400 focus:text-white transition-colors"
          placeholder="Untitled Workflow"
        />
      </div>
      <div class="flex items-center gap-3">
        <button 
          class="px-4 py-1.5 bg-white text-black rounded-lg text-[11px] font-bold uppercase tracking-widest hover:bg-zinc-200 transition-all flex items-center gap-2"
          @click="onSave"
        >
          <Save class="w-3.5 h-3.5" />
          Save Workflow
        </button>
        <router-link to="/" class="text-[11px] font-bold text-zinc-500 hover:text-white transition-colors">CLOSE</router-link>
      </div>
    </header>

    <!-- Studio Main Area -->
    <div class="flex-1 flex relative">
      <!-- Node Sidebar -->
      <aside class="w-64 border-r border-white/5 bg-zinc-950/30 p-6 space-y-8 overflow-y-auto">
        <div class="space-y-4">
          <p class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em]">Add Nodes</p>
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
      </div>

      <!-- Property Panel (Right) -->
      <aside v-if="selectedNode" class="w-80 border-l border-white/5 bg-zinc-950/30 p-6 overflow-y-auto animate-in slide-in-from-right-4 duration-300">
        <div class="space-y-6">
          <div class="flex items-center justify-between">
            <p class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em]">Node Properties</p>
            <button class="text-zinc-500 hover:text-white" @click="selectedNode = null"><X class="w-4 h-4" /></button>
          </div>
          
          <div class="space-y-4">
            <div class="space-y-1.5">
              <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Label</label>
              <input v-model="selectedNode.data.label" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white" />
            </div>
            
            <div v-if="selectedNode.type === 'llm'" class="space-y-4">
              <div class="space-y-1.5">
                <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Model</label>
                <select v-model="selectedNode.data.model" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white">
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                  <option value="deepseek-chat">DeepSeek Chat</option>
                </select>
              </div>
              <div class="space-y-1.5">
                <label class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Prompt Template</label>
                <textarea v-model="selectedNode.data.prompt" rows="6" class="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono"></textarea>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, markRaw } from 'vue';
import { VueFlow, useVueFlow, type Elements, type Connection, type Edge, type Node } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { Save, Box, Target, GitFork, X, MessageSquare } from 'lucide-vue-next';
import LLMNode from '@/components/workflow/LLMNode.vue';
import ToolNode from '@/components/workflow/ToolNode.vue';

// Styles for Vue Flow
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';

const workflowName = ref('');
const elements = ref<Elements>([
  { id: '1', type: 'input', label: 'Start', position: { x: 250, y: 100 }, data: { label: 'Workflow Start' } }
]);

const { addNodes, addEdges, onNodeClick } = useVueFlow();
const selectedNode = ref<Node | null>(null);

const nodeTypes = [
  { type: 'llm', label: 'LLM Node', icon: MessageSquare, description: 'Generate text using AI' },
  { type: 'tool', label: 'Tool Node', icon: Box, description: 'Call a JARVIS tool' },
  { type: 'condition', label: 'Condition', icon: GitFork, description: 'Route based on logic' },
  { type: 'output', label: 'Output', icon: Target, description: 'Return result to user' },
];

const nodeTypeComponents = {
  llm: markRaw(LLMNode),
  tool: markRaw(ToolNode),
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

  const position = { x: event.clientX - 300, y: event.clientY - 100 }; // Offset roughly
  const newNode = {
    id: `node_${Date.now()}`,
    type,
    position,
    label: `${type.toUpperCase()} Node`,
    data: { label: `${type.toUpperCase()} Node`, model: 'gpt-4o', prompt: '' },
  };
  addNodes([newNode]);
};

const onSave = () => {
  console.log('Saving Workflow:', {
    name: workflowName.value,
    elements: elements.value
  });
  alert('Workflow structure logged to console. (Backend integration in Track 3.2)');
};
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
