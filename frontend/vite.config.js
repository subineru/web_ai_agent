import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 開發時把 API 與 SSE 反向代理到後端（uvicorn 預設 8000）
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/tasks': { target: 'http://localhost:8000', changeOrigin: true },
      '/jobs': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
