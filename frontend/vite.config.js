import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Ensure the dev server actually listens (helps on Windows/WSL/Docker)
    host: true,
    port: 5173,
    strictPort: true, // fail fast if 5173 is taken so you notice
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  }
})