import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Register PWA Service Worker with cache busting & self-update
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

    if (isLocalhost) {
      // In local development, purge SW and caches completely to prevent stale bundle traps
      navigator.serviceWorker.getRegistrations().then((regs) => {
        regs.forEach((reg) => reg.unregister())
      })
      if ('caches' in window) {
        caches.keys().then((names) => names.forEach((name) => caches.delete(name)))
      }
      return
    }

    // Production: Clear obsolete PWA caches
    if ('caches' in window) {
      caches.keys().then((names) => {
        names.forEach((name) => {
          if (name !== 'ibrabot-pwa-v4') {
            caches.delete(name)
          }
        })
      })
    }

    navigator.serviceWorker
      .register('/sw.js')
      .then((reg) => {
        reg.update()
      })
      .catch((err) => {
        console.warn('PWA service worker registration failed:', err)
      })
  })
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
