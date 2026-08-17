import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages 部署需要 base 路径
export default defineConfig({
  plugins: [react()],
  base: '/wecom-agent-platform/',
  build: {
    outDir: 'dist',
  },
})
