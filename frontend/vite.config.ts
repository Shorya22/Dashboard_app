import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const ROOT_ENV_DIR = path.resolve(__dirname, '../')

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ROOT_ENV_DIR, '')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    envDir: ROOT_ENV_DIR,
    server: {
      host: true,
      allowedHosts: true,
      cors: {
        origin: '*',
        methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
        allowedHeaders: ['*'],
      },
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
