/**
 * src/composables/useItinerary.ts
 *
 * 职责：把 Agent 返回的结构化行程数据转换为现有 Map.vue / 景点清单
 *       能直接消费的格式，保持与原来 App.vue 的数据结构兼容。
 *
 * 输入：来自 useAgent state 的 ItineraryPayload / DonePayload
 * 输出：places[], dayGroups[], itineraryData (与原来一致)
 */

import { computed, type ComputedRef } from 'vue'
import type { ItineraryPayload, DonePayload, DayData, PlaceDetail } from '@/api/agent'

// ============================================================
// 类型（保持与原 App.vue 兼容）
// ============================================================

/** 每日行程（与原 App.vue 的 DayData 一致） */
export interface LocalDayData {
  day: number
  morning: string
  afternoon: string
  evening: string
}

/** 结构化行程（与原 App.vue 的 ItineraryData 一致） */
export interface LocalItineraryData {
  days: LocalDayData[]
  allPlaces: string[]
}

// ============================================================
// 工具函数
// ============================================================

/**
 * 从 Agent 返回的 ItineraryPayload 转为本地格式。
 * 后端已经帮我们结构化好了，这里只做一次薄转换。
 */
export function parseItineraryPayload(payload: ItineraryPayload): LocalItineraryData {
  return {
    days: payload.days.map((d) => ({
      day: d.day,
      morning: d.morning || '',
      afternoon: d.afternoon || '',
      evening: d.evening || '',
    })),
    allPlaces: payload.allPlaces || [],
  }
}

/**
 * 从 DonePayload 提取景点坐标列表，供路径优化使用。
 * 格式：[lng, lat][]
 */
export function extractCoords(done: DonePayload): [number, number][] {
  return (done.places_detail || []).map((p: PlaceDetail) => [p.lng, p.lat])
}

/**
 * 从 DonePayload 提取景点名称列表。
 */
export function extractPlaceNames(done: DonePayload): string[] {
  return (done.places_detail || []).map((p: PlaceDetail) => p.name)
}

/**
 * 从 ItineraryPayload 的 days 生成 dayGroups（按天分组的景点数组）。
 * 每项是一个 string[]：该天上午/下午/晚上的景点。
 */
export function buildDayGroups(days: DayData[]): string[][] {
  return days.map((d) =>
    [d.morning, d.afternoon, d.evening].filter((s) => s && s.trim() !== '')
  )
}

// ============================================================
// Composable
// ============================================================

export interface UseItineraryInput {
  /** 来自 useAgent state 的 itinerary */
  itinerary: ComputedRef<ItineraryPayload | null>
  /** 来自 useAgent state 的 donePayload */
  donePayload: ComputedRef<DonePayload | null>
}

export function useItinerary(input: UseItineraryInput) {
  /** 本地格式的行程数据 */
  const itineraryData = computed<LocalItineraryData>(() => {
    if (input.itinerary.value) {
      return parseItineraryPayload(input.itinerary.value)
    }
    return { days: [], allPlaces: [] }
  })

  /** 景点名称列表（allPlaces） */
  const places = computed<string[]>(() => itineraryData.value.allPlaces)

  /** 按天分组的景点列表（兼容 Map.vue 的 dayGroups prop） */
  const dayGroups = computed<string[][]>(() => {
    if (!input.itinerary.value) return []
    return buildDayGroups(input.itinerary.value.days)
  })

  /** 带坐标的景点详情 */
  const placesDetail = computed<PlaceDetail[]>(() => {
    return input.donePayload.value?.places_detail || []
  })

  /** 景点总数 */
  const placesCount = computed<number>(() => {
    return input.donePayload.value?.places_count || places.value.length
  })

  return {
    itineraryData,
    places,
    dayGroups,
    placesDetail,
    placesCount,
  }
}
