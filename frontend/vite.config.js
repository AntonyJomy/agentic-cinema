import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Firebase Auth allows localhost by default; 127.0.0.1 triggers auth/unauthorized-domain.
    host: 'localhost',
    port: 5173,
    strictPort: true,
    proxy: {
      '/clearance': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/extract-script': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
