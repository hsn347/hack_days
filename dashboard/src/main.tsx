import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Register PWA Service Worker with cache busting & self-update
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    // Clear any obsolete PWA caches on client side if needed
    if ('caches' in window) {
      caches.keys().then((names) => {
        names.forEach((name) => {
          if (name !== 'ibrabot-pwa-v3') {
            console.log('🧹 Purging obsolete PWA client cache:', name)
            caches.delete(name)
          }
        })
      })
    }

    navigator.serviceWorker
      .register('/sw.js')
      .then((reg) => {
        // Trigger immediate check for new icons and manifest
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
