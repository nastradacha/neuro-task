const CACHE_NAME = 'neurotask-offline-v1';
const OFFLINE_URL = '/offline.html'; // Optional fallback
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
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

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});


// Fetch Event - Network First with Cache Fallback
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Skip non-GET and non-API requests
  if (event.request.method !== 'GET') return;

  // Handle API routes with Network-First + Cache-Update strategy
  if (url.pathname.startsWith('/tasks')) {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          // Update cache with fresh response
          const cloned = networkResponse.clone();
          caches.open(CACHE_NAME)
            .then(cache => cache.put(event.request, cloned));
          return networkResponse;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Existing static asset handling
  event.respondWith(/* ...existing static cache logic... */);
});

// Add to sw.js
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});