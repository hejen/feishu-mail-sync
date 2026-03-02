import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    headers: {
      'X-Frame-Options': 'ALLOWALL'
    }
  },
  build: {
    outDir: 'dist'
  }
})
