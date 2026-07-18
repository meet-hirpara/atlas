const CACHE = 'atlas-shell-v2'
const ASSETS = ['/', '/index.html', '/manifest.webmanifest', '/vite.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  // Never intercept Vite/dev modules or hashed build assets with HTML fallbacks.
  // Serving index.html for a .js/.tsx request blanks the React root.
  const path = url.pathname
  if (
    path.startsWith('/src/') ||
    path.startsWith('/@') ||
    path.startsWith('/node_modules/') ||
    path.startsWith('/assets/') ||
    /\.(?:js|mjs|cjs|ts|tsx|jsx|css|map|json|wasm)(?:$|\?)/i.test(path)
  ) {
    return
  }

  const isNavigation = req.mode === 'navigate' || req.destination === 'document'

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached
      return fetch(req).catch(() => {
        if (isNavigation) return caches.match('/index.html')
        return Response.error()
      })
    }),
  )
})
