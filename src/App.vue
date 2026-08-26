<template>
  <div class="h-screen flex flex-col bg-gray-50 overflow-hidden">

    <!-- ==========================================
         Header（保持原样）
         ========================================== -->
    <header class="bg-white border-b border-gray-200 text-gray-900 px-6 py-3.5 flex items-center gap-3 shrink-0">
      <button
        @click="sidebarOpen = !sidebarOpen"
        class="md:hidden text-xl focus:outline-none text-gray-600"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
      </svg>
      <h1 class="text-xl font-bold tracking-tight">Travel Planner</h1>
    </header>

    <div class="flex flex-1 overflow-hidden relative">

      <!-- ==========================================
           左侧面板（手机抽屉 + 桌面固定）—— 保持原样
           ========================================== -->
      <aside
        class="w-80 shrink-0 bg-white border-r flex flex-col gap-6 p-6 overflow-y-auto
               fixed md:relative inset-y-0 left-0 z-50
               transform transition-transform duration-300 ease-in-out
               md:translate-x-0"
        :class="{ 'translate-x-0': sidebarOpen, '-translate-x-full': !sidebarOpen }"
      >
        <!-- 目的地输入 -->
        <div class="flex flex-col gap-3">
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">目的地</h2>
          <input
            v-model="destination"
            type="text"
            placeholder="例如：北京、上海、长沙"
            :disabled="agent.state.loading"
            class="border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
          />
          <input
            v-model.number="days"
            type="number"
            min="1"
            max="14"
            placeholder="旅行天数（例如：5）"
            :disabled="agent.state.loading"
            class="border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
          />
        </div>

        <!-- 旅行风格 -->
        <div>
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">旅行风格</h2>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="style in travelStyles"
              :key="style"
              @click="toggleStyle(style)"
              :disabled="agent.state.loading"
              :class="[
                'px-3 py-1.5 rounded-full text-xs border transition-all',
                selectedStyles.includes(style)
                  ? 'bg-blue-500 text-white border-blue-500'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400',
                agent.state.loading ? 'opacity-50 cursor-not-allowed' : ''
              ]"
            >
              {{ style }}
            </button>
          </div>
        </div>

        <!-- 每日行程卡片（数据来自 useItinerary） -->
        <div v-if="itineraryData.days.length > 0">
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">行程详情</h2>
          <div class="flex flex-col gap-3">
            <div
              v-for="d in itineraryData.days"
              :key="d.day"
              class="rounded-lg border overflow-hidden"
            >
              <div
                class="px-3 py-1.5 text-xs font-bold text-white"
                :style="{ background: mapData.DAY_COLORS[(d.day - 1) % mapData.DAY_COLORS.length] }"
              >
                Day {{ d.day }}
              </div>
              <div class="px-3 py-2 flex flex-col gap-1 text-xs text-gray-700">
                <div v-if="d.morning" class="flex gap-1">
                  <span class="text-gray-400 shrink-0 font-medium">上午</span>
                  <span>{{ d.morning }}</span>
                </div>
                <div v-if="d.afternoon" class="flex gap-1">
                  <span class="text-gray-400 shrink-0 font-medium">下午</span>
                  <span>{{ d.afternoon }}</span>
                </div>
                <div v-if="d.evening" class="flex gap-1">
                  <span class="text-gray-400 shrink-0 font-medium">晚上</span>
                  <span>{{ d.evening }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 景点清单 + 路径优化 -->
        <div v-else-if="places.length > 0">
          <!-- 路径优化结果（数据来自 useMapData） -->
          <div
            v-if="mapData.optimization.value.hasOptimized"
            class="rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-700 flex items-center gap-1.5"
          >
            <span>路径已优化，节省约 <b>{{ mapData.optimization.value.savedKm }} 公里</b></span>
          </div>
          <div
            v-else-if="mapData.optimization.value.totalKm > 0 && !mapData.optimization.value.hasOptimized"
            class="rounded-lg bg-gray-50 border border-gray-200 px-3 py-2 text-xs text-gray-500"
          >
            当前顺序已是最优路线
          </div>

          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">景点清单</h2>
          <ul class="flex flex-col gap-1.5">
            <li
              v-for="(place, i) in places"
              :key="i"
              class="flex items-center gap-2 text-sm text-gray-700"
            >
              <span class="w-5 h-5 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs shrink-0">
                {{ i + 1 }}
              </span>
              {{ place }}
            </li>
          </ul>
        </div>

        <!-- 历史记录 -->
        <div v-if="historySessions.length > 0" class="flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">历史记录</h2>
            <button
              @click="historySessions = []"
              class="text-xs text-gray-400 hover:text-gray-600"
            >收起</button>
          </div>
          <div class="flex flex-col gap-1.5 max-h-40 overflow-y-auto">
            <div
              v-for="s in historySessions"
              :key="s.session_id"
              class="group flex items-center justify-between text-left text-xs p-2 rounded border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
              @click="loadHistory(s)"
            >
              <div class="flex flex-col gap-0.5 min-w-0">
                <span class="font-medium text-gray-700 truncate">
                  {{ s.destination }} · {{ s.days }}天
                </span>
                <span v-if="s.styles?.length" class="text-gray-400 text-[10px]">
                  {{ s.styles.join('、') }}
                </span>
              </div>
              <button
                @click.stop="removeHistory(s.session_id)"
                class="shrink-0 ml-1 p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all"
                title="删除记录"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Agent 流程豆豆（生成按钮上方） -->
        <div class="mt-auto flex flex-col gap-3">
          <div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
            <div class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Agent 执行流程
            </div>
            <div class="flex items-center justify-between gap-1">
              <template v-for="(s, idx) in flowSteps" :key="s.key">
                <div class="flex min-w-0 flex-1 flex-col items-center gap-1.5">
                  <div
                    class="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold transition-all"
                    :class="flowDotClass(idx)"
                  >
                    <span v-if="flowActiveIndex === idx && agent.state.loading" class="h-2.5 w-2.5 animate-pulse rounded-full bg-white"></span>
                    <span v-else-if="flowActiveIndex >= 5 || idx < flowActiveIndex">✓</span>
                    <span v-else>{{ idx + 1 }}</span>
                  </div>
                  <span
                    class="max-w-full truncate text-center text-[10px] leading-tight"
                    :class="idx <= flowActiveIndex ? 'font-medium text-slate-700' : 'text-slate-400'"
                  >{{ s.label }}</span>
                </div>
                  <div
                  v-if="idx < flowSteps.length - 1"
                  class="mb-4 h-0.5 w-2 shrink-0 rounded-full sm:w-3"
                  :class="idx < flowActiveIndex || flowActiveIndex >= 5 ? 'bg-blue-500' : 'bg-slate-200'"
                ></div>
              </template>
            </div>
            <p v-if="agent.state.statusText" class="mt-2 truncate text-[11px] text-blue-600" :title="agent.state.statusText">
              {{ agent.state.statusText }}
            </p>
          </div>

          <button
            @click="handleGenerate"
            :disabled="agent.state.loading || !destination || !days"
            class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors"
          >
            {{ agent.state.loading ? '生成中...' : '生成行程' }}
          </button>

          <button
            @click="exportPDF"
            :disabled="!agent.state.cleanMarkdown && !itineraryData.days.length"
            class="bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors"
          >
            导出 PDF
          </button>
        </div>
      </aside>

      <!-- ==========================================
           手机遮罩层（保持原样）
           ========================================== -->
      <div
        v-if="sidebarOpen"
        @click="sidebarOpen = false"
        class="fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity"
      ></div>

      <!-- ==========================================
           右侧内容 —— 核心改动区域
           ========================================== -->
      <main class="flex-1 min-h-0 overflow-hidden bg-slate-100/80">
        <div class="h-full p-4 md:p-5">
          <div class="h-full min-h-0 rounded-[28px] border border-white/70 bg-white/70 shadow-sm backdrop-blur">
            <div class="h-full min-h-0 p-3 md:p-4">
              <div
                ref="workspaceBodyRef"
                class="grid h-full min-h-0 gap-3"
                :style="{ gridTemplateRows: `${topPaneHeight}px 14px minmax(240px, 1fr)` }"
              >
                <section
                  class="min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
                >
                  <div class="h-full min-h-0">
                    <AgentPanel
                      ref="agentPanelRef"
                      :loading="agent.state.loading"
                      :statusText="agent.state.statusText"
                      :toolCalls="agent.state.toolCalls"
                      :cleanMarkdown="agent.state.cleanMarkdown"
                      :error="agent.state.error"
                      :sessionId="agent.state.sessionId"
                      :destination="destination"
                      :days="days || 0"
                      @continue="agent.continueGenerate"
                      @abort="agent.abort"
                    />
                  </div>
                </section>

                <div
                  class="relative h-[14px] cursor-row-resize"
                  @pointerdown="startResize"
                >
                  <div class="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-slate-200"></div>
                </div>

                <section class="min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                    <div>
                      <h3 class="text-sm font-semibold text-slate-800">地图与路线规划</h3>
                      <p class="text-xs text-slate-500">支持多日分组、路线重算和最短路径优化</p>
                    </div>
                    <div class="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                      {{ places.length > 0 ? `共 ${places.length} 个景点` : '暂无坐标数据' }}
                    </div>
                  </div>
                  <div class="h-[calc(100%-61px)] min-h-0 px-4 pb-4">
                    <Map
                      ref="mapRef"
                      :places="places"
                      :destination="destination"
                      :day-groups="dayGroups"
                    />
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<!-- ==============================================
     script setup —— 只做布局 + 组合 composables
     ============================================== -->
<script setup lang="ts">
import { ref, computed, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import Map from './components/Map.vue'
import AgentPanel from './components/AgentPanel.vue'
import { useAgent } from './composables/useAgent'
import { useItinerary } from './composables/useItinerary'
import { useMapData } from './composables/useMapData'
import html2canvas from 'html2canvas-pro'
import jsPDF from 'jspdf'
import { marked } from 'marked'
import { sanitizeHtml } from '@/utils/sanitize'
import type { DonePayload } from './api/agent'
import { listSessions, getSession, deleteSession, type SessionSummary } from './api/sessions'

// ==========================================================
// 1. 三个 composable
// ==========================================================

const agent = useAgent()

/** 生成按钮上方的流程豆豆：首次生成 + 多轮追问 */
const flowSteps = [
  { key: 'understand', label: '理解需求' },
  { key: 'tools', label: '调用工具' },
  { key: 'write', label: '生成行程' },
  { key: 'done', label: '完成' },
  { key: 'followup', label: '多轮追问' },
] as const

const flowActiveIndex = computed(() => {
  const s = agent.state
  if (s.phase === 'followup' || s.followupDone) {
    if (s.followupDone && !s.loading) return 5
    return 4
  }
  if (s.error && s.phase !== 'followup') return Math.min(s.step > 0 ? 1 : 0, 3)
  if (s.sessionId && (s.donePayload || s.cleanMarkdown) && !s.loading) return 3
  if (s.cleanMarkdown || s.itinerary) return 2
  if (s.toolCalls.length > 0) return 1
  if (s.loading || s.step > 0 || s.phase === 'generate') return 0
  return -1
})

function flowDotClass(idx: number): string {
  const active = flowActiveIndex.value
  const s = agent.state
  if (active >= 5) return 'bg-blue-500 text-white shadow-sm'
  if (idx < active) return 'bg-blue-500 text-white shadow-sm'
  if (idx === active && s.loading) return 'bg-blue-500 text-white ring-4 ring-blue-100'
  if (idx === active) return 'bg-blue-500 text-white'
  if (idx === 4 && active === 3 && s.sessionId) {
    return 'bg-white text-blue-500 ring-2 ring-dashed ring-blue-300'
  }
  return 'bg-white text-slate-400 ring-1 ring-slate-200'
}

const itinerary = useItinerary({
  itinerary: computed(() => agent.state.itinerary),
  donePayload: computed(() => agent.state.donePayload),
})
const mapData = useMapData()

// ==========================================================
// 2. 表单状态（保持原来的 ref）
// ==========================================================

const destination = ref('')
const days = ref<number>()
const travelStyles = ['美食', '历史文化', '自然风光', '购物', '艺术', '冒险']
const selectedStyles = ref<string[]>([])

function toggleStyle(style: string) {
  const idx = selectedStyles.value.indexOf(style)
  if (idx === -1) selectedStyles.value.push(style)
  else selectedStyles.value.splice(idx, 1)
}

// ==========================================================
// 历史记录
// ==========================================================

const historySessions = ref<SessionSummary[]>([])
const historyLoading = ref(false)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const res = await listSessions()
    historySessions.value = res.sessions || []
  } catch {
    historySessions.value = []
  } finally {
    historyLoading.value = false
  }
}

async function loadHistory(session: SessionSummary) {
  try {
    const detail = await getSession(session.session_id)
    destination.value = detail.destination
    days.value = detail.days || undefined
    selectedStyles.value = detail.styles || []

    agent.loadSession({
      sessionId: detail.session_id,
      destination: detail.destination,
      days: detail.days,
      styles: detail.styles,
      itinerary: detail.itinerary,
      placesDetail: detail.places_detail,
      markdownText: detail.markdown_text,
    })

    await nextTick()
    mapRef.value?.lockCity?.(detail.destination)
    if (detail.places_detail?.length) {
      mapRef.value?.seedCoords?.(detail.places_detail, detail.destination)
    }
  } catch (err) {
    console.error('加载历史会话失败:', err)
  }
}

async function removeHistory(sessionId: string) {
  try {
    await deleteSession(sessionId)
    historySessions.value = historySessions.value.filter((s) => s.session_id !== sessionId)
  } catch (err) {
    console.error('删除历史会话失败:', err)
  }
}

// 首次挂载和每次生成完成后刷新历史列表
onMounted(() => {
  fetchHistory()
})

watch(
  () => agent.state.sessionId,
  (newId) => {
    if (newId) fetchHistory()
  },
)

// ==========================================================
// 3. 子组件 ref
// ==========================================================

const agentPanelRef = ref<InstanceType<typeof AgentPanel> | null>(null)
const mapRef = ref<any>(null)
const workspaceBodyRef = ref<HTMLElement | null>(null)

// 手机侧边栏
const sidebarOpen = ref(false)
const topPaneHeight = ref(360)
const isResizing = ref(false)
let activePointerId: number | null = null

function clampTopPaneHeight(height: number): number {
  const containerHeight = workspaceBodyRef.value?.clientHeight ?? window.innerHeight
  const dividerHeight = 20
  const minTop = 260
  const minBottom = 240
  const maxTop = Math.max(minTop, containerHeight - minBottom - dividerHeight)
  return Math.min(Math.max(height, minTop), maxTop)
}

function handleResizeMove(event: PointerEvent): void {
  if (!isResizing.value) return
  if (activePointerId !== null && event.pointerId !== activePointerId) return
  const container = workspaceBodyRef.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  topPaneHeight.value = clampTopPaneHeight(event.clientY - rect.top)
}

function stopResize(): void {
  isResizing.value = false
  activePointerId = null
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  window.removeEventListener('pointermove', handleResizeMove)
  window.removeEventListener('pointerup', stopResize)
  window.removeEventListener('pointercancel', stopResize)
  nextTick(() => {
    mapRef.value?.resizeMap?.()
  })
}

function startResize(event: PointerEvent): void {
  event.preventDefault()
  isResizing.value = true
  activePointerId = event.pointerId
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'row-resize'
  window.addEventListener('pointermove', handleResizeMove)
  window.addEventListener('pointerup', stopResize)
  window.addEventListener('pointercancel', stopResize)
  handleResizeMove(event)
}

onBeforeUnmount(() => {
  stopResize()
})

// ==========================================================
// 4. 生成行程
// ==========================================================

function handleGenerate() {
  if (!destination.value || !days.value || days.value < 1) return
  sidebarOpen.value = false  // 手机友好：生成后自动收起

  // 立即锁定地图搜索城市，避免 itinerary_json 先到、PlaceSearch city 为空
  mapRef.value?.lockCity?.(destination.value)

  agent.startGenerate({
    destination: destination.value,
    days: days.value,
    styles: selectedStyles.value,
  })
}

// ==========================================================
// 5. 监听 Agent 完成 → 更新地图数据 & 定位
// ==========================================================

/** watch done 事件：有景点详情时直接给 tsp 优化；无则退到 Map 组件 geocode */
watch(
  () => agent.state.donePayload,
  async (done: DonePayload | null) => {
    if (!done) return

    // 如果后端返回了 coordinates（places_detail），直接用
    if (done.places_detail && done.places_detail.length >= 2) {
      mapData.setPlacesData(done.places_detail)
      // 预填坐标 + 用 done.destination 锁定城市，避免 PlaceSearch city 为空
      mapRef.value?.seedCoords?.(done.places_detail, done.destination || destination.value)
    }
    // 否则回退到 Map 组件的 geocode 方法（兼容旧逻辑）
    else if (places.value.length >= 2) {
      await nextTick()
      const coords = await mapRef.value?.getPlaceCoords?.(places.value)
      if (coords && coords.length >= 2) {
        mapData.setCoordsFromMap(coords, places.value)
      }
    }

    // 飞到目的地
    await nextTick()
    mapRef.value?.flyToDestination?.(destination.value)
  },
)

// ==========================================================
// 6. 快捷解构（模板用）
// ==========================================================

const { places, dayGroups, itineraryData } = itinerary

// ==========================================================
// 7. PDF 导出：规范 Markdown 结构 + 攻略风排版，再截图切 A4
// ==========================================================

marked.setOptions({ async: false } as Parameters<typeof marked.setOptions>[0])

const exporting = ref(false)
/** A4 @96dpi 约 794px 宽 */
const EXPORT_WIDTH = 794

/** emoji → 中文标签，避免 html2canvas 乱码，同时保留语义 */
function replaceEmojiForPdf(text: string): string {
  return text
    .replace(/🗺️/g, '')
    .replace(/🌅/g, '【上午】')
    .replace(/☀️/g, '【下午】')
    .replace(/🌙/g, '【晚上】')
    .replace(/📌/g, '')
    .replace(/🚇/g, '交通：')
    .replace(/🌤️/g, '天气：')
    .replace(/🎫/g, '门票：')
    .replace(/🍜/g, '美食：')
    .replace(/📸|🏛️/g, '')
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}]/gu, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** 把松散正文收成可排版的 Markdown（标题 / 列表） */
function normalizeMarkdownForPdf(raw: string): string {
  let text = replaceEmojiForPdf(raw || '')
  if (!text) return ''

  text = text.replace(
    /^好的[，,]?[\s\S]*?(?:现在为您生成行程|为您生成行程)[。.]?\s*/m,
    '',
  )
  text = text
    .split('\n')
    .filter((line) => {
      const t = line.trim()
      if (!t) return true
      if (/^好的[，,]/.test(t)) return false
      if (/已获取到.+天气预报/.test(t)) return false
      if (/现在为您生成行程/.test(t)) return false
      return true
    })
    .join('\n')
    .trim()

  const start = text.search(/^(#{1,3}\s|Day\s*\d|实用贴士)/im)
  if (start > 0) text = text.slice(start).trim()

  // 行级规范化：Day / 贴士 → 二级标题；时段 → 列表项
  text = text
    .split('\n')
    .map((line) => {
      let t = line.trimEnd()
      const s = t.trim()
      if (!s) return ''

      if (/^#{1,6}\s/.test(s)) return t

      const day = s.match(/^Day\s*(\d+)\s*[：:·\-]?\s*(.*)$/i)
      if (day) {
        const theme = day[2].replace(/^[\-—–·\s]+/, '').trim()
        return theme ? `## Day ${day[1]}  ${theme}` : `## Day ${day[1]}`
      }

      if (/^实用贴士/.test(s)) {
        const rest = s.replace(/^实用贴士\s*[：:\-]?\s*/, '').trim()
        return rest ? `## 实用贴士\n\n- ${rest}` : '## 实用贴士'
      }

      const slot = s.match(/^(?:[-*•]\s*)?(?:【?\s*)?(上午|下午|晚上)(?:\s*】)?\s*[：:]\s*(.+)$/)
      if (slot) return `- **${slot[1]}**：${slot[2].trim()}`

      const labeled = s.match(/^(?:[-*•]\s*)?(交通|天气|门票|美食)\s*[：:]\s*(.+)$/)
      if (labeled) return `- **${labeled[1]}**：${labeled[2].trim()}`

      return t
    })
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return text
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function buildExportHtml(): string {
  const parts: string[] = []
  const dest = destination.value || '旅行'
  const dayCount = days.value || itineraryData.value.days.length || ''

  parts.push(`
    <header class="pdf-cover">
      <div class="pdf-eyebrow">Travel Planner</div>
      <h1 class="pdf-title">${escapeHtml(String(dest))} · ${escapeHtml(String(dayCount))} 天行程</h1>
      <div class="pdf-rule"></div>
    </header>
  `)

  const md = normalizeMarkdownForPdf(agent.state.cleanMarkdown || '')
  if (md) {
    const parsed = marked.parse(md)
    const html = sanitizeHtml(typeof parsed === 'string' ? parsed : md)
    parts.push(`<article class="pdf-body">${html}</article>`)
  } else if (itineraryData.value.days.length) {
    parts.push('<article class="pdf-body">')
    for (const d of itineraryData.value.days) {
      parts.push(`<h2>Day ${d.day}</h2><ul>`)
      if (d.morning) parts.push(`<li><strong>上午</strong>：${escapeHtml(d.morning)}</li>`)
      if (d.afternoon) parts.push(`<li><strong>下午</strong>：${escapeHtml(d.afternoon)}</li>`)
      if (d.evening) parts.push(`<li><strong>晚上</strong>：${escapeHtml(d.evening)}</li>`)
      parts.push('</ul>')
    }
    parts.push('</article>')
  }
  return parts.join('')
}

function createExportHost(): HTMLDivElement {
  const host = document.createElement('div')
  // 离屏定位隐藏；opacity 必须为 1，否则截图像「白纸/浅字」
  host.style.cssText = [
    'position:fixed',
    'left:-10000px',
    'top:0',
    `width:${EXPORT_WIDTH}px`,
    'box-sizing:border-box',
    'background:#ffffff',
    'color:#1e293b',
    'overflow:visible',
    'opacity:1',
    'pointer-events:none',
    'z-index:-1',
  ].join(';')
  host.innerHTML = buildExportHtml()

  const style = document.createElement('style')
  style.textContent = `
    .pdf-cover, .pdf-body {
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", system-ui, sans-serif;
      color: #1e293b;
    }
    .pdf-cover {
      padding: 36px 44px 20px;
      background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
      border-bottom: 1px solid #e2e8f0;
    }
    .pdf-eyebrow {
      font-size: 11px;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: #64748b;
      margin-bottom: 10px;
      font-weight: 600;
    }
    .pdf-title {
      margin: 0;
      font-size: 28px;
      line-height: 1.3;
      font-weight: 800;
      color: #0f172a !important;
    }
    .pdf-rule {
      margin-top: 16px;
      width: 56px;
      height: 4px;
      background: #2563eb;
      border-radius: 2px;
    }
    .pdf-body {
      padding: 28px 44px 48px;
      font-size: 14.5px;
      line-height: 1.85;
    }
    .pdf-body h1, .pdf-body h2, .pdf-body h3, .pdf-body h4 {
      color: #0f172a !important;
      font-weight: 750;
      line-height: 1.35;
      margin: 0 0 12px;
    }
    .pdf-body h1 { font-size: 22px; }
    .pdf-body h2 {
      font-size: 18px;
      margin-top: 28px;
      padding: 10px 14px;
      background: #f1f5f9;
      border-left: 4px solid #2563eb;
      border-radius: 0 8px 8px 0;
    }
    .pdf-body h2:first-child { margin-top: 0; }
    .pdf-body h3 { font-size: 16px; margin-top: 18px; }
    .pdf-body p {
      margin: 0 0 12px;
      color: #334155 !important;
    }
    .pdf-body ul, .pdf-body ol {
      margin: 0 0 16px;
      padding-left: 0;
      list-style: none;
    }
    .pdf-body li {
      position: relative;
      margin: 0 0 10px;
      padding: 10px 14px 10px 16px;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      color: #334155 !important;
    }
    .pdf-body strong {
      color: #0f172a !important;
      font-weight: 700;
    }
    .pdf-body hr {
      margin: 24px 0;
      border: none;
      border-top: 1px dashed #cbd5e1;
    }
  `
  host.prepend(style)
  document.body.appendChild(host)
  return host
}

/** 把整张 canvas 按 A4 可用高度切页写入 pdf */
function addCanvasAsPdfPages(
  pdf: jsPDF,
  canvas: HTMLCanvasElement,
  marginMm: number,
) {
  const pdfW = pdf.internal.pageSize.getWidth()
  const pdfH = pdf.internal.pageSize.getHeight()
  const usableW = pdfW - marginMm * 2
  const usableH = pdfH - marginMm * 2

  const imgW = canvas.width
  const imgH = canvas.height
  // 一页 PDF 对应多少 canvas 像素高
  const pageHeightPx = Math.floor((usableH / usableW) * imgW)

  let rendered = 0
  let page = 0
  while (rendered < imgH - 1) {
    const sliceH = Math.min(pageHeightPx, imgH - rendered)
    const pageCanvas = document.createElement('canvas')
    pageCanvas.width = imgW
    pageCanvas.height = sliceH
    const ctx = pageCanvas.getContext('2d')!
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, imgW, sliceH)
    ctx.drawImage(canvas, 0, rendered, imgW, sliceH, 0, 0, imgW, sliceH)

    if (page > 0) pdf.addPage()
    const drawH = (sliceH / imgW) * usableW
    pdf.addImage(pageCanvas.toDataURL('image/jpeg', 0.93), 'JPEG', marginMm, marginMm, usableW, drawH)

    rendered += sliceH
    page++
    if (page > 40) break
  }
}

async function exportPDF() {
  const hasContent = agent.state.cleanMarkdown || itineraryData.value.days.length > 0
  if (!hasContent || exporting.value) return

  exporting.value = true
  let host: HTMLDivElement | null = null

  try {
    host = createExportHost()
    await nextTick()
    try {
      await (document as any).fonts?.ready
    } catch { /* ignore */ }
    // 强制两次布局，确保 scrollHeight 量全
    void host.offsetHeight
    await new Promise((r) => requestAnimationFrame(r))
    await new Promise((r) => setTimeout(r, 250))

    const totalH = Math.ceil(
      Math.max(
        host.scrollHeight,
        host.offsetHeight,
        host.clientHeight,
        host.getBoundingClientRect().height,
      ),
    )
    if (totalH < 10) {
      alert('暂无可导出的行程内容')
      return
    }

    // 一次截全图（scale=1 降低 canvas 上限风险），再用 drawImage 切页
    const canvas = await html2canvas(host, {
      scale: 1,
      useCORS: true,
      backgroundColor: '#ffffff',
      width: EXPORT_WIDTH,
      height: totalH,
      windowWidth: EXPORT_WIDTH,
      windowHeight: totalH,
      scrollX: 0,
      scrollY: 0,
      logging: false,
    })

    // 若截到的高度明显偏短，按内容块拆开再截（兜底）
    if (canvas.height < totalH * 0.85) {
      console.warn('[PDF] 整页截图偏短，改用分块导出', {
        totalH,
        canvasH: canvas.height,
      })
      await exportPdfByBlocks(host)
      return
    }

    const pdf = new jsPDF('p', 'mm', 'a4')
    addCanvasAsPdfPages(pdf, canvas, 10)
    pdf.save(`${destination.value || '旅行行程'}.pdf`)
  } catch (err) {
    console.error('PDF 导出失败:', err)
    alert('PDF 导出失败，请稍后重试')
  } finally {
    host?.remove()
    exporting.value = false
  }
}

/** 兜底：按内容子块逐块截图拼 PDF，避免超长 canvas 被裁 */
async function exportPdfByBlocks(host: HTMLDivElement) {
  const cover = host.querySelector('.pdf-cover') as HTMLElement | null
  const body = host.querySelector('.pdf-body') as HTMLElement | null

  const targets: HTMLElement[] = []
  if (cover) targets.push(cover)
  if (body) {
    const kids = Array.from(body.children).filter(
      (n): n is HTMLElement => n instanceof HTMLElement,
    )
    if (kids.length) targets.push(...kids)
    else targets.push(body)
  }

  const pdf = new jsPDF('p', 'mm', 'a4')
  const pdfW = pdf.internal.pageSize.getWidth()
  const pdfH = pdf.internal.pageSize.getHeight()
  const margin = 10
  const usableW = pdfW - margin * 2
  const usableH = pdfH - margin * 2
  let cursorY = margin
  let needNewPageHeader = true

  const newPage = () => {
    if (!needNewPageHeader) pdf.addPage()
    needNewPageHeader = false
    cursorY = margin
  }
  newPage()

  for (const el of targets) {
    const box = el.getBoundingClientRect()
    if (box.height < 2) continue

    const canvas = await html2canvas(el, {
      scale: 1,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
    })
    if (canvas.width < 2 || canvas.height < 2) continue

    const drawH = (canvas.height / canvas.width) * usableW

    if (drawH > usableH) {
      if (cursorY > margin + 1) newPage()
      addCanvasAsPdfPages(pdf, canvas, margin)
      needNewPageHeader = false
      cursorY = pdfH
      continue
    }

    if (cursorY + drawH > pdfH - margin) newPage()

    pdf.addImage(
      canvas.toDataURL('image/jpeg', 0.93),
      'JPEG',
      margin,
      cursorY,
      usableW,
      drawH,
    )
    cursorY += drawH + 3
  }

  pdf.save(`${destination.value || '旅行行程'}.pdf`)
}
</script>
