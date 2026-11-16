import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { env } from 'node:process'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: Number(env.LEE_TOOLBOX_WEB_PORT || 5173),
    strictPort: true,
    proxy: { '/api': { target: `http://127.0.0.1:${env.LEE_TOOLBOX_API_PORT || 8000}`, changeOrigin: false } },
  },
  build: { outDir: 'dist' },
})
