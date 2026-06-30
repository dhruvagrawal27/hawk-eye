/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite 8 + @vitejs/plugin-react 6 + React 19 (blueprint Part 24.3 BOM; see docs/laptops/04-frontend.md
// for the documented deviation from the prompt's "Vite 5.x" — Node 22/26 + plugin-react 6 require Vite 8).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // Port 5173 per CONTEXT.md ports/service map. strictPort so a clash fails loudly.
  server: { port: 5173, strictPort: true, host: true },
  preview: { port: 5173, strictPort: true },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // Perf budget (Part 11 — sub-second drill-down): split the heavy investigation libs
    // (graph + charts) out of the initial route bundle. They are also route-lazy-loaded.
    // Function form (Vite 8 / Rolldown does not accept the object form of manualChunks).
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/cytoscape')) return 'cytoscape'
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3'))
            return 'charts'
          if (
            id.includes('node_modules/react-dom') ||
            id.includes('node_modules/react-router') ||
            id.includes('node_modules/react/')
          ) {
            return 'vendor'
          }
          return undefined
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: './coverage',
      exclude: ['**/*.d.ts', 'src/test/**', 'src/lib/mocks/**', 'e2e/**', '**/*.config.*'],
    },
  },
})
