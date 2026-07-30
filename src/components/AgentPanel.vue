<template>
  <div class="flex h-full flex-col overflow-hidden bg-white">
    <!-- ============================================
         空状态：还没生成过
         ============================================ -->
    <div
      v-if="!hasContent && !loading"
      class="flex-1 flex flex-col items-center justify-center text-gray-400 gap-3 p-8"
    >
      <span class="text-5xl">🗺️</span>
      <p class="text-base">在左侧填写目的地和天数，点击生成行程</p>
    </div>

    <!-- ============================================
         有内容时
         ============================================ -->
    <div v-else class="flex-1 flex flex-col overflow-hidden">
      <!-- ── 顶部状态条 ── -->
      <div
        v-if="loading || error || statusText"
        class="shrink-0 border-b px-6 py-3"
        :class="error ? 'bg-red-50 border-red-200' : 'bg-blue-50/70 border-blue-200'"
      >
        <div class="flex items-center gap-3">
          <span
            v-if="loading"
            class="inline-block h-4 w-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"
          ></span>
          <span v-else-if="error" class="text-lg">⚠️</span>
          <div class="min-w-0">
            <div class="text-[11px] uppercase tracking-[0.18em]" :class="error ? 'text-red-500' : 'text-blue-500'">
              {{ error ? 'Agent Error' : 'Current Action' }}
            </div>
            <div class="truncate text-sm font-medium" :class="error ? 'text-red-700' : 'text-blue-700'">
              {{ error ? error.message || error.code : statusText }}
            </div>
          </div>
          <button
            v-if="loading"
            @click="$emit('abort')"
            class="ml-auto rounded-full border border-blue-300 bg-white px-3 py-1 text-xs text-blue-600 transition-colors hover:bg-blue-100"
          >
            取消
          </button>
        </div>
      </div>

      <!-- ── 可折叠 / 工具调用区域 ── -->
      <div v-if="toolCalls.length > 0" class="shrink-0 border-b border-slate-200 bg-slate-50 px-6 py-3">
        <button
          @click="toolsExpanded = !toolsExpanded"
          class="flex w-full items-center gap-2 py-1 text-xs text-slate-500 transition-colors hover:text-slate-700"
        >
          <span class="transform transition-transform duration-200" :class="toolsExpanded ? 'rotate-90' : ''">
            ▶
          </span>
          <span>🔧 已调用 {{ toolCalls.length }} 个工具</span>
          <span v-if="!toolsExpanded" class="text-slate-400">
            （点击展开）
          </span>
        </button>

        <!-- 展开的工具列表 -->
        <div v-if="toolsExpanded" class="mt-3 grid max-h-48 gap-2 overflow-y-auto pb-1 md:grid-cols-2">
          <div
            v-for="(tc, idx) in toolCalls"
            :key="idx"
            class="flex items-start gap-2 rounded-xl px-3 py-2 text-xs ring-1 ring-inset"
            :class="tc.status === 'error'
              ? 'bg-red-50 text-red-700 ring-red-200'
              : tc.status === 'success'
                ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                : 'bg-blue-50 text-blue-700 ring-blue-200'"
          >
            <span class="shrink-0 mt-0.5">
              {{ tc.status === 'success' ? '✅' : tc.status === 'error' ? '❌' : '⏳' }}
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 font-medium">
                <span>{{ formatToolName(tc.tool) }}</span>
                <span v-if="tc.resultPreview?.is_fallback" class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
                  已降级
                </span>
                <span v-if="tc.duration" class="text-[10px] text-slate-400">
                  {{ formatDuration(tc.duration) }}
                </span>
              </div>
              <div class="truncate text-slate-500" :title="formatArgs(tc.args)">
                {{ formatArgs(tc.args) }}
              </div>
              <div v-if="tc.message" class="truncate text-slate-500">
                {{ tc.message }}
              </div>
              <div
                v-if="tc.resultPreview"
                class="mt-0.5 truncate text-slate-400"
                :title="formatResult(tc.resultPreview)"
              >
                {{ formatResult(tc.resultPreview) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Markdown 渲染区 ── -->
      <div
        ref="printRef"
        class="min-h-0 flex-1 overflow-y-auto bg-white p-8 prose prose-blue max-w-none"
      >
        <!-- 行程标题 -->
        <h2
          v-if="destination && days && cleanMarkdown"
          class="mb-6 text-2xl font-bold text-slate-800"
        >
          📅 {{ destination }} {{ days }} 天行程
        </h2>

        <!-- Markdown 内容（有内容就显示） -->
        <div
          v-if="cleanMarkdown"
          class="leading-relaxed text-slate-700"
          v-html="safeHtml"
        ></div>

        <!-- loading 中但还没内容时，显示等待提示 -->
        <div
          v-else-if="loading"
          class="flex flex-1 items-center justify-center text-slate-400"
        >
          <span class="animate-pulse">⏳ 等待 AI 响应...</span>
        </div>
      </div>

      <!-- ── 底部「继续修改」输入框 ── -->
      <div
        v-if="sessionId && !loading"
        class="shrink-0 border-t border-slate-200 bg-slate-50 px-6 py-4"
      >
        <div class="flex gap-2">
          <input
            v-model="chatInput"
            type="text"
            placeholder="对行程不满意？告诉我你想怎么改…（如：第三天太赶了、多加点博物馆）"
            class="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            :disabled="chatLoading"
            @keydown.enter="handleContinue"
          />
          <button
            @click="handleContinue"
            :disabled="!chatInput.trim() || chatLoading"
            class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors shrink-0"
          >
            {{ chatLoading ? '⏳' : '📨 发送' }}
          </button>
        </div>
        <p class="mt-1.5 text-xs text-slate-400">💡 试试："第二天太累了，减少一个景点" 或 "推荐一些美食"</p>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import { sanitizeHtml } from '@/utils/sanitize'
import type { ToolCallRecord } from '@/composables/useAgent'

// 强制 marked 以同步模式运行
marked.setOptions({ async: false } as Parameters<typeof marked.setOptions>[0])

// ============================================================
// Props
// ============================================================

const props = defineProps<{
  /** 是否正在生成 */
  loading: boolean
  /** 状态文字 */
  statusText: string
  /** 工具调用列表 */
  toolCalls: ToolCallRecord[]
  /** 消毒后的 Markdown 文本（或原始文本，由组件内部消毒） */
  cleanMarkdown: string
  /** 错误信息 */
  error: { code: string; message: string } | null
  /** 会话 ID（有值 = 已生成过行程） */
  sessionId: string
  /** 目的地 */
  destination: string
  /** 天数 */
  days: number
  /** 多轮对话加载中 */
  chatLoading?: boolean
}>()

// ============================================================
// Emits
// ============================================================

const emit = defineEmits<{
  /** 用户提交修改建议 */
  (e: 'continue', message: string): void
  /** 取消当前生成 */
  (e: 'abort'): void
}>()

// ============================================================
// 内部状态
// ============================================================

/** 工具列表折叠状态 */
const toolsExpanded = ref(false)

/** 多轮修改输入框 */
const chatInput = ref('')

/** 打印区域 ref */
const printRef = ref<HTMLElement | null>(null)

// ============================================================
// 计算属性
// ============================================================

/** Markdown HTML（Markdown → HTML → 消毒） */
const safeHtml = computed(() => {
  if (!props.cleanMarkdown) return ''
  try {
    const result = marked.parse(props.cleanMarkdown)
    // 防御：parse 不应返回 Promise（已设 async:false），但类型签名允许
    const html = typeof result === 'string' ? result : props.cleanMarkdown
    return sanitizeHtml(html)
  } catch {
    return sanitizeHtml(props.cleanMarkdown)
  }
})

/** 是否有内容需要展示 */
const hasContent = computed(() => {
  return props.cleanMarkdown || props.loading || props.error
})

// ============================================================
// 方法
// ============================================================

/** 处理发送修改建议 */
function handleContinue(): void {
  const msg = chatInput.value.trim()
  if (!msg) return
  emit('continue', msg)
  chatInput.value = ''
}

/** 格式化工具名（中文友好） */
function formatToolName(name: string): string {
  const map: Record<string, string> = {
    search_place: '搜索景点',
    search_pois: '搜索景点',
    get_weather: '查询天气',
    calculate_route: '规划路线',
    plan_route: '规划路线',
    geocode: '地理编码',
    search_flights: '搜索机票',
    search_hotels: '搜索酒店',
  }
  return map[name] || name
}

/** 格式化工具参数（简短摘要） */
function formatArgs(args: Record<string, unknown>): string {
  const parts: string[] = []
  if (args.city) parts.push(`📍 ${args.city}`)
  if (args.location) parts.push(`📍 ${args.location}`)
  if (args.keyword) parts.push(`关键词: ${args.keyword}`)
  if (args.category) parts.push(`类别: ${args.category}`)
  if (args.start && args.end) parts.push(`🚗 ${args.start} → ${args.end}`)
  if (args.origin && args.destination) parts.push(`🚗 ${args.origin} → ${args.destination}`)
  if (args.budget) parts.push(`预算: ${args.budget}`)
  return parts.length > 0 ? parts.join(' / ') : JSON.stringify(args).slice(0, 80)
}

/** 格式化工具结果（极简摘要） */
function formatResult(result: Record<string, unknown>): string {
  if (!result || Object.keys(result).length === 0) return ''
  if (result.error) return `错误: ${result.error}`
  if (result.pois_total !== undefined) return `找到 ${result.pois_total} 个景点`
  if (result.total !== undefined) return `共 ${result.total} 条结果`
  if (result.forecasts) {
    const f = result.forecasts as any[]
    return f.length > 0 ? `获取到 ${f.length} 天天气预报` : ''
  }
  if (result.flights) return `${(result.flights as any[]).length} 个航班可选`
  if (result.hotels) return `${(result.hotels as any[]).length} 家酒店可选`
  if (result.distance_text) return `${result.distance_text} / ${(result as any).duration_text || ''}`
  if (result.lng && result.lat) return `坐标: ${result.lng}, ${result.lat}`
  return ''
}

function formatDuration(duration?: number): string {
  if (!duration) return ''
  if (duration < 1000) return `${duration}ms`
  return `${(duration / 1000).toFixed(1)}s`
}

// ============================================================
// 暴露 printRef（给父组件用于 PDF 导出）
// ============================================================

defineExpose({ printRef })
</script>

<style scoped>
/* 保留 prose 全局样式，如果需要微调可在这里加 */
</style>
