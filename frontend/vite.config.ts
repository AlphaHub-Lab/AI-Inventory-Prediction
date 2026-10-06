/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = process.env.BACKEND_URL || process.env.VITE_API_URL || 'http://127.0.0.1:8000'
const apiProxy = {
  '/api': { target: backendTarget, changeOrigin: true },
  '/health': { target: backendTarget, changeOrigin: true },
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: { proxy: apiProxy },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts'
  }
} as any)
