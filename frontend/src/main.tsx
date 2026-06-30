import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App'
import { startMocks } from './lib/mocks/enable'

// Start MSW first (when VITE_USE_MOCKS=true) so the worker intercepts before the first request.
startMocks().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
