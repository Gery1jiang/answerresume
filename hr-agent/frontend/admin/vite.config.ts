import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 51668,
    proxy: {
      '/admin': {
        target: 'http://localhost:51666',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:51666',
        changeOrigin: true,
      },
      '/visitor': {
        target: 'http://localhost:51670',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/visitor/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
