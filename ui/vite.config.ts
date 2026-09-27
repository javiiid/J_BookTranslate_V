import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

// The Python backend is a local HTTP API on 8765. In dev we proxy to it so the
// browser sees a single origin and no CORS handling is needed anywhere.
//
// The variable was renamed with the product (JBT_API -> KALIMA_API) but the old
// name still works: an existing shell profile or .env would otherwise break with
// no error, just a proxy pointed at the wrong port.
const BACKEND =
  process.env.KALIMA_API ?? process.env.JBT_API ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/reader': { target: BACKEND, changeOrigin: true },
      '/downloads': { target: BACKEND, changeOrigin: true },
      '/library': { target: BACKEND, changeOrigin: true },
      '/account': { target: BACKEND, changeOrigin: true },
      '/workspace': { target: BACKEND, changeOrigin: true },
      '/landing': { target: BACKEND, changeOrigin: true },
      '/welcome': { target: BACKEND, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
