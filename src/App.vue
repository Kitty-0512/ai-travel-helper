<template>
  <div class="h-screen flex flex-col bg-gray-50 overflow-hidden">

    <!-- ==========================================
         Header（保持原样）
         ========================================== -->
    <header class="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-4 flex items-center gap-3 shadow-sm shrink-0">
      <button
        @click="sidebarOpen = !sidebarOpen"
        class="md:hidden text-3xl focus:outline-none"
      >
        ☰
      </button>
      <span class="text-3xl">✈️</span>
      <h1 class="text-2xl font-bold tracking-tight">AI 旅行助手</h1>
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
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">每日行程</h2>
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
                  <span class="text-yellow-500 shrink-0">🌅</span>
                  <span>{{ d.morning }}</span>
                </div>
                <div v-if="d.afternoon" class="flex gap-1">
                  <span class="text-orange-400 shrink-0">☀️</span>
                  <span>{{ d.afternoon }}</span>
                </div>
                <div v-if="d.evening" class="flex gap-1">
                  <span class="text-indigo-400 shrink-0">🌙</span>
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
            <span>✅</span>
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

        <!-- 底部按钮 -->
        <div class="mt-auto flex flex-col gap-3">
          <button
            @click="handleGenerate"
            :disabled="agent.state.loading || !destination || !days"
            class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors"
          >
            {{ agent.state.loading ? '⏳ 生成中...' : '🪄 生成行程' }}
          </button>

          <button
            @click="exportPDF"
            :disabled="!agent.state.cleanMarkdown"
            class="bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors"
          >
            📄 导出 PDF
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
import type { DonePayload } from './api/agent'
import { listSessions, getSession, deleteSession, type SessionSummary } from './api/sessions'

// ==========================================================
// 1. 三个 composable
// ==========================================================

const agent = useAgent()
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
const topPaneHeight = ref(430)
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
// 7. PDF 导出（保持原逻辑，打印源改为 AgentPanel 暴露的 printRef）
// ==========================================================

const exporting = ref(false)

function prepareExportClone(source: HTMLElement): { wrapper: HTMLDivElement; clone: HTMLElement } {
  const wrapper = document.createElement('div')
  wrapper.style.position = 'fixed'
  wrapper.style.left = '-100000px'
  wrapper.style.top = '0'
  wrapper.style.width = '800px'
  wrapper.style.background = '#ffffff'
  wrapper.style.zIndex = '-1'
  wrapper.style.pointerEvents = 'none'

  const clone = source.cloneNode(true) as HTMLElement
  clone.style.width = '800px'
  clone.style.height = 'auto'
  clone.style.maxHeight = 'none'
  clone.style.overflow = 'visible'
  clone.style.position = 'relative'
  clone.style.display = 'block'

  const elements = [clone, ...Array.from(clone.querySelectorAll<HTMLElement>('*'))]
  for (const node of elements) {
    node.style.maxHeight = 'none'
    node.style.overflow = 'visible'
    if (node.classList.contains('overflow-y-auto') || node.classList.contains('overflow-hidden')) {
      node.style.height = 'auto'
      node.style.minHeight = '0'
    }
  }

  wrapper.appendChild(clone)
  document.body.appendChild(wrapper)
  return { wrapper, clone }
}

async function exportPDF() {
  const printEl = agentPanelRef.value?.printRef as HTMLElement | null
  if (!printEl || exporting.value) return

  exporting.value = true
  let exportWrapper: HTMLDivElement | null = null

  try {
    const { wrapper, clone } = prepareExportClone(printEl)
    exportWrapper = wrapper
    await nextTick()
    await new Promise((r) => requestAnimationFrame(r))

    const canvas = await html2canvas(clone, {
      scale: 1,
      useCORS: true,
      backgroundColor: '#ffffff',
      scrollX: 0,
      scrollY: 0,
      width: 800,
      height: clone.scrollHeight,
      windowWidth: 800,
      windowHeight: clone.scrollHeight,
      logging: false,
    })
    wrapper.remove()
    exportWrapper = null

    // A4 分页（保持原逻辑）
    const pdf = new jsPDF('p', 'mm', 'a4')
    const pdfW = pdf.internal.pageSize.getWidth()
    const pdfH = pdf.internal.pageSize.getHeight()
    const ratio = pdfW / canvas.width
    const pageHeightPx = Math.floor(pdfH / ratio)

    let page = 0
    while (page * pageHeightPx < canvas.height) {
      if (page > 0) pdf.addPage()

      const srcY = page * pageHeightPx
      const srcH = Math.min(pageHeightPx, canvas.height - srcY)

      const pageCanvas = document.createElement('canvas')
      pageCanvas.width = canvas.width
      pageCanvas.height = srcH
      const ctx = pageCanvas.getContext('2d')!
      ctx.drawImage(canvas, 0, srcY, canvas.width, srcH, 0, 0, canvas.width, srcH)

      const imgData = pageCanvas.toDataURL('image/jpeg', 0.92)
      pdf.addImage(imgData, 'JPEG', 0, 0, pdfW, srcH * ratio)

      page++
    }

    pdf.save(`${destination.value || '旅行行程'}.pdf`)
  } catch (err) {
    console.error('PDF 导出失败:', err)
    alert('PDF 导出失败，请稍后重试')
  } finally {
    exportWrapper?.remove()
    exporting.value = false
  }
}
</script>
