// Minimal service worker for PWA installability
// Network-first strategy: always fetch fresh content, SW just enables installation
const CACHE_NAME = 'jarvis-v1'

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  )
  self.clients.claim()
})

// Network-first: always try network, fall back to cache for static assets only
self.addEventListener('fetch', (event) => {
  // Only cache GET requests for static assets
  if (event.request.method !== 'GET') return
  if (event.request.url.includes('/api/')) return  // Never cache API calls

  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)))
})
