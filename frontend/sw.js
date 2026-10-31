/**
 * sw.js — SmartRoute Service Worker
 * ─────────────────────────────────────────────────────────────────────────────
 * Minimal Service Worker for PWA App Shell caching.
 *
 * CRITICAL REQUIREMENTS:
 * 1. Cache only static app shell assets (HTML, manifest, icons, Leaflet assets).
 * 2. NEVER cache route calculations, heatmap feeds, or graph/node API responses.
 * 3. Never present stale routing or incident data as current.
 * 4. Keep routing strictly dependent on the backend.
 * 5. Return explicit 503 if backend is unreachable for API requests.
 */

const CACHE_NAME = 'smartroute-shell-v1';

// Static assets forming the application shell
const APP_SHELL_ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
  './icons/icon.svg',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

// Install event — precache app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Use addAll with error resilience for each asset
      return Promise.allSettled(
        APP_SHELL_ASSETS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn(`[SW] Precache failed for ${url}:`, err);
          })
        )
      );
    }).then(() => self.skipWaiting())
  );
});

// Activate event — clean up old caches and claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME && key.startsWith('smartroute-')) {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Helper: determine if request is an API call
function isApiRequest(url) {
  const path = url.pathname;
  return (
    path.startsWith('/route') ||
    path.startsWith('/nodes') ||
    path.startsWith('/heatmap') ||
    path.startsWith('/graph') ||
    path.startsWith('/scenarios') ||
    path.startsWith('/congestion') ||
    path.startsWith('/simulate') ||
    path.startsWith('/health')
  );
}

// Fetch event handler
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Non-GET requests always bypass service worker
  if (req.method !== 'GET') {
    return;
  }

  // 1. API Requests — STRICTLY NETWORK ONLY (Never cache!)
  if (isApiRequest(url)) {
    event.respondWith(
      fetch(req).catch(() => {
        // Return clear JSON error payload indicating backend unavailability
        return new Response(
          JSON.stringify({
            error: 'Backend unavailable. SmartRoute routing requires an active connection to the server.',
            backend_unavailable: true
          }),
          {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'application/json' }
          }
        );
      })
    );
    return;
  }

  // 2. OpenStreetMap Tiles — Network first with cache fallback for smooth rendering
  if (url.hostname.includes('tile.openstreetmap.org')) {
    event.respondWith(
      fetch(req)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open('smartroute-tiles-v1').then((tileCache) => {
              tileCache.put(req, copy);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(req);
        })
    );
    return;
  }

  // 3. Static App Shell Assets — Stale-While-Revalidate
  event.respondWith(
    caches.match(req).then((cachedResponse) => {
      const fetchPromise = fetch(req)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(req, responseToCache);
            });
          }
          return networkResponse;
        })
        .catch((err) => {
          // If offline and not in cache, fallback to app shell root
          if (req.mode === 'navigate') {
            return caches.match('./index.html');
          }
          throw err;
        });

      return cachedResponse || fetchPromise;
    })
  );
});
