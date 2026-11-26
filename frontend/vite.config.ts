import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const target = process.env.CODEFORGE_PROXY || 'http://localhost:8080'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    fs: {
      allow: [
        fileURLToPath(new URL('.', import.meta.url)),
        fileURLToPath(new URL('../app/codeforge/common/judge_languages.json', import.meta.url)),
      ],
    },
    proxy: {
      '/api': target,
      '/ws': { target, ws: true },
    },
  },
  build: { target: 'es2020' },
})
