import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin `/api/*` → FastAPI on 8765 so the browser never hits CORS when Vite uses a
    // non-default port (e.g. 5174). Set VITE_CHAT_API=/api in dev — see README.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
