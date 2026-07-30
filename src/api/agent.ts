/**
 * src/api/agent.ts
 * AI 旅行 Agent — SSE 流式客户端
 *
 * 用原生 fetch + ReadableStream 消费后端 FastAPI 的 SSE 端点，
 * 支持 AbortController 取消、完整 TypeScript 类型、中文注释。
 */

import { getUserId } from '@/utils/userId'

// ============================================================
// 类型定义
// ============================================================

/** 后端 SSE 事件类型（与 backend/app/agents/loop.py 对齐） */
type SSEEventType =
  | 'agent_think'    // Agent 正在思考
  | 'tool_call'      // 即将调用工具
  | 'tool_result'    // 工具返回结果
  | 'chunk'          // LLM 流式文本片段
  | 'itinerary_json' // 最终结构化行程 JSON
  | 'done'           // 全部完成
  | 'error'          // 异常中断

/** 景点坐标详情 */
export interface PlaceDetail {
  name: string
  lng: number
  lat: number
}

/** 每日行程 */
export interface DayData {
  day: number
  morning: string
  afternoon: string
  evening: string
}

/** itinerary_json 事件携带的数据 */
export interface ItineraryPayload {
  days: DayData[]
  allPlaces: string[]
}

/** done 事件携带的数据 */
export interface DonePayload {
  request_id?: string
  destination: string
  days: number
  places_count: number
  places_detail: PlaceDetail[]
  /** 会话 ID，用于后续 /chat 多轮修改 */
  session_id?: string
}

/** tool_call 事件携带的数据 */
export interface ToolCallPayload {
  type?: 'tool_call'
  tool: string
  status: 'running'
  message?: string
  args: Record<string, unknown>
}

/** tool_result 事件携带的数据 */
export interface ToolResultPayload {
  tool: string
  status: 'success' | 'error'
  message?: string
  duration?: number
  result_preview: Record<string, unknown>
}

/** error 事件携带的数据 */
export interface ErrorPayload {
  code: string
  message: string
}

/** 统一的 SSE 事件对象 */
export interface AgentSSEEvent {
  type: SSEEventType
  /** agent_think / chunk → 字符串；tool_* / itinerary_json / done / error → 对象 */
  data: string | ToolCallPayload | ToolResultPayload | ItineraryPayload | DonePayload | ErrorPayload
}

/** onEvent 回调类型 */
export type OnEventCallback = (event: AgentSSEEvent) => void

/** generateItinerary 的请求参数 */
export interface GenerateParams {
  destination: string
  days: number
  styles: string[]
}

// ============================================================
// 请求头（后端 SimpleAuth）
// ============================================================

/** 从环境变量取 API Key，或使用空字符串（走 Vite 代理时可不填） */
const API_SECRET_KEY = import.meta.env.VITE_API_SECRET_KEY || 'change-me-to-a-random-string'

/** 后端基础地址（开发时走 Vite proxy，生产时用完整 URL） */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// ============================================================
// 核心：SSE 流读取器
// ============================================================

/**
 * 通用 SSE 流读取函数。
 *
 * @param url       请求路径（如 /api/agent/generate）
 * @param body      请求体（POST JSON）
 * @param onEvent   事件回调，每解析出一个 SSE 事件就调用
 * @param signal    AbortSignal，用于取消请求
 */
async function streamSSE(
  url: string,
  body: Record<string, unknown>,
  onEvent: OnEventCallback,
  signal?: AbortSignal,
): Promise<void> {
  const fullUrl = `${BASE_URL}${url}`

  let response: Response
  try {
    response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'X-API-Key': API_SECRET_KEY,
        'X-User-Id': getUserId(),
      },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      // 用户主动取消，不算错误
      return
    }
    onEvent({
      type: 'error',
      data: { code: 'NETWORK_ERROR', message: `网络请求失败: ${(err as Error).message}` },
    })
    return
  }

  // ── HTTP 状态码检查 ──
  if (!response.ok) {
    let errorMsg = `后端返回 ${response.status}`
    try {
      const errBody = await response.text()
      const parsed = JSON.parse(errBody)
      errorMsg = parsed.detail || parsed.message || errorMsg
    } catch {
      // 非 JSON 响应体
    }
    onEvent({
      type: 'error',
      data: { code: 'HTTP_ERROR', message: errorMsg },
    })
    return
  }

  if (!response.body) {
    onEvent({
      type: 'error',
      data: { code: 'NO_BODY', message: '后端未返回流式数据' },
    })
    return
  }

  // ── ReadableStream 逐行解析 SSE（按 RFC 8895 实现） ──
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''           // 残留的未完整行
  let currentEventType = '' // 当前事件的 event 字段
  let currentData = ''      // 当前事件的 data 字段（多行拼接）
  let hasData = false        // 是否收到过至少一个 data 行
  let lastEventId = ''       // 最近一次事件 ID，便于断线诊断
  let receivedDone = false   // 是否已收到 done 事件

  /** 解析一个字段行，返回 { field, value } */
  function parseField(raw: string): { field: string; value: string } {
    const colonIdx = raw.indexOf(':')
    if (colonIdx === -1) {
      // 整行是字段名，值为空字符串
      return { field: raw.trim(), value: '' }
    }
    const field = raw.slice(0, colonIdx).trim()
    // RFC：冒号后紧跟一个可选的空格，只去掉第一个空格
    const value = raw.slice(colonIdx + 1).replace(/^ /, '')
    return { field, value }
  }

  /** 派发一个完整事件 */
  function dispatchEvent(): void {
    if (!hasData) return           // 没有 data 字段，忽略
    const data = currentData
    const type = (currentEventType || 'message') as SSEEventType
    // 重置
    currentEventType = ''
    currentData = ''
    hasData = false

    if (type === 'done') {
      receivedDone = true
    }

    // 尝试 JSON 解析（dict / list 事件）；失败则视为纯字符串
    try {
      const parsed = JSON.parse(data)
      onEvent({ type, data: parsed })
    } catch {
      onEvent({ type, data })
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      // 统一行尾符：\r\n → \n，孤立的 \r → \n
      buffer += decoder.decode(value, { stream: true })
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')

      const lines = buffer.split('\n')
      // 最后一段可能不完整，留在 buffer 等下次数据到来
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line === '') {
          // 空行 = 事件边界
          dispatchEvent()
          continue
        }
        if (line.startsWith(':')) {
          // SSE 注释行，忽略
          continue
        }

        const { field, value: fieldValue } = parseField(line)

        switch (field) {
          case 'event':
            currentEventType = fieldValue
            break
          case 'data':
            // 多行 data 拼接时用 \n 分隔
            if (hasData) currentData += '\n'
            currentData += fieldValue
            hasData = true
            break
          case 'id':
            lastEventId = fieldValue
            break
          case 'retry':
            // 重连间隔，暂不处理
            break
        }
      }
    }
    // 流结束时如果缓冲区还有未派发的事件
    if (hasData) dispatchEvent()

    if (!receivedDone && !signal?.aborted) {
      onEvent({
        type: 'error',
        data: {
          code: 'STREAM_INTERRUPTED',
          message: lastEventId
            ? `连接意外中断（最后事件 ID: ${lastEventId}），请重新发起生成`
            : '连接意外中断，请检查网络后重新发起生成',
        },
      })
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return
    }
    onEvent({
      type: 'error',
      data: {
        code: 'STREAM_ERROR',
        message: lastEventId
          ? `流读取中断（最后事件 ID: ${lastEventId}）: ${(err as Error).message}`
          : `流读取中断: ${(err as Error).message}`,
      },
    })
  } finally {
    reader.releaseLock()
  }
}

// ============================================================
// 对外 API 1：首次生成行程
// ============================================================

/**
 * 一键生成旅行行程。
 *
 * 使用示例：
 * ```ts
 * const controller = new AbortController()
 *
 * await generateItinerary(
 *   { destination: '北京', days: 3, styles: ['美食', '历史文化'] },
 *   (event) => {
 *     switch (event.type) {
 *       case 'agent_think': console.log('思考:', event.data)
 *       case 'tool_call':   console.log('调工具:', event.data)
 *       case 'chunk':       appendToMarkdown(event.data as string)
 *       case 'itinerary_json': updateItinerary(event.data as ItineraryPayload)
 *       case 'done':        finish(event.data as DonePayload)
 *       case 'error':       showError(event.data as ErrorPayload)
 *     }
 *   },
 *   controller.signal   // 可选：用于取消
 * )
 *
 * // 用户点击取消：
 * controller.abort()
 * ```
 */
export async function generateItinerary(
  params: GenerateParams,
  onEvent: OnEventCallback,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE(
    '/api/agent/generate',
    {
      destination: params.destination,
      days: params.days,
      styles: params.styles,
    },
    onEvent,
    signal,
  )
}

// ============================================================
// 对外 API 2：多轮修改
// ============================================================

/**
 * 在已生成的行程上继续对话修改。
 *
 * @param sessionId 从 done 事件的 session_id 获取
 * @param message   用户的修改意见（如"第三天太赶了，删掉一个景点"）
 * @param onEvent   SSE 事件回调
 * @param signal    取消信号
 *
 * 使用示例：
 * ```ts
 * await continueChat(
 *   'abc12345',
 *   '第二天我想多逛一些博物馆',
 *   (event) => { ... },
 *   controller.signal,
 * )
 * ```
 */
export async function continueChat(
  sessionId: string,
  message: string,
  onEvent: OnEventCallback,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE(
    '/api/agent/chat',
    {
      session_id: sessionId,
      message,
    },
    onEvent,
    signal,
  )
}

// ============================================================
// 工具函数：从 DonePayload 提取景点名称列表
// ============================================================

/**
 * 从 done 事件的 places_detail 提取景点名称数组（保持顺序）。
 * 用于传给现有的路径优化 / 地图渲染逻辑。
 */
export function extractPlaceNames(done: DonePayload): string[] {
  return done.places_detail.map((p) => p.name)
}

/**
 * 从 done 事件的 places_detail 提取坐标数组。
 * 格式：[lng, lat][]，用于传给 tsp.ts 的 optimizeRoute。
 */
export function extractCoords(done: DonePayload): [number, number][] {
  return done.places_detail.map((p) => [p.lng, p.lat] as [number, number])
}
