import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// 개발 중에는 /api, /health를 기존 FastAPI(uvicorn, 8000포트)로 프록시한다.
// 이렇게 하면 백엔드 CORS 설정을 전혀 건드리지 않고도 브라우저 입장에서 동일 오리진처럼 호출 가능하다
// (task-plan-frontend-react.md 참고). 운영 빌드는 FastAPI가 dist/를 직접 서빙하므로 프록시가 불필요.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5183,
    proxy: {
      // localhost는 Mac에서 IPv6(::1)로 먼저 풀릴 수 있어, 127.0.0.1을 명시해 IPv4 개발서버로 고정한다.
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
