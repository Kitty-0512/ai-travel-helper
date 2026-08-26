import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],

  // @ alias -> src/
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  // GitHub Pages uses relative paths
  base: './',

  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: false,
    open: false,

    // Dev proxy: forward /api to FastAPI backend
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // if busy, change to 8001
        changeOrigin: true,
        // SSE: adjust headers only, do not take over the pipe
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            const ct = proxyRes.headers['content-type'] ?? ''
            if (ct.includes('text/event-stream')) {
              delete proxyRes.headers['content-encoding']
              proxyRes.headers['cache-control'] = 'no-cache'
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        },
      },
    },
  },
})
