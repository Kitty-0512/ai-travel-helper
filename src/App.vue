<template>
  <div class="h-screen flex flex-col bg-gray-50 overflow-hidden">

    <!-- Header -->
    <header class="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-4 flex items-center gap-3 shadow-sm shrink-0">
      <!-- 手机菜单按钮 -->
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

      <!-- 左侧面板（手机抽屉 + 桌面固定） -->
      <aside 
        class="w-80 shrink-0 bg-white border-r flex flex-col gap-6 p-6 overflow-y-auto 
               fixed md:relative inset-y-0 left-0 z-50 
               transform transition-transform duration-300 ease-in-out
               md:translate-x-0"
        :class="{ 'translate-x-0': sidebarOpen, '-translate-x-full': !sidebarOpen }"
      >
        <div class="flex flex-col gap-3">
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">目的地</h2>
          <input
            v-model="destination"
            type="text"
            placeholder="例如：北京、上海、长沙"
            class="border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            v-model="days"
            type="number"
            min="1"
            max="14"
            placeholder="旅行天数（例如：5）"
            class="border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">旅行风格</h2>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="style in travelStyles"
              :key="style"
              @click="toggleStyle(style)"
              :class="[
                'px-3 py-1.5 rounded-full text-xs border transition-all',
                selectedStyles.includes(style)
                  ? 'bg-blue-500 text-white border-blue-500'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
              ]"
            >
              {{ style }}
            </button>
          </div>
        </div>

        <!-- 每日行程卡片 -->
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
                :style="{ background: DAY_COLORS[(d.day - 1) % DAY_COLORS.length] }"
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

        <!-- 景点清单 -->
        <div v-else-if="places.length > 0">
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

        <div class="mt-auto flex flex-col gap-3">
          <button
            @click="generatePlan"
            :disabled="loading || !destination || !days"
            class="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors"
          >
            {{ loading ? '⏳ 生成中...' : '🪄 生成行程' }}
          </button>

          <button
            @click="exportPDF"
            :disabled="!plan"
            class="bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors"
          >
            📄 导出 PDF
          </button>
        </div>
      </aside>

      <!-- 手机遮罩层 -->
      <div 
        v-if="sidebarOpen" 
        @click="sidebarOpen = false"
        class="fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity"
      ></div>

      <!-- 右侧内容 -->
      <main class="flex-1 flex flex-col overflow-hidden md:ml-0" :class="{ 'ml-80': sidebarOpen }">

        <!-- 行程文本 -->
        <div
          ref="printRef"
          class="flex-1 overflow-y-auto bg-white p-8 prose prose-blue max-w-none"
        >
          <div v-if="!plan" class="h-full flex flex-col items-center justify-center text-gray-400 gap-3">
            <span class="text-5xl">🗺️</span>
            <p class="text-base">在左侧填写目的地和天数，点击生成行程</p>
          </div>
          <div v-else>
            <h2 class="text-2xl font-bold text-gray-800 mb-6">
              📅 {{ destination }} {{ days }} 天行程
            </h2>
            <div class="text-gray-700 leading-relaxed" v-html="planHtml"></div>
          </div>
        </div>

        <!-- 地图 -->
        <div class="h-80 shrink-0 border-t bg-white flex flex-col">
          <div class="px-4 pt-3 pb-1 shrink-0 flex items-center gap-2">
            <span class="text-sm font-semibold text-gray-500">🗺️ 地图行程</span>
            <span v-if="places.length > 0" class="text-xs text-gray-400">
              共 {{ places.length }} 个景点
            </span>
          </div>
          <div class="flex-1 overflow-hidden px-4 pb-4">
            <Map
              ref="mapRef"
              :places="places"
              :destination="destination"
              :day-groups="dayGroups"
            />
          </div>
        </div>

      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from "vue"
import Map from "./components/Map.vue"
import { generateTravelPlan } from "./api/ai"
import { marked } from "marked"
import html2canvas from "html2canvas-pro"
import jsPDF from "jspdf"

// Day 颜色方案
const DAY_COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"]

interface DayData {
  day: number
  morning: string
  afternoon: string
  evening: string
}

interface ItineraryData {
  days: DayData[]
  allPlaces: string[]
}

const destination = ref("")
const days = ref<number>()
const plan = ref("")
const places = ref<string[]>([])
const dayGroups = ref<string[][]>([])
const itineraryData = ref<ItineraryData>({ days: [], allPlaces: [] })
const loading = ref(false)

const printRef = ref<HTMLElement | null>(null)
const mapRef = ref<any>(null)

// 手机侧边栏控制
const sidebarOpen = ref(false)

// 隐藏 JSON 块
const planHtml = computed(() => {
  const text = plan.value.replace(/```json[\s\S]*?```/g, "").trim()
  return marked(text)
})

const travelStyles = ["美食", "历史文化", "自然风光", "购物", "艺术", "冒险"]
const selectedStyles = ref<string[]>([])

function toggleStyle(style: string) {
  const index = selectedStyles.value.indexOf(style)
  if (index === -1) selectedStyles.value.push(style)
  else selectedStyles.value.splice(index, 1)
}

// 解析 JSON（不变）
function parseItineraryJson(text: string): ItineraryData | null {
  try {
    const match = text.match(/```json\s*([\s\S]*?)\s*```/)
    if (!match) return null
    const data = JSON.parse(match[1]) as ItineraryData
    if (!data.days || !data.allPlaces) return null
    return data
  } catch {
    return null
  }
}

async function generatePlan() {
  if (!destination.value || !days.value || days.value < 1) return

  loading.value = true
  plan.value = ""
  places.value = []
  dayGroups.value = []
  itineraryData.value = { days: [], allPlaces: [] }
  sidebarOpen.value = false   // 生成后自动收起侧边栏（手机友好）

  try {
    const stream = await generateTravelPlan(
      destination.value,
      days.value,
      selectedStyles.value
    )

    const reader = stream.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split("\n")

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (data === "[DONE]") continue
        try {
          const json = JSON.parse(data)
          const text = json.choices?.[0]?.delta?.content
          if (text) plan.value += text
        } catch {
          // 跳过非 JSON 行
        }
      }
    }

    const parsed = parseItineraryJson(plan.value)

    if (parsed) {
      itineraryData.value = parsed
      places.value = parsed.allPlaces
      dayGroups.value = parsed.days.map((d) =>
        [d.morning, d.afternoon, d.evening].filter(Boolean)
      )
    }

    await nextTick()
    mapRef.value?.flyToDestination?.(destination.value)

  } catch (e: any) {
    console.error("生成错误:", e)
    plan.value = `生成失败：${e.message || "请检查 API Key 或网络"}`
  } finally {
    loading.value = false
  }
}

async function exportPDF() {
  if (!printRef.value) return

  try {
    const el = printRef.value
    const original = {
      height: el.style.height,
      overflow: el.style.overflow,
      maxHeight: el.style.maxHeight,
    }

    el.style.height = "auto"
    el.style.overflow = "visible"
    el.style.maxHeight = "none"

    await nextTick()

    const canvas = await html2canvas(el, {
      scale: 2,
      useCORS: true,
      backgroundColor: "#ffffff",
      scrollY: 0,
      width: el.scrollWidth,
      height: el.scrollHeight,
      windowWidth: el.scrollWidth,
      windowHeight: el.scrollHeight,
    })

    el.style.height = original.height
    el.style.overflow = original.overflow
    el.style.maxHeight = original.maxHeight

    const pdf = new jsPDF("p", "mm", "a4")
    const pdfW = pdf.internal.pageSize.getWidth()
    const pdfH = pdf.internal.pageSize.getHeight()
    const ratio = pdfW / canvas.width
    const imgH = canvas.height * ratio
    let heightLeft = imgH
    let position = 0

    pdf.addImage(canvas.toDataURL("image/png"), "PNG", 0, position, pdfW, imgH)
    heightLeft -= pdfH

    while (heightLeft > 0) {
      position = heightLeft - imgH
      pdf.addPage()
      pdf.addImage(canvas.toDataURL("image/png"), "PNG", 0, position, pdfW, imgH)
      heightLeft -= pdfH
    }

    pdf.save(`${destination.value || "旅行行程"}.pdf`)
  } catch (err) {
    console.error("PDF 导出失败:", err)
    alert("PDF 导出失败，请查看控制台（F12）")
  }
}
</script>