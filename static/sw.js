// sw.js
const CACHE_NAME = 'neurotask-offline-v1';
const OFFLINE_URL = '/offline.html'; // (optional fallback)

// Install Phase: Pre-cache critical assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        // Cache only valid, accessible URLs.
        return cache.addAll([
          '/',
          '/static/output.css'
          // Add other valid assets here.
          // e.g., '/static/notification-icon.png'
        ]);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate Phase: Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Phase: Intercept network requests
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Check if the request's Accept header indicates a Server-Sent Event.
  const acceptHeader = event.request.headers.get('Accept') || '';
  if (acceptHeader.includes('text/event-stream')) {
    // For SSE requests, do not intercept; let the browser handle it.
    return;
  }

  // Optionally, you can also check the pathname:
  if (url.pathname.startsWith('/stream')) {
    return;
  }

  // Only handle GET requests.
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Open the cache and store a clone of the response.
        return caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, response.clone());
          return response;
        });
      })
      .catch(() => {
        // If the network fetch fails, try to return a cached response.
        return caches.match(event.request) || new Response('Offline', {
          status: 503,
          statusText: 'Offline'
        });
      })
  );
});

// Message event handler for skipWaiting.
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
