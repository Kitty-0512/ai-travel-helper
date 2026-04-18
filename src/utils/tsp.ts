// 用 Haversine 公式计算两点之间的实际距离（单位：km）
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

// 贪心最近邻算法
export function optimizeRoute(
  coords: [number, number][],
  names: string[]
): { coords: [number, number][]; names: string[]; totalKm: number } {
  if (coords.length <= 2) {
    return { coords, names, totalKm: coords.length === 2 ? haversine(coords[0], coords[1]) : 0 }
  }

  const n = coords.length
  const visited = new Array(n).fill(false)
  const resultCoords: [number, number][] = []
  const resultNames: string[] = []

  // 从第一个点出发
  let current = 0
  visited[0] = true
  resultCoords.push(coords[0])
  resultNames.push(names[0])

  for (let step = 1; step < n; step++) {
    let nearest = -1
    let minDist = Infinity

    for (let j = 0; j < n; j++) {
      if (visited[j]) continue
      const d = haversine(coords[current], coords[j])
      if (d < minDist) {
        minDist = d
        nearest = j
      }
    }

    visited[nearest] = true
    resultCoords.push(coords[nearest])
    resultNames.push(names[nearest])
    current = nearest
  }

  // 计算总距离
  let totalKm = 0
  for (let i = 0; i < resultCoords.length - 1; i++) {
    totalKm += haversine(resultCoords[i], resultCoords[i + 1])
  }

  return { coords: resultCoords, names: resultNames, totalKm: Math.round(totalKm) }
}

// 计算原始顺序的总距离（用于对比）
export function calcTotalDistance(coords: [number, number][]): number {
  let total = 0
  for (let i = 0; i < coords.length - 1; i++) {
    total += haversine(coords[i], coords[i + 1])
  }
  return Math.round(total)
}