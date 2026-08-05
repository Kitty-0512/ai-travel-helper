/**
 * src/composables/useAgent.ts
 *
 * 职责：管理 AI Agent 的完整生命周期
 *   - 调用 generateItinerary / continueChat 发起 SSE 请求
 *   - 处理所有 SSE 事件，更新响应式状态
 *   - 支持 AbortController 取消
 *   - 支持多轮对话（continueGenerate）
 *
 * 暴露给 App.vue 的状态和方法：
 *   state        → 所有响应式状态
 *   startGenerate(params)  → 首次生成
 *   continueGenerate(msg)  → 多轮修改
 *   abort()      → 取消当前请求
 *   reset()      → 清空所有状态
 */

import { reactive } from 'vue'
import {
  generateItinerary,
  continueChat,
  type AgentSSEEvent,
  type GenerateParams,
  type ItineraryPayload,
  type DonePayload,
  type ToolCallPayload,
  type ToolResultPayload,
  type ErrorPayload,
} from '@/api/agent'

// ============================================================
// 类型
// ============================================================

/** 一条工具调用记录（tool_call 开始 → tool_result 结束） */
export interface ToolCallRecord {
  tool: string
  args: Record<string, unknown>
  message?: string
  resultPreview?: Record<string, unknown>
  /** 状态：running → success → error */
  status: 'running' | 'success' | 'error'
  /** 调用开始时间 */
  startTime: number
  duration?: number
}

/** 完整的 Agent 状态 */
export interface AgentState {
  /** 是否正在请求中 */
  loading: boolean
  /** 当前状态文字（如 "正在搜索北京的景点…"） */
  statusText: string
  /** 当前是第几步 */
  step: number
  /** LLM 流式输出的原始文本（含 JSON 块） */
  rawMarkdown: string
  /** 过滤 JSON 后的纯 Markdown 文本 */
  cleanMarkdown: string
  /** 本次所有工具调用记录 */
  toolCalls: ToolCallRecord[]
  /** itinerary_json 事件的结构化数据 */
  itinerary: ItineraryPayload | null
  /** done 事件的完整载荷 */
  donePayload: DonePayload | null
  /** 会话 ID（用于多轮修改） */
  sessionId: string
  /** 请求 ID（用于 trace 查询） */
  requestId: string
  /** 错误信息 */
  error: ErrorPayload | null
}

// ============================================================
// 初始状态工厂
// ============================================================

function createInitialState(): AgentState {
  return {
    loading: false,
    statusText: '',
    step: 0,
    rawMarkdown: '',
    cleanMarkdown: '',
    toolCalls: [],
    itinerary: null,
    donePayload: null,
    sessionId: '',
    requestId: '',
    error: null,
  }
}

// ============================================================
// Composable
// ============================================================

export function useAgent() {
  const state = reactive<AgentState>(createInitialState())

  /** AbortController 实例，用于取消 */
  let abortController: AbortController | null = null

  // ==========================================================
  // SSE 事件处理器
  // ==========================================================

  function handleEvent(event: AgentSSEEvent): void {
    console.log('收到事件:', event.type, event.data)
    switch (event.type) {
      // ── Agent 思考状态 ──
      case 'agent_think': {
        state.statusText = event.data as string
        state.step += 1
        break
      }

      // ── 工具调用开始 ──
      case 'tool_call': {
        const payload = event.data as ToolCallPayload
        const record: ToolCallRecord = {
          tool: payload.tool,
          args: payload.args,
          message: payload.message,
          status: 'running',
          startTime: Date.now(),
        }
        state.toolCalls.push(record)
        state.statusText = payload.message || `正在调用 ${payload.tool}...`
        break
      }

      // ── 工具调用结束 ──
      case 'tool_result': {
        const payload = event.data as ToolResultPayload
        // 找到最近一个同名的 calling 记录并更新
        const record = state.toolCalls
          .filter((t) => t.status === 'running')
          .find((t) => t.tool === payload.tool)
        if (record) {
          record.resultPreview = payload.result_preview
          record.message = payload.message
          record.duration = payload.duration
          record.status = payload.status
        }
        state.statusText = payload.message || (payload.status === 'error'
          ? `${payload.tool} 失败`
          : `${payload.tool} 完成`)
        break
      }

      // ── LLM 流式文本 ──
      case 'chunk': {
        const text = event.data as string
        state.rawMarkdown += text
        // 实时去除 JSON 块，保留干净文本
        state.cleanMarkdown = cleanJsonBlock(state.rawMarkdown)
        break
      }

      // ── 结构化行程 JSON ──
      case 'itinerary_json': {
        state.itinerary = event.data as ItineraryPayload
        state.statusText = '行程数据已生成'
        // 若流式文案被清洗后过短，用结构化 days 生成可读兜底，避免左侧有卡、中间空白
        if (!state.cleanMarkdown || state.cleanMarkdown.length < 40) {
          const fallback = buildMarkdownFromItinerary(event.data as ItineraryPayload)
          if (fallback) {
            state.cleanMarkdown = fallback
            if (!state.rawMarkdown) state.rawMarkdown = fallback
          }
        }
        break
      }

      // ── 完成 ──
      case 'done': {
        const payload = event.data as DonePayload
        state.donePayload = payload
        state.sessionId = payload.session_id || ''
        state.requestId = payload.request_id || ''
        state.loading = false
        state.statusText = '行程生成完成'
        break
      }

      // ── 错误 ──
      case 'error': {
        const payload = event.data as ErrorPayload
        state.error = payload
        state.loading = false
        if (payload.code === 'STREAM_INTERRUPTED' || payload.code === 'STREAM_ERROR') {
          state.statusText = '连接中断，可重新点击生成'
        } else {
          state.statusText = '生成失败'
        }
        break
      }
    }
  }

  // ==========================================================
  // 公开方法
  // ==========================================================

  /**
   * 首次生成行程。
   */
  async function startGenerate(params: GenerateParams): Promise<void> {
    // 重置状态
    Object.assign(state, createInitialState())
    state.loading = true
    state.statusText = '正在启动旅行规划...'

    abortController = new AbortController()

    try {
      await generateItinerary(params, handleEvent, abortController.signal)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        state.error = {
          code: 'UNKNOWN',
          message: `未预期的错误: ${(err as Error).message}`,
        }
      }
    } finally {
      state.loading = false
      abortController = null
    }
  }

  /**
   * 多轮修改：在已有行程上继续对话。
   */
  async function continueGenerate(message: string): Promise<void> {
    if (!state.sessionId) {
      state.error = { code: 'NO_SESSION', message: '没有可用的会话，请先生成行程' }
      return
    }

    state.loading = true
    state.statusText = '正在根据你的意见修改行程...'
    state.error = null

    abortController = new AbortController()

    try {
      await continueChat(state.sessionId, message, handleEvent, abortController.signal)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        state.error = {
          code: 'UNKNOWN',
          message: `未预期的错误: ${(err as Error).message}`,
        }
      }
    } finally {
      state.loading = false
      abortController = null
    }
  }

  /**
   * 从历史会话加载行程数据到当前 state。
   */
  function loadSession(data: {
    sessionId: string
    destination: string
    days: number
    styles: string[]
    itinerary: import('@/api/agent').ItineraryPayload | null
    placesDetail: {
      name: string
      lng: number
      lat: number
      address?: string
      tel?: string
      category?: string
    }[] | null
    markdownText?: string
  }): void {
    Object.assign(state, createInitialState())
    state.sessionId = data.sessionId
    state.itinerary = data.itinerary
    if (data.markdownText) {
      state.rawMarkdown = data.markdownText
      state.cleanMarkdown = cleanJsonBlock(data.markdownText)
    }
    if (data.placesDetail && data.placesDetail.length > 0) {
      state.donePayload = {
        destination: data.destination,
        days: data.days,
        places_count: data.placesDetail.length,
        places_detail: data.placesDetail,
        session_id: data.sessionId,
      }
    }
  }

  /**
   * 取消当前请求。
   */
  function abort(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    state.loading = false
    state.statusText = '已取消'
  }

  /**
   * 清空所有状态。
   */
  function reset(): void {
    abort()
    Object.assign(state, createInitialState())
  }

  // ==========================================================
  // 返回
  // ==========================================================

  return {
    state,
    startGenerate,
    continueGenerate,
    loadSession,
    abort,
    reset,
  }
}

// ============================================================
// 工具函数：从 Markdown 中移除 JSON 代码块
// ============================================================

/** 当流式文案缺失时，用 itinerary_json 拼一份可读 Markdown（仅展示兜底） */
function buildMarkdownFromItinerary(payload: ItineraryPayload): string {
  const days = payload?.days
  if (!Array.isArray(days) || days.length === 0) return ''
  const lines: string[] = ['### 行程概览', '']
  for (const d of days) {
    lines.push(`#### Day ${d.day}`)
    if (d.morning) lines.push(`- **上午**：${d.morning}`)
    if (d.afternoon) lines.push(`- **下午**：${d.afternoon}`)
    if (d.evening) lines.push(`- **晚上**：${d.evening}`)
    lines.push('')
  }
  return lines.join('\n').trim()
}

/**
 * 实时去除 Markdown 中的 ```json/```xml 代码块以及 LLM 误输出的 tool_calls XML。
 * 只清理工具相关标签，避免误伤正文 Markdown（加粗/标题等可读性格式）。
 */
function cleanJsonBlock(raw: string): string {
  let cleaned = raw
  const toolTags = ['tool_calls', 'function_calls', 'invoke', 'parameter']
  const toolTagAlt = toolTags.join('|')

  // 1. 移除 ```json / ```xml 代码块
  cleaned = cleaned.replace(/```(?:json|xml)[\s\S]*?```/g, '')
  cleaned = cleaned.replace(/```(?:json|xml)[\s\S]*$/g, '')

  // 2. 整块删除工具 XML（重复直到稳定，处理嵌套）
  for (let i = 0; i < 20; i++) {
    const prev = cleaned
    for (const tag of toolTags) {
      cleaned = cleaned.replace(new RegExp(`<${tag}[^>]*>[\\s\\S]*?<\\/${tag}>`, 'g'), '')
      cleaned = cleaned.replace(new RegExp(`<${tag}[^>]*\\/>`, 'g'), '')
    }
    if (cleaned === prev) break
  }

  // 3. 逐行过滤：工具 XML 行、以及误当作正文的工具日志
  cleaned = cleaned
    .split('\n')
    .filter((line) => {
      if (new RegExp(`^\\s*<\\/?(?:${toolTagAlt})\\b`).test(line)) return false
      if (/^\s*已执行工具调用[：:]/.test(line)) return false
      if (/^\s*【已收集的真实工具数据】/.test(line)) return false
      if (/^\s*[-*]\s*(调用|结果)[：:]/.test(line)) return false
      return true
    })
    .join('\n')

  // 4. 兜底：仅从残留的工具 XML 开标签截断到末尾（流式未闭合）
  cleaned = cleaned.replace(new RegExp(`<(?:${toolTagAlt})\\b[^>]*>[\\s\\S]*$`, 'g'), '')

  // 5. 清理多余空行
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n')
  return cleaned.trim()
}
