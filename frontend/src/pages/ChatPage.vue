<template>
  <div class="flex h-screen w-full bg-zinc-950 font-sans">

    <!-- Mobile backdrop overlay -->
    <div
      v-if="isMobile && !sidebarCollapsed"
      aria-hidden="true"
      class="fixed inset-0 z-30 bg-black/50"
      @click="sidebarCollapsed = true"
    />

    <!-- Sidebar -->
    <aside
      :class="[
        'flex flex-col bg-zinc-950 border-r border-zinc-800 transition-all duration-300 ease-in-out',
        isMobile
          ? sidebarCollapsed
            ? 'fixed inset-y-0 left-0 z-50 w-[260px] -translate-x-full'
            : 'fixed inset-y-0 left-0 z-50 w-[260px] translate-x-0 shadow-2xl'
          : sidebarCollapsed
            ? 'w-0 border-none opacity-0'
            : 'w-[260px]'
      ]"
    >
      <div class="h-14 flex items-center px-4 justify-between">
        <template v-if="searchMode">
          <input
            ref="searchInputEl"
            v-model="searchQuery"
            type="text"
            :placeholder="$t('chat.searchPlaceholder')"
            class="flex-1 bg-zinc-800 rounded-md px-2 py-1 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none mr-2"
          />
          <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors" @click="clearSearch">
            <X class="w-4 h-4 text-zinc-400" />
          </button>
        </template>
        <template v-else>
          <div class="flex items-center gap-2 font-semibold tracking-tighter">
            <div class="w-5 h-5 bg-white text-black rounded-sm flex items-center justify-center text-[10px] font-bold">J</div>
            <span class="text-sm text-zinc-100">JARVIS</span>
          </div>
          <div class="flex items-center gap-1">
            <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors" title="Search" @click="searchMode = true">
              <Search class="w-4 h-4 text-zinc-400" />
            </button>
            <button
              class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
              :class="bookmarkMode ? 'text-amber-400' : ''"
              title="Bookmarks"
              @click="toggleBookmarkMode"
            >
              <Bookmark class="w-4 h-4" :class="bookmarkMode ? 'text-amber-400' : 'text-zinc-400'" />
            </button>
            <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors" title="New Chat" @click="chat.newConversation">
              <SquarePen class="w-4 h-4 text-zinc-400" />
            </button>
          </div>
        </template>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 py-4 space-y-0.5 custom-scrollbar">
        <!-- Search results -->
        <template v-if="searchMode && searchQuery.length >= 2">
          <div
            v-for="r in searchResults"
            :key="r.conv_id"
            class="group flex items-start gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            @click="selectSearchResult(r.conv_id)"
          >
            <MessageSquare class="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
            <div class="flex-1 min-w-0">
              <div class="text-xs truncate">{{ r.title }}</div>
              <div class="text-[10px] text-zinc-600 truncate mt-0.5">{{ r.snippet }}</div>
            </div>
          </div>
          <div v-if="searchResults.length === 0" class="px-3 py-6 text-center text-[10px] text-zinc-600">
            No results
          </div>
        </template>
        <!-- Bookmarks panel -->
        <template v-else-if="bookmarkMode">
          <div class="px-3 pb-2 text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">Bookmarks</div>
          <div v-if="bookmarkedMessages.length === 0" class="px-3 py-6 text-center text-[10px] text-zinc-600">
            No bookmarks yet
          </div>
          <div
            v-for="bm in bookmarkedMessages"
            :key="bm.id"
            class="group flex flex-col gap-0.5 px-3 py-2 rounded-md cursor-pointer transition-colors text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            @click="openBookmark(bm)"
          >
            <div class="text-[10px] text-zinc-600 truncate">{{ bm.conv_title }}</div>
            <div class="text-xs line-clamp-2 text-zinc-400">{{ bm.content }}</div>
          </div>
        </template>
        <!-- Normal conversation list -->
        <template v-else>
          <!-- Tag filter bar -->
          <div v-if="activeTagFilter" class="flex items-center gap-1 px-3 pb-2 flex-wrap">
            <span class="text-[9px] text-zinc-500 uppercase tracking-wider">Filter:</span>
            <button
              class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] bg-indigo-600 text-white"
              @click="activeTagFilter = null"
            >
              {{ activeTagFilter }} ×
            </button>
          </div>
          <div
            v-for="c in filteredConversations"
            :key="c.id"
            :class="[
              'group flex flex-col rounded-md cursor-pointer transition-colors relative',
              chat.currentConvId === c.id ? 'bg-zinc-800 text-zinc-100' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
            ]"
            @click="selectConversation(c.id)"
          >
            <!-- Main row -->
            <div class="flex items-center gap-3 px-3 py-2">
              <MessageSquare class="w-3.5 h-3.5 flex-shrink-0" />
              <input
                v-if="renamingConvId === c.id"
                :ref="setRenameInput"
                v-model="renameValue"
                class="text-xs flex-1 bg-zinc-700 text-zinc-100 rounded px-1 outline-none min-w-0"
                maxlength="255"
                @keydown.enter.stop="commitRename(c.id)"
                @keydown.escape.stop.prevent="renamingConvId = null"
                @blur="commitRename(c.id)"
                @click.stop
              />
              <span
                v-else
                class="text-xs truncate flex-1"
                @dblclick.stop="startRename(c)"
              >{{ c.title }}</span>
              <button
                class="p-0.5 rounded transition-opacity"
                :class="c.is_pinned ? 'text-yellow-400 opacity-100' : 'text-zinc-500 hover:text-zinc-300 opacity-0 group-hover:opacity-100'"
                :title="c.is_pinned ? 'Unpin' : 'Pin'"
                @click.stop="togglePin(c.id)"
              >
                <Pin class="w-3 h-3" :class="c.is_pinned ? 'fill-current' : ''" />
              </button>
              <button
                class="opacity-0 group-hover:opacity-100 p-1 hover:text-indigo-400 text-zinc-500"
                title="Add tag"
                @click.stop="tagInputConvId = tagInputConvId === c.id ? null : c.id; tagInputValue = ''"
              >
                <Tag class="w-3 h-3" />
              </button>
              <div class="relative opacity-0 group-hover:opacity-100">
                <button
                  class="p-1 hover:text-zinc-200"
                  title="Export"
                  @click.stop="exportMenuConvId = exportMenuConvId === c.id ? null : c.id"
                >
                  <Download class="w-3 h-3" />
                </button>
                <div
                  v-if="exportMenuConvId === c.id"
                  class="absolute right-0 top-6 z-50 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl py-1 w-36"
                >
                  <button class="w-full text-left px-3 py-1.5 text-[11px] text-zinc-300 hover:bg-zinc-800 hover:text-white" @click.stop="downloadExport(c.id, c.title, 'md')">Markdown (.md)</button>
                  <button class="w-full text-left px-3 py-1.5 text-[11px] text-zinc-300 hover:bg-zinc-800 hover:text-white" @click.stop="downloadExport(c.id, c.title, 'json')">JSON</button>
                  <button class="w-full text-left px-3 py-1.5 text-[11px] text-zinc-300 hover:bg-zinc-800 hover:text-white" @click.stop="downloadExport(c.id, c.title, 'txt')">Plain text (.txt)</button>
                </div>
              </div>
              <button
                class="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400"
                @click.stop="chat.deleteConversation(c.id)"
              >
                <Trash2 class="w-3 h-3" />
              </button>
            </div>
            <!-- Tags row -->
            <div v-if="c.tags.length > 0 || tagInputConvId === c.id" class="flex flex-wrap items-center gap-1 px-8 pb-1.5" @click.stop>
              <div
                v-for="tag in c.tags"
                :key="tag"
                class="inline-flex items-center rounded bg-zinc-700 hover:bg-zinc-600 transition-colors overflow-hidden"
              >
                <button
                  class="px-1.5 py-0.5 text-[9px]"
                  :class="activeTagFilter === tag ? 'text-indigo-400' : 'text-zinc-400'"
                  @click.stop="setTagFilter(tag)"
                >{{ tag }}</button>
                <button
                  :aria-label="`Remove tag ${tag}`"
                  class="px-1 py-0.5 text-[9px] text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click.stop="handleRemoveTag(c.id, tag)"
                >×</button>
              </div>
              <!-- Inline tag input -->
              <div v-if="tagInputConvId === c.id" class="flex items-center gap-1">
                <input
                  v-model="tagInputValue"
                  class="text-[9px] px-1 py-0.5 bg-zinc-700 text-zinc-200 rounded outline-none w-16 focus:ring-1 focus:ring-indigo-500"
                  :placeholder="$t('chat.newTagPlaceholder')"
                  maxlength="100"
                  autofocus
                  @keydown.enter.stop="handleAddTag(c.id)"
                  @keydown.escape.stop="tagInputConvId = null; tagInputValue = ''"
                  @click.stop
                />
                <button class="text-indigo-400 hover:text-indigo-300" @click.stop="handleAddTag(c.id)">
                  <Plus class="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        </template>
        <!-- Load more conversations -->
        <div v-if="chat.conversations.length < chat.conversationsTotal" class="px-3 py-2">
          <button
            class="w-full text-xs text-zinc-500 hover:text-zinc-300 disabled:opacity-40 py-1 transition-colors"
            :disabled="chat.loadingMoreConversations"
            @click="chat.loadMoreConversations()"
          >
            {{ chat.loadingMoreConversations ? 'Loading…' : `Load more (${chat.conversationsTotal - chat.conversations.length} remaining)` }}
          </button>
        </div>
      </nav>

      <div class="p-4 border-t border-zinc-800 space-y-4">
        <div class="space-y-1">
          <router-link to="/proactive" class="flex items-center gap-3 px-2 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 transition-all">
            <Zap class="w-3.5 h-3.5" />
            <span>{{ $t('chat.automations') }}</span>
          </router-link>
          <router-link to="/workflows" class="flex items-center gap-3 px-2 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 transition-all">
            <GitFork class="w-3.5 h-3.5" />
            <span>{{ $t('workflows.title') }}</span>
          </router-link>
          <router-link to="/settings" class="flex items-center gap-3 px-2 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 transition-all">
            <Settings class="w-3.5 h-3.5" />
            <span>{{ $t('chat.settings') }}</span>
          </router-link>
        </div>
        
        <div class="pt-2 border-t border-zinc-800">
          <div class="group flex items-center justify-between w-full px-2 py-2 bg-transparent hover:bg-zinc-900 rounded-lg transition-colors cursor-default">
            <div class="flex items-center gap-3 overflow-hidden">
              <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-zinc-800 to-zinc-700 flex items-center justify-center text-xs font-bold text-white shadow-sm border border-zinc-700/50 flex-shrink-0">
                {{ auth.displayName?.[0] || 'U' }}
              </div>
              <div class="flex flex-col overflow-hidden">
                <span class="text-xs font-medium text-zinc-200 truncate">{{ auth.displayName || 'User' }}</span>
                <span class="text-[10px] text-zinc-500 truncate">Free Plan</span>
              </div>
            </div>
            
            <button class="opacity-0 group-hover:opacity-100 flex items-center gap-1.5 px-2 py-1 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 rounded transition-all text-[10px] font-bold uppercase tracking-wider" title="Sign out" @click="handleLogout">
              <LogOut class="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Content Well -->
    <main class="flex-1 flex flex-col min-w-0 bg-zinc-900 relative">
      <header class="h-14 flex items-center px-6 justify-between border-b border-zinc-800/50 bg-zinc-900/80 backdrop-blur-sm z-40">
        <div class="flex items-center gap-4">
          <button 
            v-if="sidebarCollapsed"
            class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
            @click="sidebarCollapsed = false"
          >
            <PanelLeft class="w-4 h-4 text-zinc-400" />
          </button>
          <h2 class="text-xs font-semibold text-zinc-100 tracking-tight">{{ currentConvTitle }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <button
            v-if="activeCanvasContent"
            :class="['p-1.5 rounded transition-colors', canvasVisible ? 'bg-zinc-100 text-zinc-950' : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800']"
            title="Toggle Canvas"
            @click="canvasVisible = !canvasVisible"
          >
            <Layout class="w-4 h-4" />
          </button>
          <button
            class="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded transition-colors"
            title="Prompt Templates"
            @click="showTemplates = true"
          >
            <Sparkles class="w-4 h-4" />
          </button>
          <button
            class="text-zinc-500 hover:text-zinc-300 transition-colors relative"
            :disabled="sharing"
            @click="handleShare"
          >
            <Share2 class="w-4 h-4" :class="{'animate-pulse': sharing}" />
            
            <!-- Share Link Popover -->
            <div v-if="shareUrl" class="absolute top-10 right-0 w-64 bg-zinc-950 border border-zinc-800 p-3 rounded-lg shadow-2xl z-50 animate-in fade-in zoom-in duration-200">
              <p class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest mb-2">Share Conversation</p>
              <div class="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 mb-2">
                <input type="text" readonly :value="shareUrl" class="bg-transparent border-none outline-none text-[10px] text-zinc-300 flex-1 truncate" />
              </div>
              <button class="w-full py-1.5 bg-white text-black text-[10px] font-bold rounded hover:bg-zinc-200 transition-all" @click="copyShareUrl">
                COPY LINK
              </button>
            </div>
          </button>
        </div>
      </header>

      <!-- Messages Stream -->
      <div class="flex-1 relative overflow-hidden">
      <button
        v-if="showScrollBtn"
        class="absolute bottom-4 right-4 z-20 p-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-full shadow-lg transition-all text-zinc-400 hover:text-white"
        title="Scroll to bottom"
        @click="scrollToBottom"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
      </button>
      <div ref="messagesEl" class="h-full overflow-y-auto custom-scrollbar" @scroll="onMessagesScroll">
        <div class="max-w-3xl mx-auto px-6 py-12 space-y-16">
          
          <!-- New Session Welcome -->
          <div v-if="chat.messages.length === 0" class="pt-20 animate-in fade-in slide-in-from-bottom-4 duration-1000">
            <div class="max-w-2xl mx-auto">
              <div class="w-10 h-10 bg-white text-black rounded-lg flex items-center justify-center font-bold mx-auto mb-6">J</div>
              <h1 class="text-center text-2xl font-bold text-zinc-50 mb-12 tracking-tight">Intelligence at your service.</h1>
              
              <!-- Persona Selector -->
              <div v-if="personas.length > 0" class="mb-12">
                <div class="flex items-center justify-between mb-4">
                  <p class="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em]">Select Persona</p>
                  <router-link to="/personas" class="text-[10px] font-bold text-zinc-500 hover:text-white transition-colors">MANAGE</router-link>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button 
                    :class="['p-4 rounded-xl border text-left transition-all group', !selectedPersonaId ? 'bg-white border-white text-black shadow-xl shadow-white/5' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700']"
                    @click="selectedPersonaId = null"
                  >
                    <div class="text-[13px] font-bold uppercase tracking-tight">Default Agent</div>
                    <div :class="['text-[11px] mt-1', !selectedPersonaId ? 'text-black/60' : 'text-zinc-500 group-hover:text-zinc-400']">Standard autonomous assistant</div>
                  </button>
                  <button 
                    v-for="p in personas" 
                    :key="p.id"
                    :class="['p-4 rounded-xl border text-left transition-all group', selectedPersonaId === p.id ? 'bg-white border-white text-black shadow-xl shadow-white/5' : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700']"
                    @click="selectedPersonaId = p.id"
                  >
                    <div class="text-[13px] font-bold uppercase tracking-tight truncate">{{ p.name }}</div>
                    <div :class="['text-[11px] mt-1 truncate', selectedPersonaId === p.id ? 'text-black/60' : 'text-zinc-500 group-hover:text-zinc-400']">{{ p.description || 'Custom personality' }}</div>
                  </button>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <button
                  v-for="s in suggestions" :key="s.text"
                  class="p-4 rounded-xl border border-zinc-800 bg-zinc-950/50 hover:bg-zinc-800 hover:border-zinc-700 transition-all text-left group"
                  @click="input = s.prompt"
                >
                  <div class="text-[13px] font-semibold text-zinc-200 group-hover:text-white">{{ s.text }}</div>
                  <div class="text-[11px] text-zinc-500 mt-1">{{ s.sub }}</div>
                </button>
              </div>

              <div class="mt-6 flex justify-center">
                <button
                  class="flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-100 hover:border-zinc-500 transition-all text-xs font-medium"
                  @click="showTemplates = true"
                >
                  <Sparkles class="w-3.5 h-3.5" />
                  Browse Templates
                </button>
              </div>
            </div>
          </div>

          <!-- Message Blocks -->
          <div
            v-for="(msg, idx) in visibleMessages"
            :id="msg.id ? `msg-${msg.id}` : undefined"
            :key="idx"
            class="flex flex-col gap-4 animate-in fade-in duration-700"
          >
            <!-- Sender Label -->
            <div class="flex items-center gap-3 select-none">
              <div
                :class="['w-5 h-5 rounded-sm flex items-center justify-center text-[9px] font-bold tracking-tighter', 
                msg.role === 'ai' ? 'bg-white text-black' : 'bg-zinc-800 text-zinc-400']">
                {{ msg.role === 'ai' ? 'JARVIS' : (auth.displayName?.[0] || 'U') }}
              </div>
              <span class="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{{ msg.role === 'ai' ? 'Autonomous Agent' : 'User' }}</span>
            </div>

            <!-- Content Column -->
            <div class="pl-8 group relative min-h-[20px]">
              <div v-if="msg.image_urls && msg.image_urls.length > 0" class="flex flex-wrap gap-2 mb-2">
                <img v-for="(img, imgIdx) in msg.image_urls" :key="imgIdx" :src="img" class="max-w-[300px] max-h-[300px] object-contain rounded-md border border-zinc-700/50" />
              </div>
              
              <div v-if="editingMessageId === msg.id" class="space-y-2">
                <textarea
                  v-model="editInput"
                  class="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-[14px] text-zinc-100 focus:ring-1 focus:ring-white/20 focus:border-zinc-600 outline-none min-h-[100px] resize-none"
                ></textarea>
                <div class="flex gap-2 justify-end">
                  <button class="px-3 py-1.5 text-[11px] font-bold text-zinc-400 hover:text-zinc-200 transition-colors" @click="cancelEdit">CANCEL</button>
                  <button class="px-3 py-1.5 text-[11px] font-bold bg-white text-black rounded hover:bg-zinc-200 transition-all" @click="handleEditSubmit(msg)">SUBMIT</button>
                </div>
              </div>
              <div v-else class="markdown-body text-zinc-200 leading-[1.7] text-[14px]" v-html="renderMarkdown(msg.content)"></div>

              <!-- RAG Sources -->
              <template v-for="(ragSources, _ri) in [getRagSources(msg)]" :key="'rag-' + _ri + '-' + msg.id">
                <div v-if="msg.role === 'ai' && ragSources.length > 0" class="mt-2 border-t border-zinc-800 pt-2">
                  <button
                    class="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
                    @click="toggleSources(msg.id!)"
                  >
                    <ChevronDown
                      class="w-3 h-3 transition-transform duration-200"
                      :class="openSources.has(msg.id!) ? 'rotate-180' : ''"
                    />
                    {{ ragSources.length }} source{{ ragSources.length > 1 ? 's' : '' }}
                  </button>
                  <div v-if="msg.id && openSources.has(msg.id)" class="mt-2 space-y-2">
                    <div
                      v-for="(src, si) in ragSources"
                      :key="si"
                      class="rounded-md bg-zinc-800/50 border border-zinc-700/40 p-2.5 text-xs"
                    >
                      <div class="text-zinc-200 font-medium mb-0.5">{{ src.name }}</div>
                      <div class="text-zinc-500 text-[11px] mb-1">{{ Math.round(src.score * 100) }}% relevance</div>
                      <div class="text-zinc-400 line-clamp-3">{{ src.snippet }}</div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Human message timestamp -->
              <div v-if="msg.role === 'human' && msg.created_at" class="mt-2 text-[10px] text-zinc-700 select-none text-right">
                {{ formatMsgTime(msg.created_at) }}
              </div>

              <!-- Message Actions (Human) -->
              <div v-if="msg.role === 'human' && !editingMessageId" class="absolute -top-1 -right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Edit" @click="startEdit(msg)">
                  <SquarePen class="w-3 h-3" />
                </button>
                <button v-if="msg.id && !chat.streaming" class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500 hover:text-red-400" title="Delete" @click="handleDeleteMessage(msg.id)">
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>

              <!-- HITL Security Box -->
              <div v-if="msg.pending_tool_call" class="mt-8 p-6 bg-zinc-950 border border-white/10 rounded-lg space-y-5 max-w-md shadow-2xl">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2 text-[9px] font-black text-white tracking-[0.2em]">
                    <ShieldAlert class="w-3.5 h-3.5" />
                    CONFIRM EXECUTION
                  </div>
                  <span
                    class="text-[10px] font-mono tabular-nums"
                    :class="approvalRemainingSeconds <= 30 ? 'text-red-400 animate-pulse' : 'text-zinc-500'"
                  >{{ formatCountdown(approvalRemainingSeconds) }}</span>
                </div>
                <div class="text-[13px] text-zinc-300">Target action: <code class="bg-zinc-800 text-white px-1.5 py-0.5 rounded font-mono">{{ msg.pending_tool_call.name }}</code></div>
                <div class="flex gap-2">
                  <button class="flex-1 py-2.5 bg-white text-black rounded text-[11px] font-bold hover:bg-zinc-200 transition-all" @click="chat.handleConsent(true)">APPROVE</button>
                  <button class="flex-1 py-2.5 bg-zinc-900 text-zinc-400 border border-zinc-800 rounded text-[11px] font-bold hover:bg-zinc-800 transition-all" @click="chat.handleConsent(false)">REJECT</button>
                </div>
              </div>

              <!-- Message Footer: Branch Nav & Actions -->
              <div v-if="msg.id" class="mt-3 flex items-center gap-4 text-zinc-500">
                <!-- Branch Switcher -->
                <div v-if="chat.getSiblings(msg).length > 1" class="flex items-center gap-1.5 bg-zinc-900/50 rounded-full px-2 py-0.5 border border-zinc-800/50">
                  <button 
                    class="hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-500 transition-colors" 
                    :disabled="getBranchIndex(msg) === 0"
                    @click="navigateBranch(msg, -1)"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                  </button>
                  <span class="text-[9px] font-medium tabular-nums text-zinc-400">{{ getBranchIndex(msg) + 1 }} / {{ chat.getSiblings(msg).length }}</span>
                  <button 
                    class="hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-500 transition-colors" 
                    :disabled="getBranchIndex(msg) === chat.getSiblings(msg).length - 1"
                    @click="navigateBranch(msg, 1)"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                  </button>
                </div>

                <!-- AI Specific: Regenerate -->
                <button 
                  v-if="msg.role === 'ai' && !chat.streaming" 
                  class="text-[10px] font-medium hover:text-zinc-300 flex items-center gap-1.5 transition-colors" 
                  @click="chat.regenerate(msg.id, activeModel ?? undefined)"
                >
                  <RotateCcw class="w-3 h-3" />
                  Regenerate
                </button>
              </div>
              
              <!-- Tool Execution Logs -->
              <div v-if="msg.toolCalls?.length" class="mt-6 flex flex-col gap-2 pt-4 border-t border-zinc-800/50">
                <details v-for="(tc, i) in msg.toolCalls" :key="i" class="group bg-zinc-950/80 border border-zinc-800/80 rounded-xl overflow-hidden text-xs transition-all">
                  <summary class="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-zinc-900 transition-colors select-none marker:content-['']">
                    <div :class="['w-1.5 h-1.5 rounded-full flex-shrink-0 shadow-[0_0_8px_rgba(255,255,255,0.5)]', tc.status === 'running' ? 'bg-amber-400 animate-pulse shadow-amber-400/50' : 'bg-emerald-500 shadow-emerald-500/50']"></div>
                    <span class="font-mono text-zinc-300 font-semibold tracking-tight">{{ tc.name }}</span>
                    <span class="text-zinc-600 truncate flex-1 font-mono text-[10px]">{{ tc.args ? JSON.stringify(tc.args).substring(0, 50) + (JSON.stringify(tc.args).length > 50 ? '...' : '') : '' }}</span>
                    
                    <div class="flex items-center gap-2">
                      <span class="text-zinc-500 text-[9px] uppercase tracking-widest font-bold">{{ tc.status === 'running' ? 'Executing' : 'Completed' }}</span>
                      <svg class="w-3.5 h-3.5 text-zinc-500 transform transition-transform group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </div>
                  </summary>
                  
                  <div class="px-4 py-4 bg-[#0a0a0a] border-t border-zinc-800/80">
                    <div class="mb-2 flex items-center gap-2 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                      <Zap class="w-3 h-3" /> Payload
                    </div>
                    <pre class="text-zinc-300 font-mono text-[11px] bg-zinc-900/40 p-3 rounded-lg border border-zinc-800/50 overflow-x-auto whitespace-pre-wrap leading-relaxed">{{ tc.args ? JSON.stringify(tc.args, null, 2) : '{}' }}</pre>
                    
                    <div v-if="tc.result" class="mt-5">
                      <div class="mb-2 flex items-center gap-2 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                        <PanelLeft class="w-3 h-3" /> Output / Response
                      </div>
                      <pre class="text-zinc-300 font-mono text-[11px] bg-zinc-900/40 p-3 rounded-lg border border-zinc-800/50 overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto leading-relaxed custom-scrollbar">{{ tc.result }}</pre>
                    </div>
                  </div>
                </details>
              </div>

              <!-- Message metadata (model, tokens, timestamp) -->
              <div
                v-if="msg.role === 'ai' && (msg.model_name || msg.created_at)"
                class="mt-3 flex items-center gap-2 text-[10px] text-zinc-600 select-none"
              >
                <template v-if="msg.model_name">
                  <span class="font-mono">{{ msg.model_name }}</span>
                  <template v-if="msg.tokens_input != null || msg.tokens_output != null">
                    <span>·</span>
                    <span>{{ (msg.tokens_input ?? 0) + (msg.tokens_output ?? 0) }} tokens</span>
                  </template>
                </template>
                <template v-if="msg.created_at">
                  <span v-if="msg.model_name">·</span>
                  <span>{{ formatMsgTime(msg.created_at) }}</span>
                </template>
              </div>

              <!-- Message Actions -->
              <div v-if="msg.role === 'ai' && msg.content" class="absolute -bottom-8 left-8 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Copy" @click="copyToClipboard(msg.content)">
                  <Copy class="w-3 h-3" />
                </button>
                <button
                  v-if="msg.id && !chat.streaming"
                  class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
                  :class="msg.user_rating === 1 ? 'text-emerald-400' : 'text-zinc-500'"
                  title="Good response"
                  @click="handleRateMessage(msg.id, msg.user_rating === 1 ? null : 1)"
                >
                  <ThumbsUp class="w-3 h-3" />
                </button>
                <button
                  v-if="msg.id && !chat.streaming"
                  class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
                  :class="msg.user_rating === -1 ? 'text-red-400' : 'text-zinc-500'"
                  title="Bad response"
                  @click="handleRateMessage(msg.id, msg.user_rating === -1 ? null : -1)"
                >
                  <ThumbsDown class="w-3 h-3" />
                </button>
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" title="Regenerate" @click="regenerate(msg)">
                  <RotateCcw class="w-3 h-3" />
                </button>
                <button class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500" :class="{ 'text-emerald-400': isPlayingTTS === msg.content }" title="Read Aloud" @click="playTTS(msg.content)">
                  <Volume2 class="w-3 h-3" />
                </button>
                <button
                  v-if="msg.id && !chat.streaming"
                  class="p-1.5 hover:bg-zinc-800 rounded transition-colors"
                  :class="msg.is_bookmarked ? 'text-amber-400' : 'text-zinc-500'"
                  :title="msg.is_bookmarked ? 'Remove bookmark' : 'Bookmark'"
                  @click="handleToggleBookmark(msg.id)"
                >
                  <BookmarkCheck v-if="msg.is_bookmarked" class="w-3 h-3" />
                  <Bookmark v-else class="w-3 h-3" />
                </button>
                <button v-if="msg.id && !chat.streaming" class="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-500 hover:text-red-400" title="Delete" @click="handleDeleteMessage(msg.id)">
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>

          <!-- Typing Pulse -->
          <div v-if="chat.streaming" class="flex items-center gap-2 pl-8 py-4">
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse"></div>
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse [animation-delay:0.2s]"></div>
            <div class="w-1 h-1 bg-white/40 rounded-full animate-pulse [animation-delay:0.4s]"></div>
            <span
              v-if="chat.routingAgent"
              class="ml-1 text-[9px] font-bold text-zinc-500 uppercase tracking-widest px-2 py-0.5 bg-zinc-800 rounded-full"
            >{{ agentLabel(chat.routingAgent) }}</span>
          </div>
        </div>
      </div>
      </div>

      <!-- Footer Dock -->
      <div class="w-full bg-zinc-900 pt-2">
        <div class="max-w-3xl mx-auto px-6 pb-10">
          <div class="relative bg-zinc-950 border border-zinc-800 rounded-xl transition-all focus-within:border-zinc-700">
            <!-- Image Previews -->
            <div v-if="selectedImages.length > 0" class="flex flex-wrap gap-2 px-4 pt-3 pb-1">
              <div v-for="(img, idx) in selectedImages" :key="idx" class="relative group">
                <img :src="img" class="w-14 h-14 object-cover rounded-md border border-zinc-800" />
                <button 
                  class="absolute -top-1.5 -right-1.5 bg-zinc-900 text-zinc-400 rounded-full p-0.5 border border-zinc-800 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
                  @click="removeImage(idx)"
                >
                  <X class="w-3 h-3" />
                </button>
              </div>
            </div>

            <div class="flex items-end p-2 gap-1">
              <input 
                ref="fileInput" 
                type="file" 
                class="hidden" 
                multiple 
                accept="image/*" 
                @change="handleImageSelect" 
              />
              <button class="p-2.5 text-zinc-500 hover:text-white transition-colors" title="Attach Image" @click="fileInput?.click()">
                <Image class="w-4 h-4" />
              </button>
              <button class="p-2.5 text-zinc-500 hover:text-white transition-colors" @click="voiceOverlay?.start()">
                <Mic class="w-4 h-4" />
              </button>
              <button
                class="p-2.5 text-zinc-500 hover:text-white transition-colors"
                title="Prompt Templates"
                @click="showTemplates = true"
              >
                <Sparkles class="w-4 h-4" />
              </button>
              
              <textarea
                v-model="input"
                class="flex-1 bg-transparent border-none focus:ring-0 px-2 py-3 text-[14px] text-zinc-100 resize-none max-h-[300px] min-h-[44px] custom-scrollbar placeholder:text-zinc-600"
                :placeholder="$t('chat.inputPlaceholder')"
                rows="1"
                @keydown.enter="handleEnter"
                @paste="handlePaste"
              ></textarea>
              
              <!-- Stop button during streaming -->
              <button
                v-if="chat.streaming"
                class="p-2.5 bg-zinc-800 text-white rounded-lg transition-all active:scale-95 hover:bg-zinc-700"
                :title="$t('chat.stopGenerating')"
                @click="chat.cancelStream()"
              >
                <Square class="w-4 h-4" />
              </button>
              <!-- Send button otherwise -->
              <button
                v-else
                :disabled="!input.trim()"
                class="p-2.5 bg-white text-black rounded-lg disabled:opacity-10 transition-all active:scale-95"
                @click="handleSend"
              >
                <ArrowUp class="w-4 h-4 stroke-[3px]" />
              </button>
            </div>
          </div>
          <div class="mt-4 flex justify-center items-center gap-4 text-[9px] font-bold text-zinc-600 uppercase tracking-widest">
            <!-- Model picker -->
            <div v-if="availableModels.length > 1" class="relative">
              <button
                class="flex items-center gap-1 hover:text-zinc-400 transition-colors"
                :class="activeModel ? 'text-indigo-500' : ''"
                @click="showModelPicker = !showModelPicker"
              >
                <Cpu class="w-2.5 h-2.5" />
                {{ activeModel || userDefaultModel || 'Default' }}
                <ChevronDown class="w-2.5 h-2.5" />
              </button>
              <!-- Dropdown -->
              <div
                v-if="showModelPicker"
                class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-50 py-1 min-w-[180px]"
              >
                <button
                  v-if="activeModel"
                  class="w-full text-left px-3 py-1.5 text-[11px] text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
                  @click="activeModel = null; showModelPicker = false"
                >
                  ↩ Use default ({{ userDefaultModel }})
                </button>
                <button
                  v-for="m in availableModels"
                  :key="m"
                  class="w-full text-left px-3 py-1.5 text-[11px] transition-colors"
                  :class="(activeModel || userDefaultModel) === m ? 'text-indigo-400 bg-zinc-800' : 'text-zinc-300 hover:bg-zinc-800'"
                  @click="activeModel = m === userDefaultModel ? null : m; showModelPicker = false"
                >
                  {{ m }}
                </button>
              </div>
            </div>
            <div v-if="availableModels.length > 1" class="w-1 h-1 bg-zinc-800 rounded-full"></div>
            <span>{{ $t('chat.enterpriseGuard') }}</span>
            <div class="w-1 h-1 bg-zinc-800 rounded-full"></div>
            <span>{{ $t('chat.encrypted') }}</span>
          </div>
        </div>
      </div>
    </main>

    <!-- Right Sidebar for Live Canvas -->
    <LiveCanvas 
      :content="activeCanvasContent" 
      :is-visible="canvasVisible" 
      :collapsed="canvasCollapsed" 
      @close="canvasVisible = false"
      @submit="handleCanvasSubmit"
    />

    <VoiceOverlay ref="voiceOverlay" />

    <PromptTemplateModal
      v-if="showTemplates"
      @close="showTemplates = false"
      @select="applyTemplate"
    />

    <!-- Export menu close backdrop -->
    <div v-if="exportMenuConvId" class="fixed inset-0 z-40" @click="exportMenuConvId = null" />
    <!-- Model picker close backdrop -->
    <div v-if="showModelPicker" class="fixed inset-0 z-40" @click="showModelPicker = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";
import { marked } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";
import { sanitizeHtml } from "@/utils/sanitizeHtml";

import {
  Trash2, Zap, Settings, LogOut,
  PanelLeft, SquarePen, Copy, RotateCcw,
  Mic, ArrowUp, Square, ShieldAlert, Share2, MessageSquare,
  Volume2, Layout, Image, X, ChevronDown, Cpu,
  Search, Download, Sparkles, Pin, Bookmark, BookmarkCheck, ThumbsUp, ThumbsDown,
  Tag, Plus, GitFork
} from "lucide-vue-next";

import LiveCanvas from "@/components/LiveCanvas.vue";
import VoiceOverlay from "@/components/VoiceOverlay.vue";
import PromptTemplateModal from "@/components/PromptTemplateModal.vue";
import type { PromptTemplate } from "@/data/prompt-templates";
import client from "@/api/client";
import { searchConversations, exportConversation, patchConversation } from "@/api";
import { useToast } from "@/composables/useToast";

const { t, te } = useI18n();
const chat = useChatStore();
const auth = useAuthStore();
const router = useRouter();
const toast = useToast();
const visibleMessages = computed(() =>
  chat.activeMessages.filter((msg) => msg.role !== "tool"),
);

const input = ref("");
const editingMessageId = ref<string | null>(null);
const editInput = ref("");
const fileInput = ref<HTMLInputElement>();
const selectedImages = ref<string[]>([]);
const isMobile = ref(typeof window !== "undefined" ? window.innerWidth < 768 : false);
const sidebarCollapsed = ref(isMobile.value);

let resizeDebounce: ReturnType<typeof setTimeout> | undefined;
const handleResize = () => {
  clearTimeout(resizeDebounce);
  resizeDebounce = setTimeout(() => {
    const nowMobile = window.innerWidth < 768;
    if (nowMobile !== isMobile.value) {
      isMobile.value = nowMobile;
      if (!nowMobile) sidebarCollapsed.value = false;
    }
  }, 150);
};

const selectConversation = (convId: string) => {
  chat.selectConversation(convId);
  if (isMobile.value) sidebarCollapsed.value = true;
};

const selectSearchResult = (convId: string) => {
  chat.selectConversation(convId);
  clearSearch();
  if (isMobile.value) sidebarCollapsed.value = true;
};
const exportMenuConvId = ref<string | null>(null);
const pendingSystemPrompt = ref<string | null>(null);

// Model picker
const userDefaultModel = ref("");
const availableModels = ref<string[]>([]);
const activeModel = ref<string | null>(null); // null = use user default
const showModelPicker = ref(false);

// Search state
const searchMode = ref(false);
const searchQuery = ref("");
const searchResults = ref<Array<{ conv_id: string; title: string; snippet: string; updated_at: string }>>([]);
const searchInputEl = ref<HTMLInputElement>();

const clearSearch = () => {
  searchMode.value = false;
  searchQuery.value = "";
  searchResults.value = [];
};

// Bookmarks
interface BookmarkedMessage {
  id: string;
  conv_id: string;
  conv_title: string;
  role: string;
  content: string;
  created_at: string;
}
const bookmarkMode = ref(false);
const bookmarkedMessages = ref<BookmarkedMessage[]>([]);

// Tags
const activeTagFilter = ref<string | null>(null);
const tagInputConvId = ref<string | null>(null);
const tagInputValue = ref("");

const filteredConversations = computed(() =>
  activeTagFilter.value
    ? chat.conversations.filter((c) => c.tags.includes(activeTagFilter.value!))
    : chat.conversations,
);

const setTagFilter = (tag: string) => {
  activeTagFilter.value = activeTagFilter.value === tag ? null : tag;
};

const handleAddTag = async (convId: string) => {
  const tag = tagInputValue.value.trim();
  if (!tag) { tagInputConvId.value = null; return; }
  try {
    await chat.addTag(convId, tag);
  } catch {
    toast.error(t("chat.addTagError"));
  }
  tagInputValue.value = "";
  tagInputConvId.value = null;
};

const handleRemoveTag = async (convId: string, tag: string) => {
  try {
    await chat.removeTag(convId, tag);
    if (activeTagFilter.value === tag) activeTagFilter.value = null;
  } catch {
    toast.error(t("chat.removeTagError"));
  }
};

const toggleBookmarkMode = async () => {
  bookmarkMode.value = !bookmarkMode.value;
  if (bookmarkMode.value) {
    const { data } = await client.get<BookmarkedMessage[]>("/conversations/bookmarked");
    bookmarkedMessages.value = data;
  } else {
    bookmarkedMessages.value = [];
  }
};

const openBookmark = async (bm: BookmarkedMessage) => {
  bookmarkMode.value = false;
  await selectConversation(bm.conv_id);
  await nextTick();
  document.getElementById(`msg-${bm.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
};

const handleRateMessage = async (msgId: string, rating: 1 | -1 | null) => {
  try {
    await chat.rateMessage(msgId, rating);
  } catch {
    toast.error(t("chat.ratingError"));
  }
};

const handleToggleBookmark = async (msgId: string) => {
  const isNowBookmarked = await chat.toggleBookmark(msgId);
  if (isNowBookmarked === undefined) return; // store precondition not met
  if (!bookmarkMode.value) return;
  if (isNowBookmarked) {
    // Added: re-fetch to get conv_title
    const { data } = await client.get<BookmarkedMessage[]>("/conversations/bookmarked");
    bookmarkedMessages.value = data;
  } else {
    // Removed: filter locally (no network needed)
    bookmarkedMessages.value = bookmarkedMessages.value.filter((bm) => bm.id !== msgId);
  }
};

let searchTimer: ReturnType<typeof setTimeout> | undefined;

// HITL approval timeout
const APPROVAL_TIMEOUT_SECONDS = 300;
const approvalRemainingSeconds = ref(APPROVAL_TIMEOUT_SECONDS);
let approvalTickInterval: ReturnType<typeof setInterval> | undefined;

const formatCountdown = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
};

const calcRemaining = (pendingSince: number): number =>
  Math.max(0, APPROVAL_TIMEOUT_SECONDS - Math.floor((Date.now() - pendingSince) / 1000));

watch(
  () => chat.activeMessages.some((m) => !!m.pending_tool_call),
  (hasPending) => {
    if (hasPending && !approvalTickInterval) {
      const pendingMsg = chat.activeMessages.find((m) => m.pending_tool_call);
      if (!pendingMsg?.pending_tool_call) return;
      // Capture pendingSince once so the interval avoids per-second getter traversal
      const { pending_since: pendingSince } = pendingMsg.pending_tool_call;
      const initial = calcRemaining(pendingSince);
      approvalRemainingSeconds.value = initial;
      if (initial === 0) {
        chat.handleConsent(false).catch((e) => console.error("[chat] auto-deny failed", e));
        return;
      }
      approvalTickInterval = setInterval(() => {
        const remaining = calcRemaining(pendingSince);
        approvalRemainingSeconds.value = remaining;
        if (remaining === 0) {
          clearInterval(approvalTickInterval);
          approvalTickInterval = undefined;
          chat.handleConsent(false).catch((e) => console.error("[chat] auto-deny failed", e));
        }
      }, 1000);
    } else if (!hasPending) {
      if (approvalTickInterval) {
        clearInterval(approvalTickInterval);
        approvalTickInterval = undefined;
      }
      approvalRemainingSeconds.value = APPROVAL_TIMEOUT_SECONDS;
    }
  },
  { immediate: true },
);

const handleGlobalKeydown = (e: KeyboardEvent) => {
  const isMeta = e.metaKey || e.ctrlKey;
  // Ctrl/Cmd+K → open conversation search
  if (isMeta && e.key === "k") {
    e.preventDefault();
    if (sidebarCollapsed.value) sidebarCollapsed.value = false;
    searchMode.value = true;
    return;
  }
  // Escape → close search, share overlay, export dropdown, or sidebar on mobile
  if (e.key === "Escape") {
    if (showModelPicker.value) { showModelPicker.value = false; return; }
    if (searchMode.value) { clearSearch(); return; }
    if (shareUrl.value) { shareUrl.value = null; return; }
    if (exportMenuConvId.value) { exportMenuConvId.value = null; return; }
    if (isMobile.value && !sidebarCollapsed.value) { sidebarCollapsed.value = true; return; }
  }
};

onUnmounted(() => {
  clearTimeout(searchTimer);
  clearTimeout(resizeDebounce);
  clearTimeout(_scrollGuardTimer);
  cancelAnimationFrame(_scrollRafId);
  if (approvalTickInterval) clearInterval(approvalTickInterval);
  window.removeEventListener("resize", handleResize);
  window.removeEventListener("keydown", handleGlobalKeydown);
  messagesEl.value?.removeEventListener("click", handleCodeCopy);
});

watch(searchQuery, (q) => {
  if (searchTimer) clearTimeout(searchTimer);
  if (q.length < 2) {
    searchResults.value = [];
    return;
  }
  searchTimer = setTimeout(async () => {
    try {
      const resp = await searchConversations(q);
      searchResults.value = resp.data;
    } catch {
      /* ignore */
    }
  }, 300);
});

watch(searchMode, async (on) => {
  if (on) {
    await nextTick();
    searchInputEl.value?.focus();
  }
});

const downloadExport = async (convId: string, title: string, format: "md" | "json" | "txt") => {
  exportMenuConvId.value = null;
  try {
    const resp = await exportConversation(convId, format);
    const url = URL.createObjectURL(resp.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title}.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  } catch {
    toast.error(t("chat.exportError"));
  }
};

const togglePin = async (convId: string) => {
  try {
    await chat.togglePinConversation(convId);
  } catch {
    toast.error(t("chat.pinError"));
  }
};

// Inline conversation rename
const renamingConvId = ref<string | null>(null);
const renameValue = ref("");
// Plain mutable variable — Vue's :ref function ref sets this each render
 
let renameInputEl: HTMLInputElement | null = null;
const setRenameInput = (el: unknown) => { renameInputEl = el as HTMLInputElement | null; };

const startRename = (c: { id: string; title: string }) => {
  renamingConvId.value = c.id;
  renameValue.value = c.title;
  nextTick(() => renameInputEl?.select());
};

const commitRename = async (convId: string) => {
  // Guard: Escape already cleared renamingConvId (keydown fires before blur),
  // or Enter+blur causes double invocation — both are rejected here.
  if (renamingConvId.value !== convId) return;
  const title = renameValue.value.trim();
  renamingConvId.value = null;
  if (!title) {
    toast.error(t("chat.titleEmptyError"));
    return;
  }
  const conv = chat.conversations.find((c) => c.id === convId);
  if (!conv || title === conv.title) return;
  try {
    await chat.renameConversation(convId, title);
  } catch {
    toast.error(t("chat.renameError"));
  }
};

// Prompt template state
const showTemplates = ref(false);

const applyTemplate = async (template: PromptTemplate) => {
  showTemplates.value = false;
  if (chat.currentConvId) {
    try {
      await patchConversation(chat.currentConvId, { persona_override: template.system_prompt });
      toast.success(t("chat.templateApplied"));
    } catch {
      toast.error(t("chat.templateApplyError"));
    }
  } else {
    pendingSystemPrompt.value = template.system_prompt;
    toast.info(t("chat.templateAppliedNew"));
  }
};

const startEdit = (msg: any) => {
  editingMessageId.value = msg.id;
  editInput.value = msg.content;
};

const cancelEdit = () => {
  editingMessageId.value = null;
  editInput.value = "";
};

const handleEditSubmit = async (msg: any) => {
  const content = editInput.value;
  cancelEdit();
  await chat.sendMessage(content, undefined, msg.parent_id);
};

const getBranchIndex = (msg: any) => {
  const siblings = chat.getSiblings(msg);
  return siblings.findIndex(m => m.id === msg.id);
};

const navigateBranch = (msg: any, direction: number) => {
  const siblings = chat.getSiblings(msg);
  const currentIndex = siblings.findIndex(m => m.id === msg.id);
  const nextIndex = currentIndex + direction;
  if (nextIndex >= 0 && nextIndex < siblings.length) {
    chat.switchBranch(siblings[nextIndex].id!);
  }
};

const MAX_IMAGES = 4;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;

const addImages = (files: File[]) => {
  let accepted = 0;
  for (const file of files) {
    if (selectedImages.value.length + accepted >= MAX_IMAGES) {
      toast.error(t("chat.maxImagesError", { count: MAX_IMAGES }));
      break;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      toast.error(t("chat.imageTooLarge", { name: file.name }));
      continue;
    }
    accepted++;
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result && selectedImages.value.length < MAX_IMAGES) {
        selectedImages.value.push(ev.target.result as string);
      }
    };
    reader.readAsDataURL(file);
  }
};

const handleImageSelect = (e: Event) => {
  const files = (e.target as HTMLInputElement).files;
  if (!files) return;
  addImages(Array.from(files));
  if (fileInput.value) fileInput.value.value = '';
};

const handlePaste = (e: ClipboardEvent) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  const imageFiles: File[] = [];
  for (const item of Array.from(items)) {
    if (item.type.startsWith("image/")) {
      const file = item.getAsFile();
      if (file) imageFiles.push(file);
    }
  }
  if (imageFiles.length > 0) {
    e.preventDefault();
    addImages(imageFiles);
  }
};

const removeImage = (idx: number) => {
  selectedImages.value.splice(idx, 1);
};

const messagesEl = ref<HTMLElement>();
const voiceOverlay = ref<InstanceType<typeof VoiceOverlay>>();
const showScrollBtn = ref(false);

let _scrollRafId = 0;
let _programmaticScroll = false;
let _scrollGuardTimer = 0;
const onMessagesScroll = () => {
  if (_programmaticScroll) return;
  cancelAnimationFrame(_scrollRafId);
  _scrollRafId = requestAnimationFrame(() => {
    if (!messagesEl.value) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesEl.value;
    showScrollBtn.value = scrollHeight - scrollTop - clientHeight > 200;
  });
};

const formatMsgTime = (iso: string) => {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
};

// Share State
const shareUrl = ref<string | null>(null);
const sharing = ref(false);

// Personas State
const personas = ref<any[]>([]);
const selectedPersonaId = ref<string | null>(null);

const fetchPersonas = async () => {
  try {
    const { data } = await client.get("/personas");
    personas.value = data;
  } catch (err) {
    console.error("Failed to fetch personas:", err);
  }
};

const handleShare = async () => {
  if (!chat.currentConvId || sharing.value) return;
  sharing.value = true;
  try {
    const { data } = await client.post(`/conversations/${chat.currentConvId}/share`);
    const baseUrl = window.location.origin;
    shareUrl.value = `${baseUrl}/share/${data.token}`;
  } catch (err) {
    console.error("Failed to share:", err);
  } finally {
    sharing.value = false;
  }
};

const copyToClipboard = async function(text: string, successMsg = "Copied", errorMsg = "Failed to copy"): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(successMsg);
  } catch {
    toast.error(errorMsg);
  }
};

const copyShareUrl = async function(): Promise<void> {
  if (shareUrl.value) {
    await copyToClipboard(shareUrl.value, "Link copied", "Failed to copy link");
    setTimeout(() => {
      shareUrl.value = null;
    }, 3000);
  }
};

// Canvas State
const canvasVisible = ref(false);
const canvasCollapsed = ref(false);

const activeCanvasContent = computed(() => {
  // Find the latest message with HTML, Chart or Form
  const lastCanvasMsg = [...chat.messages].reverse().find(m => m.role === 'ai' && (hasHtml(m.content) || hasCanvasData(m.content)));
  return lastCanvasMsg ? lastCanvasMsg.content : "";
});

// Auto-open canvas when new content arrives
watch(activeCanvasContent, (newVal) => {
  if (newVal && !canvasVisible.value) {
    canvasVisible.value = true;
  }
});

const handleCanvasSubmit = async (values: any) => {
  await chat.sendMessage(`Form Submitted: ${JSON.stringify(values)}`);
};

const currentAudio = ref<HTMLAudioElement | null>(null);
const isPlayingTTS = ref<string | null>(null);

const playTTS = async function(text: string): Promise<void> {
  // If the same text is already playing, toggle pause
  if (isPlayingTTS.value === text && currentAudio.value) {
    currentAudio.value.pause();
    isPlayingTTS.value = null;
    return;
  }

  // Stop currently playing audio
  if (currentAudio.value) {
    currentAudio.value.pause();
  }

  try {
    isPlayingTTS.value = text;
    const cleanText = text
      .replace(/<[^>]*>?/gm, '')
      .replace(/[*#_`~[\]()]/g, '');

    const response = await client.post('/tts/synthesize', {
      text: cleanText.substring(0, 5000),
      voice: "zh-CN-XiaoxiaoNeural",
      rate: "+0%"
    }, {
      responseType: 'blob'
    });

    const audioUrl = URL.createObjectURL(response.data);
    const audio = new Audio(audioUrl);
    currentAudio.value = audio;

    audio.onended = () => {
      isPlayingTTS.value = null;
      URL.revokeObjectURL(audioUrl);
    };

    await audio.play();
  } catch (error) {
    console.error("TTS failed", error);
    isPlayingTTS.value = null;
  }
};

const agentLabel = (agent: string): string =>
  te(`chat.agents.${agent}`) ? t(`chat.agents.${agent}`) : agent;

const openSources = ref(new Set<string>());
const toggleSources = (msgId: string) => {
  const s = new Set(openSources.value);
  if (s.has(msgId)) s.delete(msgId);
  else s.add(msgId);
  openSources.value = s;
};

interface RagSource { name: string; score: number; snippet: string }

const RAG_SOURCE_RE = /\[(\d+)\] Document: "([^"]+)" \(relevance: ([\d.]+)\)\n([\s\S]*?)(?=\[\d+\] Document:|$)/g;

const getRagSources = (msg: { id?: string; role: string; tool_calls?: Array<{name: string; id?: string}> | null }): RagSource[] => {
  if (msg.role !== 'ai' || !msg.tool_calls) return [];
  const ragCall = msg.tool_calls.find((tc) => tc.name === 'rag_search');
  if (!ragCall) return [];

  const msgIdx = chat.messages.findIndex((m) => m.id === msg.id);
  if (msgIdx === -1) return [];

  const sources: RagSource[] = [];
  const re = new RegExp(RAG_SOURCE_RE.source, RAG_SOURCE_RE.flags);
  for (let i = msgIdx + 1; i < chat.messages.length; i++) {
    const m = chat.messages[i];
    if (m.role !== 'tool') break;
    re.lastIndex = 0;
    let match;
    while ((match = re.exec(m.content)) !== null) {
      sources.push({ name: match[2], score: parseFloat(match[3]), snippet: match[4].trim().slice(0, 150) });
    }
    break;
  }
  return sources;
};

const suggestions = [
  { text: 'Run Security Scan', sub: 'Audit current workspace structure', prompt: 'Run a proactive security check' },
  { text: 'Dynamic Canvas', sub: 'Generate interactive UI components', prompt: 'Show me a demo of Live Canvas' },
  { text: 'Deep Memory Search', sub: 'Search offline conversation logs', prompt: 'Search local memory for project roadmap' }
];

const escHtml = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

marked.use({
  breaks: true,
  renderer: {
    code({ text, lang }: { text: string; lang?: string }): string {
      const langLabel = lang ? `<span class="code-lang-label">${escHtml(lang)}</span>` : "";
      const highlighted = lang && hljs.getLanguage(lang)
        ? hljs.highlight(text, { language: lang }).value
        : hljs.highlightAuto(text).value;
      return `<div class="code-block-wrapper"><div class="code-block-header">${langLabel}<button class="copy-code-btn" aria-label="Copy code">Copy</button></div><pre><code class="hljs${lang ? ` language-${escHtml(lang)}` : ""}">${highlighted}</code></pre></div>\n`;
    },
  },
});

const renderMarkdown = (text: string) => {
  if (!text) return '<span class="cursor-block"></span>';
  
  let processed = text;
  const blocks: string[] = [];
  
  // Extract closed <think> blocks
  processed = processed.replace(/<think>([\s\S]*?)<\/think>/g, (_, p1) => {
    const placeholder = `__THINK_BLOCK_${blocks.length}__`;
    blocks.push(`<details class="my-3 group"><summary class="cursor-pointer text-xs font-semibold text-zinc-500 hover:text-zinc-300 transition-colors list-none flex items-center gap-2 select-none"><span class="w-5 h-5 rounded-full bg-zinc-800 flex items-center justify-center text-[10px]">🧠</span> <span>Thought Process</span></summary><div class="mt-3 pl-4 border-l-2 border-zinc-800 text-zinc-400 text-[13px] leading-relaxed opacity-80">${marked.parse(p1)}</div></details>`);
    return placeholder;
  });

  // Extract unclosed <think> block (streaming)
  const unclosedIndex = processed.indexOf('<think>');
  if (unclosedIndex !== -1) {
    const thinkingPart = processed.substring(unclosedIndex + 7);
    processed = processed.substring(0, unclosedIndex);
    const placeholder = `__THINK_BLOCK_${blocks.length}__`;
    blocks.push(`<details open class="my-3 group"><summary class="cursor-pointer text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors list-none flex items-center gap-2 select-none"><span class="w-5 h-5 rounded-full bg-indigo-500/20 flex items-center justify-center text-[10px] animate-pulse">🧠</span> <span>Thinking...</span></summary><div class="mt-3 pl-4 border-l-2 border-indigo-500/30 text-zinc-400 text-[13px] leading-relaxed opacity-80">${marked.parse(thinkingPart)}</div></details>`);
    processed += placeholder;
  }

  let html = marked.parse(processed) as string;

  blocks.forEach((blockHtml, i) => {
    html = html.replace(`<p>__THINK_BLOCK_${i}__</p>`, blockHtml);
    html = html.replace(`__THINK_BLOCK_${i}__`, blockHtml);
  });
  
  return sanitizeHtml(html);
};
const hasHtml = (text: string) => /<html>[\s\S]*?<\/html>/.test(text);
const hasCanvasData = (text: string) => {
  if (text.includes('"type": "chart"') || text.includes('"type": "form"')) return true;
  return false;
};
const currentConvTitle = computed(() => chat.conversations.find((conv) => conv.id === chat.currentConvId)?.title || "Intelligence Terminal");

const handleSend = async function(): Promise<void> {
  if ((!input.value.trim() && selectedImages.value.length === 0) || chat.streaming) return;
  const msg = input.value;
  const images = [...selectedImages.value];
  const personaId = selectedPersonaId.value;
  input.value = "";
  selectedImages.value = [];

  // Apply pending template system prompt when starting a new conversation
  if (pendingSystemPrompt.value && !chat.currentConvId) {
    const title = msg.slice(0, 30) + (msg.length > 30 ? "..." : "");
    const templatePrompt = pendingSystemPrompt.value;
    try {
      const { data } = await client.post("/conversations", { title });
      chat.conversations.unshift(data);
      chat.currentConvId = data.id;
      await patchConversation(data.id, { persona_override: templatePrompt });
      pendingSystemPrompt.value = null;
    } catch {
      toast.error(t("chat.templateApplyNewError"));
      // Restore so the user can retry without re-selecting the template
      pendingSystemPrompt.value = templatePrompt;
    }
  }

  await chat.sendMessage(msg, images.length > 0 ? images : undefined, undefined, personaId || undefined, activeModel.value || undefined);
};

const handleEnter = function(e: KeyboardEvent): void {
  // IME composition or Shift+Enter → allow newline
  if (e.isComposing || e.shiftKey) return;

  // Otherwise, send the message
  e.preventDefault();
  handleSend();
};

const handleDeleteMessage = async function(msgId: string): Promise<void> {
  if (!window.confirm(t("chat.deleteMessageConfirm"))) return;
  try {
    await chat.removeMessage(msgId);
  } catch {
    toast.error(t("chat.deleteMessageError"));
  }
};

const regenerate = async function(
  targetMsg: { id?: string; role: string; content: string },
): Promise<void> {
  const msgIndex = visibleMessages.value.findIndex(
    (msg) => msg === targetMsg || (targetMsg.id != null && msg.id === targetMsg.id),
  );
  if (msgIndex === -1) return;

  const prevHuman = visibleMessages.value.slice(0, msgIndex)
    .reverse()
    .find((m) => m.role === "human");
  if (prevHuman) {
    await chat.sendMessage(prevHuman.content);
  }
};

const handleLogout = function(): void {
  auth.logout();
  router.push("/login");
};

const scrollToBottom = async function(): Promise<void> {
  await nextTick();
  if (messagesEl.value) {
    _programmaticScroll = true;
    showScrollBtn.value = false;
    messagesEl.value.scrollTo({
      top: messagesEl.value.scrollHeight,
      behavior: "smooth"
    });
    // Re-enable scroll tracking after animation completes; cancel any prior timer
    clearTimeout(_scrollGuardTimer);
    _scrollGuardTimer = window.setTimeout(() => { _programmaticScroll = false; }, 400);
  }
};

const _copyTimers = new WeakMap<Element, number>();
const handleCodeCopy = (e: MouseEvent) => {
  const btn = (e.target as HTMLElement).closest(".copy-code-btn");
  if (!btn) return;
  const code = btn.closest(".code-block-wrapper")?.querySelector("pre code");
  if (!code) return;
  navigator.clipboard.writeText(code.textContent ?? "").then(() => {
    if (!btn.isConnected) return;
    btn.textContent = "Copied!";
    clearTimeout(_copyTimers.get(btn));
    _copyTimers.set(btn, window.setTimeout(() => {
      if (btn.isConnected) btn.textContent = "Copy";
    }, 2000));
  }).catch(() => {
    toast.error(t("chat.copyError"));
  });
};

watch(() => chat.messages.length, scrollToBottom);
watch(() => chat.streaming, (isStreaming) => { if (isStreaming) scrollToBottom(); });
watch(() => chat.currentConvId, () => { activeModel.value = null; });
async function loadModelOptions() {
  if (availableModels.value.length > 0) return; // already loaded this session
  try {
    const [settingsRes, modelsRes] = await Promise.all([
      client.get("/settings"),
      client.get<Record<string, string[]>>("/settings/models"),
    ]);
    const provider = settingsRes.data.model_provider ?? "";
    userDefaultModel.value = settingsRes.data.model_name ?? "";
    availableModels.value = modelsRes.data[provider] ?? [];
  } catch {
    // non-critical; fallback to no picker
  }
}

onMounted(async () => {
  window.addEventListener("resize", handleResize);
  window.addEventListener("keydown", handleGlobalKeydown);
  await nextTick();
  messagesEl.value?.addEventListener("click", handleCodeCopy);
  await chat.loadConversations();
  await Promise.all([fetchPersonas(), loadModelOptions()]);
});
</script>

<style scoped>
.markdown-body :deep(.code-block-wrapper) { position: relative; margin: 1.5rem 0; border: 1px solid #27272a; border-radius: 6px; overflow: hidden; }
.markdown-body :deep(.code-block-header) { display: flex; align-items: center; justify-content: space-between; background: #111; padding: 0.35rem 0.75rem; border-bottom: 1px solid #27272a; min-height: 28px; }
.markdown-body :deep(.code-lang-label) { font-family: 'JetBrains Mono', monospace; font-size: 0.7em; color: #71717a; text-transform: lowercase; }
.markdown-body :deep(.copy-code-btn) { margin-left: auto; font-size: 0.7em; font-weight: 600; color: #71717a; background: transparent; border: none; cursor: pointer; padding: 0.1rem 0.4rem; border-radius: 3px; transition: color 0.15s; }
.markdown-body :deep(.copy-code-btn:hover) { color: #e4e4e7; }
.markdown-body :deep(.code-block-wrapper pre) { background: #000; padding: 1.25rem; margin: 0; border-radius: 0; border: none; overflow-x: auto; }
.markdown-body :deep(pre) { background: #000; padding: 1.25rem; border-radius: 6px; margin: 1.5rem 0; border: 1px solid #27272a; overflow-x: auto; }
.markdown-body :deep(code) { font-family: 'JetBrains Mono', monospace; font-size: 0.85em; }
.markdown-body :deep(p) { margin-bottom: 1.5rem; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }

.cursor-block { display: inline-block; width: 6px; height: 14px; background: #fff; margin-left: 4px; animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #27272a; border-radius: 10px; }

details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }
</style>
