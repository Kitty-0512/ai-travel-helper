<template>
  <div class="w-full h-full flex flex-col gap-2">

    <!-- 控制栏 -->
    <div class="flex flex-wrap items-center gap-2 px-1 shrink-0">
      <div class="flex gap-1">
        <button
          v-for="mode in routeModes"
          :key="mode.value"
          @click="selectMode(mode.value)"
          :class="[
            'px-2.5 py-1 rounded-full text-xs border transition-all',
            currentMode === mode.value
              ? 'bg-blue-500 text-white border-blue-500'
              : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
          ]"
        >
          {{ mode.label }}
        </button>
      </div>

      <!-- 最短路径开关 -->
      <label class="flex items-center gap-1.5 cursor-pointer ml-2">
        <div
          @click="toggleOptimize"
          :class="[
            'w-8 h-4 rounded-full transition-colors relative cursor-pointer',
            isOptimize ? 'bg-blue-500' : 'bg-gray-300'
          ]"
        >
          <div :class="[
            'absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform',
            isOptimize ? 'translate-x-4' : 'translate-x-0.5'
          ]"></div>
        </div>
        <span class="text-xs text-gray-600">最短路径</span>
      </label>

      <!-- 优化结果 -->
      <span v-if="optimizeInfo" class="text-xs text-emerald-600 font-medium">
        {{ optimizeInfo }}
      </span>

      <button
        v-if="places.length > 1"
        @click="planRoute"
        :disabled="routeLoading"
        class="ml-auto px-3 py-1 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white text-xs rounded-full transition-colors"
      >
        {{ routeLoading ? '规划中...' : '重新规划' }}
      </button>
    </div>

    <!-- 每日图例 -->
    <div v-if="dayColors.length > 1" class="flex flex-wrap gap-2 px-1 shrink-0">
      <div
        v-for="(color, i) in dayColors"
        :key="i"
        class="flex items-center gap-1 text-xs text-gray-600"
      >
        <span :style="{ background: color }" class="w-3 h-3 rounded-full inline-block"></span>
        Day {{ i + 1 }}
      </div>
    </div>

    <!-- 地图容器 -->
    <div ref="mapRef" class="w-full flex-1 rounded-xl overflow-hidden min-h-0"></div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue"
import AMapLoader from "@amap/amap-jsapi-loader"

const props = defineProps<{
  places: string[]
  destination: string
  dayGroups?: string[][]
}>()

const mapRef = ref<HTMLDivElement>()
let map: any = null
let AMap: any = null
let placeSearch: any = null

let markers: any[] = []
let polylines: any[] = []
let drivingInstances: any[] = []

const routeLoading = ref(false)
const isOptimize = ref(false)
const optimizeInfo = ref("")
const currentMode = ref<"driving" | "walking" | "riding" | "straight">("driving")
const dayColors = ref<string[]>([])

const DAY_COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"]

const routeModes = [
  { label: "驾车", value: "driving" },
  { label: "步行", value: "walking" },
  { label: "骑行", value: "riding" },
  { label: "直线", value: "straight" },
]

let mapReadyResolve!: () => void
const mapReadyPromise = new Promise<void>((r) => { mapReadyResolve = r })

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY as string
const AMAP_SECURITY_CODE = import.meta.env.VITE_AMAP_SECURITY_CODE as string

const coordCache = new Map<string, [number, number]>()
const poiCache = new Map<string, any>()

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

function buildAmapNavigationUrl(name: string, coord: [number, number]): string {
  return `https://uri.amap.com/navigation?to=${coord[0]},${coord[1]},${encodeURIComponent(name)}&mode=car&src=ai-travel-helper&coordinate=gaode&callnative=0`
}

function buildTicketUrl(name: string): string {
  return `https://you.ctrip.com/searchsite/Sight?query=${encodeURIComponent(name)}`
}

async function initMap() {
  ;(window as any)._AMapSecurityConfig = { securityJsCode: AMAP_SECURITY_CODE }

  AMap = await AMapLoader.load({
    key: AMAP_KEY,
    version: "2.0",
    plugins: ["AMap.PlaceSearch", "AMap.Driving", "AMap.Walking", "AMap.Riding"],
  })

  map = new AMap.Map(mapRef.value!, {
    zoom: 4,
    center: [104.195, 35.861],
    resizeEnable: true,
    mapStyle: "amap://styles/normal",
  })

  placeSearch = new AMap.PlaceSearch({ city: "" })
  mapReadyResolve()
}

onMounted(() => initMap())
onUnmounted(() => map?.destroy())

// ========================
// 地理编码（带缓存+延迟）
// ========================

function searchPlace(name: string): Promise<[number, number] | null> {
  if (coordCache.has(name)) return Promise.resolve(coordCache.get(name)!)
  return new Promise((resolve) => {
    placeSearch.search(name, (status: string, result: any) => {
      if (status === "complete" && result.poiList?.pois?.length) {
        const poi = result.poiList.pois[0]
        const coord: [number, number] = [poi.location.lng, poi.location.lat]
        coordCache.set(name, coord)
        poiCache.set(name, {
          address: poi.address || "暂无地址",
          tel: poi.tel || "",
          type: poi.type || "",
        })
        resolve(coord)
      } else {
        resolve(null)
      }
    })
  })
}

async function searchAllPlaces(names: string[]): Promise<{ name: string; coord: [number, number] }[]> {
  const results: { name: string; coord: [number, number] }[] = []
  for (const name of names) {
    const coord = await searchPlace(name)
    if (coord) results.push({ name, coord })
    await new Promise((r) => setTimeout(r, 300))
  }
  return results
}

// ========================
// 最短路径（贪心算法）
// ========================

function haversine(a: [number, number], b: [number, number]): number {
  const R = 6371
  const dLat = ((b[1] - a[1]) * Math.PI) / 180
  const dLon = ((b[0] - a[0]) * Math.PI) / 180
  const lat1 = (a[1] * Math.PI) / 180
  const lat2 = (b[1] * Math.PI) / 180
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x))
}

function calcTotalKm(coords: [number, number][]): number {
  let total = 0
  for (let i = 0; i < coords.length - 1; i++) {
    total += haversine(coords[i], coords[i + 1])
  }
  return Math.round(total)
}

function greedyOptimize(
  items: { name: string; coord: [number, number] }[]
): { name: string; coord: [number, number] }[] {
  if (items.length <= 2) return items
  const visited = new Array(items.length).fill(false)
  const result = [items[0]]
  visited[0] = true

  for (let step = 1; step < items.length; step++) {
    const last = result[result.length - 1].coord
    let nearestIdx = -1
    let minDist = Infinity
    for (let j = 0; j < items.length; j++) {
      if (visited[j]) continue
      const d = haversine(last, items[j].coord)
      if (d < minDist) { minDist = d; nearestIdx = j }
    }
    visited[nearestIdx] = true
    result.push(items[nearestIdx])
  }
  return result
}

// ========================
// 清空地图
// ========================

function clearMap() {
  markers.forEach((m) => map.remove(m))
  markers = []
  polylines.forEach((p) => map.remove(p))
  polylines = []
  drivingInstances.forEach((d) => d.clear?.())
  drivingInstances = []
}

// ========================
// 添加标记
// ========================

function addMarker(
  coord: [number, number],
  label: string,
  name: string,
  color: string
) {
  const marker = new AMap.Marker({
    position: coord,
    content: `<div style="
      width:30px;height:30px;
      background:${color};color:white;
      border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:11px;font-weight:bold;
      box-shadow:0 2px 8px rgba(0,0,0,0.3);
      border:2px solid white;cursor:pointer;
    ">${label}</div>`,
    offset: new AMap.Pixel(-15, -15),
    title: name,
    zIndex: 100,
  })

  marker.on("click", () => {
    const poi = poiCache.get(name)
    const safeName = escapeHtml(name)
    const safeAddress = poi?.address ? escapeHtml(poi.address) : ""
    const safeTel = poi?.tel ? escapeHtml(poi.tel) : ""
    const safeType = poi?.type ? escapeHtml(poi.type.split(";")[0]) : ""
    const navUrl = buildAmapNavigationUrl(name, coord)
    const ticketUrl = buildTicketUrl(name)
    const content = `<div style="padding:12px 14px;min-width:220px;font-size:13px;line-height:1.9">
      <div style="font-weight:600;font-size:14px;margin-bottom:4px;color:#1f2937">${label}. ${safeName}</div>
      ${safeAddress ? `<div style="color:#6b7280">${safeAddress}</div>` : ""}
      <div style="color:#6b7280">坐标：<a href="${navUrl}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none">${coord[0].toFixed(6)}, ${coord[1].toFixed(6)}</a></div>
      ${safeTel ? `<div style="color:#6b7280">${safeTel}</div>` : ""}
      ${safeType ? `<div style="color:#6b7280">${safeType}</div>` : ""}
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
        <a
          href="${navUrl}"
          target="_blank"
          rel="noopener noreferrer"
          style="display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:9999px;background:#2563eb;color:#fff;text-decoration:none;font-weight:600"
        >开始导航</a>
        <a
          href="${ticketUrl}"
          target="_blank"
          rel="noopener noreferrer"
          style="display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:9999px;background:#eef2ff;color:#4338ca;text-decoration:none;font-weight:600"
        >查看门票</a>
      </div>
    </div>`
    const info = new AMap.InfoWindow({ content, offset: new AMap.Pixel(0, -32) })
    info.open(map, coord)
  })

  map.add(marker)
  markers.push(marker)
}

// ========================
// 路线绘制
// ========================

function drawStraightLine(coords: [number, number][], color: string) {
  const poly = new AMap.Polyline({
    path: coords,
    strokeColor: color,
    strokeWeight: 3,
    strokeDasharray: [10, 6],
    strokeOpacity: 0.8,
    lineJoin: "round",
  })
  map.add(poly)
  polylines.push(poly)
}

async function planDriving(coords: [number, number][], color: string) {
  if (coords.length < 2) return
  const driving = new AMap.Driving({
    map,
    hideMarkers: true,
    polylineOptions: { strokeColor: color, strokeWeight: 4, strokeOpacity: 0.9 },
  })
  drivingInstances.push(driving)
  const waypoints = coords.slice(1, -1).map((c) => new AMap.LngLat(c[0], c[1]))
  await new Promise<void>((resolve) => {
    driving.search(
      new AMap.LngLat(coords[0][0], coords[0][1]),
      new AMap.LngLat(coords[coords.length - 1][0], coords[coords.length - 1][1]),
      { waypoints },
      (status: string) => {
        if (status !== "complete") drawStraightLine(coords, color)
        resolve()
      }
    )
  })
}

async function planWalking(coords: [number, number][], color: string) {
  for (let i = 0; i < coords.length - 1; i++) {
    const walking = new AMap.Walking({
      map, hideMarkers: true,
      polylineOptions: { strokeColor: color, strokeWeight: 4 },
    })
    await new Promise<void>((resolve) => {
      walking.search(
        new AMap.LngLat(coords[i][0], coords[i][1]),
        new AMap.LngLat(coords[i + 1][0], coords[i + 1][1]),
        (status: string) => {
          if (status !== "complete") drawStraightLine([coords[i], coords[i + 1]], color)
          resolve()
        }
      )
    })
    await new Promise((r) => setTimeout(r, 200))
  }
}

async function planRiding(coords: [number, number][], color: string) {
  for (let i = 0; i < coords.length - 1; i++) {
    const riding = new AMap.Riding({
      map, hideMarkers: true,
      polylineOptions: { strokeColor: color, strokeWeight: 4 },
    })
    await new Promise<void>((resolve) => {
      riding.search(
        new AMap.LngLat(coords[i][0], coords[i][1]),
        new AMap.LngLat(coords[i + 1][0], coords[i + 1][1]),
        (status: string) => {
          if (status !== "complete") drawStraightLine([coords[i], coords[i + 1]], color)
          resolve()
        }
      )
    })
    await new Promise((r) => setTimeout(r, 200))
  }
}

async function drawRoute(coords: [number, number][], color: string) {
  if (coords.length < 2) return
  if (currentMode.value === "driving") await planDriving(coords, color)
  else if (currentMode.value === "walking") await planWalking(coords, color)
  else if (currentMode.value === "riding") await planRiding(coords, color)
  else drawStraightLine(coords, color)
}

// ========================
// 主渲染
// ========================

async function renderPlaces(places: string[]) {
  await mapReadyPromise
  if (!places?.length) return

  routeLoading.value = true
  optimizeInfo.value = ""
  clearMap()

  const hasMultipleDays = props.dayGroups && props.dayGroups.length > 1

  if (hasMultipleDays) {
    // ---- 多日分色模式 ----
    dayColors.value = props.dayGroups!.map((_, i) => DAY_COLORS[i % DAY_COLORS.length])

    for (let day = 0; day < props.dayGroups!.length; day++) {
      const color = DAY_COLORS[day % DAY_COLORS.length]
      const dayItems = await searchAllPlaces(props.dayGroups![day])

      dayItems.forEach((item, i) => {
        addMarker(item.coord, `D${day + 1}-${i + 1}`, item.name, color)
      })

      if (dayItems.length > 1) {
        await drawRoute(dayItems.map((d) => d.coord), color)
      }
    }

  } else {
    // ---- 单色模式 + 最短路径优化 ----
    dayColors.value = []
    let items = await searchAllPlaces(places)

    if (isOptimize.value && items.length > 2) {
      const beforeKm = calcTotalKm(items.map((d) => d.coord))
      items = greedyOptimize(items)
      const afterKm = calcTotalKm(items.map((d) => d.coord))
      const saved = beforeKm - afterKm
      optimizeInfo.value = saved > 0
        ? `已优化！节省约 ${saved} km`
        : "当前顺序已是最优"
    }

    const color = DAY_COLORS[0]
    items.forEach((item, i) => addMarker(item.coord, String(i + 1), item.name, color))

    if (items.length > 1) {
      await drawRoute(items.map((d) => d.coord), color)
    }
  }

  map.setFitView(undefined, false, [60, 60, 60, 60])
  routeLoading.value = false
}

// ========================
// 对外方法
// ========================

async function flyToDestination(city: string) {
  await mapReadyPromise
  const coord = await searchPlace(city)
  if (coord) { map.setZoom(13); map.setCenter(coord) }
}

async function resizeMap() {
  await mapReadyPromise
  map?.resize?.()
}

function toggleOptimize() {
  isOptimize.value = !isOptimize.value
  if (props.places.length > 1) renderPlaces(props.places)
}

async function selectMode(mode: any) {
  currentMode.value = mode
  if (props.places.length > 1) await renderPlaces(props.places)
}

async function planRoute() {
  await renderPlaces(props.places)
}

watch(() => props.places, (p) => { if (p?.length) renderPlaces(p) }, { deep: true })
watch(() => props.dayGroups, () => { if (props.places.length) renderPlaces(props.places) }, { deep: true })

defineExpose({ flyToDestination, resizeMap })
</script>
