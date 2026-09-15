const CACHE_NAME = 'ibrabot-pwa-v3'
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/favicon.png',
  '/logo.png',
  '/pwa-192x192.png',
  '/pwa-512x512.png',
  '/pwa-maskable-192x192.png',
  '/pwa-maskable-512x512.png',
  '/apple-touch-icon.png'
]

// Install event - Cache core static assets & take over immediately
self.addEventListener('install', (event) => {
  self.skipWaiting()
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('⚠️ Some PWA assets failed to pre-cache:', err)
      })
    })
  )
})

// Activate event - Force clean up ALL obsolete caches immediately
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('🧹 Clearing old PWA cache:', key)
            return caches.delete(key)
          }
        })
      )
    }).then(() => self.clients.claim())
  )
})

// Fetch event - Network-first for dynamic navigation & icons to ensure fresh updates
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Never cache API or Firebase requests
  if (
    url.pathname.startsWith('/api') ||
    url.hostname.includes('firebase') ||
    url.hostname.includes('googleapis') ||
    url.port === '8000'
  ) {
    return
  }

  // Handle image and static asset caching with network-first to get freshest icon
  if (
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.ico') ||
    url.pathname.includes('/assets/')
  ) {
    event.respondWith(
      fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone()
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone))
          }
          return networkResponse
        })
        .catch(() => caches.match(event.request))
    )
    return
  }

  // Network-first strategy for HTML pages
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const clone = networkResponse.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone))
        }
        return networkResponse
      })
      .catch(() => {
        return caches.match(event.request).then((cached) => {
          return cached || caches.match('/')
        })
      })
  )
})
