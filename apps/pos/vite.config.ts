import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Festival Bar',
        short_name: 'Bar',
        lang: 'nl',
        start_url: '/',
        display: 'fullscreen',
        orientation: 'landscape',
        background_color: '#17130f',
        theme_color: '#17130f',
        icons: [],
      },
      workbox: {
        // The app shell must load from a cold start with no network at all.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
      },
    }),
  ],
  server: {
    host: true, // listen on the LAN so a real tablet can reach the dev server
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
