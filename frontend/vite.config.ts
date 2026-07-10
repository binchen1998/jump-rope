import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const assetBase = process.env.VITE_ASSET_BASE || '/'

export default defineConfig({
  plugins: [vue()],
  base: assetBase.endsWith('/') ? assetBase : `${assetBase}/`,
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
