import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    // Unit tests only. e2e/ is Playwright, and vitest chokes on its module-level
    // test.skip(), which turned a green-looking local grep into a red CI run.
    include: ['src/**/*.{test,spec}.ts'],
  },
})
