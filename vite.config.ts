import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],

  base: '/ai-travel-helper/',

  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: false,
    open: false
  }
})