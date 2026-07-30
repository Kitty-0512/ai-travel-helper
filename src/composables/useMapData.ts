/**
 * src/composables/useMapData.ts
 *
 * 职责：封装路径优化逻辑（Haversine + 贪心最近邻），保持与原有 tsp.ts 的接口兼容。
 *
 * 输入：景点坐标数组 + 景点名称数组
 * 输出：优化后的景点顺序、节省的公里数
 */

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { optimizeRoute, calcTotalDistance } from '@/utils/tsp'
import type { PlaceDetail } from '@/api/agent'

// ============================================================
// 类型
// ============================================================

export interface RouteOptimizationResult {
  /** 优化后的坐标顺序 */
  optimizedCoords: [number, number][]
  /** 优化后的景点名称顺序 */
  optimizedNames: string[]
  /** 优化后的总距离 (km) */
  totalKm: number
  /** 节省的公里数 */
  savedKm: number
  /** 是否有优化效果 */
  hasOptimized: boolean
}

// ============================================================
// Composable
// ============================================================

export function useMapData() {
  /** 原始坐标（用于优化前计算） */
  const originalCoords: Ref<[number, number][]> = ref([])
  /** 原始景点名 */
  const originalNames: Ref<string[]> = ref([])

  /** 优化结果 */
  const optimization = computed<RouteOptimizationResult>(() => {
    const coords = originalCoords.value
    const names = originalNames.value

    if (coords.length < 2) {
      return {
        optimizedCoords: coords,
        optimizedNames: names,
        totalKm: coords.length === 2
          ? Math.round(calcTotalDistance(coords))
          : 0,
        savedKm: 0,
        hasOptimized: false,
      }
    }

    const originalKm = calcTotalDistance(coords)
    const result = optimizeRoute(coords, names)
    const saved = Math.round(originalKm - result.totalKm)

    return {
      optimizedCoords: result.coords,
      optimizedNames: result.names,
      totalKm: result.totalKm,
      savedKm: saved > 0 ? saved : 0,
      hasOptimized: saved > 0,
    }
  })

  /**
   * 从 DonePayload 的 places_detail 设置坐标数据。
   * 调用时机：收到 done 事件后。
   */
  function setPlacesData(placesDetail: PlaceDetail[]): void {
    originalCoords.value = placesDetail.map((p) => [p.lng, p.lat])
    originalNames.value = placesDetail.map((p) => p.name)
  }

  /**
   * 从外部直接设置坐标和名称（用于兼容原有从 Map 组件 geocode 获取坐标的方式）。
   * 调用时机：如果后端 places_detail 坐标不够，可回退到 Map 组件 geocode。
   */
  function setCoordsFromMap(coords: [number, number][], names: string[]): void {
    originalCoords.value = coords
    originalNames.value = names
  }

  /** 清空数据 */
  function reset(): void {
    originalCoords.value = []
    originalNames.value = []
  }

  // ==========================================================
  // Day 颜色方案（与原来保持一致）
  // ==========================================================

  const DAY_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

  return {
    // 状态
    optimization,
    DAY_COLORS,
    // 方法
    setPlacesData,
    setCoordsFromMap,
    reset,
  }
}
