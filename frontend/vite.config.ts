import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const target = process.env.CODEFORGE_PROXY || 'http://localhost:8080'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': target,
      '/ws': { target, ws: true },
    },
  },
  build: { target: 'es2020' },
})
