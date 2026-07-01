import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Ship the web fonts (previously declared in Tailwind but never loaded → silent system fallback).
// Fraunces (display serif) for editorial headings, Inter for prose, JetBrains Mono for every
// numeric / id / timestamp / eyebrow. Self-hosted variable faces → no layout shift, on-prem safe.
import '@fontsource-variable/fraunces/index.css'
import '@fontsource-variable/inter/index.css'
import '@fontsource-variable/jetbrains-mono/index.css'
import './index.css'
import { App } from './App'
import { startMocks } from './lib/mocks/enable'
import { initDensity } from './lib/density'

// Reflect the persisted density choice before first paint.
initDensity()

// Start MSW first (when VITE_USE_MOCKS=true) so the worker intercepts before the first request.
startMocks().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
