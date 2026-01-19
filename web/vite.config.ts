import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ command }) => ({
  plugins: [
    react(),
    tailwindcss(),
  ],
  css: {
    postcss: {
      plugins: [require('@tailwindcss/postcss')]
    }
  },
  build: {
    minify: 'terser', // 启用 Terser 压缩
    terserOptions: {
      compress: {
        drop_console: command === 'build', // 仅在 build 命令时移除 console
        drop_debugger: command === 'build', // 仅在 build 命令时移除 debugger
      },
    },
  },
}))