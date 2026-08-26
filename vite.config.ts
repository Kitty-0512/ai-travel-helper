import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],

  // @ 别名 → src/
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  // GitHub Pages 部署用相对路径
  base: './',

  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: false,
    open: false,

    // ──────────────────────────────────────
    // 开发环境代理：把 /api 请求转发到 FastAPI 后端
    // 前端无需配 VITE_API_BASE_URL（设置了也不影响代理）
    // ──────────────────────────────────────
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',   // FastAPI 后端；若与其它项目冲突可改为 8001
        changeOrigin: true,
        // SSE 流式响应：只修改响应头，不接管 pipe，避免数据重复
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            const ct = proxyRes.headers['content-type'] ?? ''
            if (ct.includes('text/event-stream')) {
              // 删除 Content-Encoding 防止中间件重复解压
              delete proxyRes.headers['content-encoding']
              // 告知各级代理不要缓冲
              proxyRes.headers['cache-control'] = 'no-cache'
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        },
      },
    },
  },
})
