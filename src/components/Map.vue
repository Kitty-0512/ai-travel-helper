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
let geocoder: any = null

let markers: any[] = []
let polylines: any[] = []
let drivingInstances: any[] = []

/** 防止 places/dayGroups 连续更新时叠多重绘，打爆浏览器连接数 */
let renderToken = 0
let renderTimer: ReturnType<typeof setTimeout> | null = null

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
    plugins: ["AMap.PlaceSearch", "AMap.Geocoder", "AMap.Driving", "AMap.Walking", "AMap.Riding"],
  })

  map = new AMap.Map(mapRef.value!, {
    zoom: 4,
    center: [104.195, 35.861],
    resizeEnable: true,
    mapStyle: "amap://styles/normal",
  })

  // 初始化时 destination 常为空；真正带 city 的实例在每次 search 时重建
  placeSearch = null
  mapReadyResolve()
}

onMounted(() => initMap())
onUnmounted(() => {
  if (renderTimer) clearTimeout(renderTimer)
  renderToken += 1
  clearMap()
  map?.destroy()
  map = null
})

// ========================
// 地理编码（带缓存+延迟）
// ========================

/** props.destination 为空时，用 done/seed 注入的城市兜底 */
let lockedCity = ""

function resolveCity(): string {
  return (props.destination || lockedCity || "").trim()
}

/** 父组件在点击「生成」时立即调用，避免 itinerary 先到、city 还未锁定 */
function lockCity(city: string) {
  const c = (city || "").trim()
  if (!c) return
  lockedCity = c
}

function buildSearchKeyword(name: string, city: string): string {
  if (!city) return name
  if (name.includes(city)) return name
  // 明确写成「城市+名称」，请求里 keywords 应出现城市前缀
  return `${city}${name}`
}

/** 每次按城市新建实例，避免 setCity 写不进请求 */
function ensurePlaceSearch(city: string) {
  if (!AMap || !city) return
  placeSearch = new AMap.PlaceSearch({ city, citylimit: true })
}

function ensureGeocoder(city: string) {
  if (!AMap || !city) return
  geocoder = new AMap.Geocoder({ city, citylimit: true })
}

function cacheKey(name: string): string {
  return `${resolveCity()}::${name}`
}

function cityMatches(poiCity: string | undefined, dest: string): boolean {
  if (!dest) return true
  if (!poiCity) return false
  const a = poiCity.replace(/市$|省$|自治区|特别行政区/g, "")
  const b = dest.replace(/市$|省$|自治区|特别行政区/g, "")
  return poiCity.includes(b) || dest.includes(a) || a.includes(b) || b.includes(a)
}

function pickPoiInCity(pois: any[], dest: string): any | null {
  if (!pois?.length) return null
  if (!dest) return null
  return pois.find((p) => cityMatches(p.cityname || p.pname, dest)) || null
}

function searchPlace(name: string): Promise<[number, number] | null> {
  const city = resolveCity()
  const key = cacheKey(name)
  if (coordCache.has(key)) return Promise.resolve(coordCache.get(key)!)

  return new Promise((resolve) => {
    if (!AMap) {
      resolve(null)
      return
    }
    if (!city) {
      console.warn("[Map] 跳过搜索（目的地城市为空）:", name)
      resolve(null)
      return
    }

    const keyword = buildSearchKeyword(name, city)

    const finish = (
      coord: [number, number] | null,
      poi?: { address?: string; tel?: string; type?: string },
    ) => {
      if (!coord) {
        resolve(null)
        return
      }
      coordCache.set(key, coord)
      const prev = poiCache.get(key)
      poiCache.set(key, {
        address: poi?.address || prev?.address || "暂无地址",
        tel: (poi?.tel || prev?.tel || "").trim(),
        type: poi?.type || prev?.type || "",
      })
      resolve(coord)
    }

    // 优先 Geocoder：city 参数更可靠
    ensureGeocoder(city)
    if (geocoder) {
      geocoder.getLocation(keyword, (status: string, result: any) => {
        const geocodes = result?.geocodes || []
        if (status === "complete" && geocodes.length) {
          const geo = geocodes.find((g: any) => cityMatches(g.city || g.province, city)) || geocodes[0]
          if (geo?.location && cityMatches(geo.city || geo.province, city)) {
            finish([geo.location.lng, geo.location.lat], { address: geo.formattedAddress })
            return
          }
        }
        // Geocoder 未命中时回退 PlaceSearch
        searchWithPlaceSearch(keyword, city, name, finish)
      })
      return
    }

    searchWithPlaceSearch(keyword, city, name, finish)
  })
}

function searchWithPlaceSearch(
  keyword: string,
  city: string,
  name: string,
  finish: (
    coord: [number, number] | null,
    poi?: { address?: string; tel?: string; type?: string },
  ) => void,
) {
  ensurePlaceSearch(city)
  if (!placeSearch) {
    finish(null)
    return
  }
  placeSearch.search(keyword, (status: string, result: any) => {
    const pois = result?.poiList?.pois || []
    if (status === "complete" && pois.length) {
      const poi = pickPoiInCity(pois, city)
      if (!poi) {
        console.warn("[Map] PlaceSearch 结果不在目的地城市:", name, "city=", city, "top=", pois[0]?.cityname)
        finish(null)
        return
      }
      finish([poi.location.lng, poi.location.lat], {
        address: poi.address,
        tel: poi.tel || "",
        type: poi.type || "",
      })
    } else {
      console.warn("[Map] PlaceSearch 未命中:", name, "city=", city, "keyword=", keyword)
      finish(null)
    }
  })
}

/** 用后端 places_detail 预填坐标/电话；第二个参数可锁定城市 */
function seedCoords(
  details: {
    name: string
    lng: number
    lat: number
    address?: string
    tel?: string
    category?: string
  }[],
  city?: string,
) {
  if (city?.trim()) lockedCity = city.trim()
  else if (props.destination?.trim()) lockedCity = props.destination.trim()

  for (const p of details || []) {
    if (!p?.name || !p.lng || !p.lat) continue
    const key = cacheKey(p.name)
    coordCache.set(key, [p.lng, p.lat])
    poiCache.set(key, {
      address: p.address || "",
      tel: (p.tel || "").trim(),
      type: p.category || "",
    })
  }
  if (props.places?.length) scheduleRenderPlaces(props.places)
}

async function searchAllPlaces(
  names: string[],
  token: number,
): Promise<{ name: string; coord: [number, number] }[]> {
  const results: { name: string; coord: [number, number] }[] = []
  for (const name of names) {
    if (token !== renderToken) return results
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
  markers.forEach((m) => map?.remove(m))
  markers = []
  polylines.forEach((p) => map?.remove(p))
  polylines = []
  drivingInstances.forEach((d) => {
    try {
      d.clear?.()
      d.setMap?.(null)
    } catch {
      /* ignore */
    }
  })
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
    const poi = poiCache.get(cacheKey(name))
    const safeName = escapeHtml(name)
    const safeAddress = poi?.address ? escapeHtml(poi.address) : ""
    const rawTel = (poi?.tel || "").trim()
    const safeTel = rawTel ? escapeHtml(rawTel) : ""
    const telHref = rawTel ? rawTel.split(/[;；,/|]/)[0].trim() : ""
    const safeType = poi?.type ? escapeHtml(String(poi.type).split(";")[0]) : ""
    const navUrl = buildAmapNavigationUrl(name, coord)
    const ticketUrl = buildTicketUrl(name)
    const content = `<div style="padding:12px 14px;min-width:220px;font-size:13px;line-height:1.9">
      <div style="font-weight:600;font-size:14px;margin-bottom:4px;color:#1f2937">${label}. ${safeName}</div>
      ${safeAddress ? `<div style="color:#6b7280">地址：${safeAddress}</div>` : ""}
      ${safeTel
        ? `<div style="color:#6b7280">电话：<a href="tel:${escapeHtml(telHref)}" style="color:#2563eb;text-decoration:none">${safeTel}</a></div>`
        : `<div style="color:#9ca3af">电话：暂无收录</div>`}
      <div style="color:#6b7280">坐标：<a href="${navUrl}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none">${coord[0].toFixed(6)}, ${coord[1].toFixed(6)}</a></div>
      ${safeType ? `<div style="color:#6b7280">类型：${safeType}</div>` : ""}
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

async function planDriving(coords: [number, number][], color: string, token: number) {
  if (coords.length < 2 || token !== renderToken) return
  const driving = new AMap.Driving({
    map,
    hideMarkers: true,
    showTraffic: false,
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
        if (token !== renderToken) {
          try { driving.clear?.(); driving.setMap?.(null) } catch { /* ignore */ }
          resolve()
          return
        }
        if (status !== "complete") drawStraightLine(coords, color)
        resolve()
      }
    )
  })
}

async function planWalking(coords: [number, number][], color: string, token: number) {
  for (let i = 0; i < coords.length - 1; i++) {
    if (token !== renderToken) return
    const walking = new AMap.Walking({
      map, hideMarkers: true,
      polylineOptions: { strokeColor: color, strokeWeight: 4 },
    })
    drivingInstances.push(walking)
    await new Promise<void>((resolve) => {
      walking.search(
        new AMap.LngLat(coords[i][0], coords[i][1]),
        new AMap.LngLat(coords[i + 1][0], coords[i + 1][1]),
        (status: string) => {
          if (token !== renderToken) {
            try { walking.clear?.(); walking.setMap?.(null) } catch { /* ignore */ }
            resolve()
            return
          }
          if (status !== "complete") drawStraightLine([coords[i], coords[i + 1]], color)
          resolve()
        }
      )
    })
    await new Promise((r) => setTimeout(r, 200))
  }
}

async function planRiding(coords: [number, number][], color: string, token: number) {
  for (let i = 0; i < coords.length - 1; i++) {
    if (token !== renderToken) return
    const riding = new AMap.Riding({
      map, hideMarkers: true,
      polylineOptions: { strokeColor: color, strokeWeight: 4 },
    })
    drivingInstances.push(riding)
    await new Promise<void>((resolve) => {
      riding.search(
        new AMap.LngLat(coords[i][0], coords[i][1]),
        new AMap.LngLat(coords[i + 1][0], coords[i + 1][1]),
        (status: string) => {
          if (token !== renderToken) {
            try { riding.clear?.(); riding.setMap?.(null) } catch { /* ignore */ }
            resolve()
            return
          }
          if (status !== "complete") drawStraightLine([coords[i], coords[i + 1]], color)
          resolve()
        }
      )
    })
    await new Promise((r) => setTimeout(r, 200))
  }
}

async function drawRoute(coords: [number, number][], color: string, token: number) {
  if (coords.length < 2 || token !== renderToken) return
  if (currentMode.value === "driving") await planDriving(coords, color, token)
  else if (currentMode.value === "walking") await planWalking(coords, color, token)
  else if (currentMode.value === "riding") await planRiding(coords, color, token)
  else drawStraightLine(coords, color)
}

// ========================
// 主渲染
// ========================

async function renderPlaces(places: string[]) {
  await mapReadyPromise
  if (!map || !places?.length) return

  const token = ++renderToken
  routeLoading.value = true
  optimizeInfo.value = ""
  clearMap()

  const hasMultipleDays = props.dayGroups && props.dayGroups.length > 1

  try {
    if (hasMultipleDays) {
      // ---- 多日分色模式 ----
      dayColors.value = props.dayGroups!.map((_, i) => DAY_COLORS[i % DAY_COLORS.length])

      for (let day = 0; day < props.dayGroups!.length; day++) {
        if (token !== renderToken) return
        const color = DAY_COLORS[day % DAY_COLORS.length]
        const dayItems = await searchAllPlaces(props.dayGroups![day], token)
        if (token !== renderToken) return

        dayItems.forEach((item, i) => {
          addMarker(item.coord, `D${day + 1}-${i + 1}`, item.name, color)
        })

        if (dayItems.length > 1) {
          await drawRoute(dayItems.map((d) => d.coord), color, token)
        }
      }

    } else {
      // ---- 单色模式 + 最短路径优化 ----
      dayColors.value = []
      let items = await searchAllPlaces(places, token)
      if (token !== renderToken) return

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
        await drawRoute(items.map((d) => d.coord), color, token)
      }
    }

    if (token === renderToken) {
      map.setFitView(undefined, false, [60, 60, 60, 60])
    }
  } finally {
    if (token === renderToken) {
      routeLoading.value = false
    }
  }
}

function scheduleRenderPlaces(places: string[]) {
  if (!places?.length) return
  if (renderTimer) clearTimeout(renderTimer)
  renderTimer = setTimeout(() => {
    renderTimer = null
    void renderPlaces(places)
  }, 250)
}

// ========================
// 对外方法
// ========================

async function flyToDestination(city: string) {
  await mapReadyPromise
  if (!city) return
  lockedCity = city.trim()
  const coord = await searchPlace(city)
  if (coord) { map.setZoom(13); map.setCenter(coord) }
}

async function resizeMap() {
  await mapReadyPromise
  map?.resize?.()
}

function toggleOptimize() {
  isOptimize.value = !isOptimize.value
  if (props.places.length > 1) scheduleRenderPlaces(props.places)
}

async function selectMode(mode: any) {
  currentMode.value = mode
  if (props.places.length > 1) await renderPlaces(props.places)
}

async function planRoute() {
  await renderPlaces(props.places)
}

// places 与 dayGroups 常同时更新：合并为一次防抖渲染，避免双 watch 叠请求
watch(
  () => [props.places, props.dayGroups] as const,
  ([p]) => { scheduleRenderPlaces(p || []) },
  { deep: true },
)

// 目的地一有值就锁定，防止后续搜索 city 为空
watch(
  () => props.destination,
  (city, prev) => {
    if (city?.trim()) lockedCity = city.trim()
    // 换城市时清掉旧缓存，避免跨城脏坐标
    if (prev && city && prev !== city) {
      coordCache.clear()
      poiCache.clear()
    }
  },
  { immediate: true },
)

defineExpose({ flyToDestination, resizeMap, seedCoords, lockCity })
</script>
