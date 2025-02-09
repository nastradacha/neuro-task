const CACHE_NAME = 'neurotask-offline-v1';
const OFFLINE_URL = '/offline.html'; // Optional fallback
const STATIC_ASSETS = [
  '/',
  '/static/output.css',
  '/static/main.css',
  '/static/icons/*',
  '/templates/index.html',
  '/static/notification-icon.png'
];

// Install Phase: Pre-cache critical assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll([
          '/',
          '/static/output.css',
          '/templates/index.html'
        ]);
      })
      .then(() => self.skipWaiting())
  );
});

// Fetch Event: Network-first with cache fallback
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Cache successful responses
        const clone = response.clone();
        caches.open(CACHE_NAME)
          .then(cache => cache.put(event.request, clone));
        return response;
      })
      .catch(() => {
        // Fallback 1: Return cached version
        return caches.match(event.request)
          .then(cached => {
            // Fallback 2: Show offline page
            if (!cached && event.request.mode === 'navigate') {
              return caches.match(OFFLINE_URL);
            }
            return cached;
          });
      })
  );
});