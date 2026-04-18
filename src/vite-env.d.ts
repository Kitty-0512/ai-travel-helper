/// <reference types="vite/client" />

// 高德地图类型声明
/// <reference types="@amap/amap-jsapi-types" />

interface ImportMetaEnv {
  readonly VITE_AMAP_KEY: string      // 高德地图 Key
  readonly VITE_OPENAI_API_KEY: string // OpenAI Key（可选）
  // 以后有其他 VITE_ 开头的环境变量也可以在这里添加
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}