const CACHE_VERSION = 3;
const STATIC_CACHE = `neurotask-static-v${CACHE_VERSION}`;
const API_CACHE = `neurotask-api-v${CACHE_VERSION}`;
const OFFLINE_URL = '/offline.html';
const SYNC_TAG = 'sync-offline-edits';

// ------------------------------
// IndexedDB helper for offline edits
// ------------------------------
function openSyncDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('neurotask-offline', 2);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('offlineEdits')) {
        db.createObjectStore('offlineEdits', { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Helper: Returns a promise that resolves when the transaction completes.
function txComplete(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

async function queueFailedRequest(request) {
  try {
    const body = await request.clone().json();
    const db = await openSyncDB();
    const tx = db.transaction('offlineEdits', 'readwrite');
    const store = tx.objectStore('offlineEdits');
    store.put({
      url: request.url,
      method: request.method,
      payload: body,
      timestamp: Date.now(),
      retries: 0
    });
    console.log('[ServiceWorker] Queued failed request:', request.url);
    return txComplete(tx);
  } catch (err) {
    console.error('[ServiceWorker] Error queueing failed request:', err);
  }
}

// ------------------------------
// Cache and offline asset helpers
// ------------------------------
async function fetchAndCache(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    return cached || caches.match(OFFLINE_URL);
  }
}

// ------------------------------
// API request handling
// ------------------------------
async function handleApiRequest(request) {
  const cache = await caches.open(API_CACHE);
  try {
    // Network-first strategy for API requests
    const networkResponse = await fetch(request);
    if (request.method === 'GET' && networkResponse.ok) {
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (err) {
    console.warn('[ServiceWorker] Network request failed, serving from cache:', request.url);
    if (request.method !== 'GET') {
      await queueFailedRequest(request);
      return new Response(JSON.stringify({ status: 'queued' }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
    const cached = await cache.match(request);
    return cached || Response.error();
  }
}

// ------------------------------
// Install Event: Cache core assets
// ------------------------------
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        return cache.addAll([
          '/',
          '/offline.html'
        ]);
      })
      .catch(err => {
        console.error('[ServiceWorker] Failed to cache core assets:', err);
      })
      .then(() => self.skipWaiting())
  );
});

// ------------------------------
// Activate Event: Cleanup old caches
// ------------------------------
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== STATIC_CACHE && k !== API_CACHE)
          .map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// ------------------------------
// Fetch Event: Single consolidated handler
// ------------------------------
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }
  if (event.request.method !== 'GET' || 
      url.pathname.startsWith('/stream') ||
      event.request.headers.get('Accept')?.includes('text/event-stream')) {
    return;
  }
  if (event.request.headers.get('Content-Type')?.includes('application/json') ||
      url.pathname.startsWith('/tasks')) {
    event.respondWith(handleApiRequest(event.request.clone()));
    return;
  }
  event.respondWith(
    caches.match(event.request)
      .then(cached => cached || fetchAndCache(event.request, STATIC_CACHE))
  );
});

// ------------------------------
// Background Sync: Process queued offline edits
// ------------------------------
self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) {
    console.log('[ServiceWorker] Sync event fired!');
    event.waitUntil(processSyncQueue());
  }
});

async function processSyncQueue() {
  try {
    const db = await openSyncDB();
    const tx = db.transaction('offlineEdits', 'readonly');
    const store = tx.objectStore('offlineEdits');
    const offlineEdits = await store.getAll();

    for (const edit of offlineEdits) {
      try {
        // Check if task already exists on the server
        const checkRes = await fetch(edit.url, { method: 'HEAD' });
        if (checkRes.ok) {
          // Task exists - remove from queue without creating
          await db.transaction('offlineEdits', 'readwrite')
            .objectStore('offlineEdits').delete(edit.id);
          continue;
        }

        // Create/update task
        const req = new Request(edit.url, {
          method: edit.method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(edit.payload)
        });
        
        const res = await fetch(req);
        if (res.ok) {
          // Sync successful - remove from queue
          await db.transaction('offlineEdits', 'readwrite')
            .objectStore('offlineEdits').delete(edit.id);
        } else {
          // Retry logic with exponential backoff
          if (edit.retries < 5) {
            edit.retries++;
            edit.lastAttempt = Date.now();
            await db.transaction('offlineEdits', 'readwrite')
              .objectStore('offlineEdits').put(edit);
          } else {
            await db.transaction('offlineEdits', 'readwrite')
              .objectStore('offlineEdits').delete(edit.id);
          }
        }
      } catch (err) {
        console.error('Sync error:', err);
        if (edit.retries < 5) {
          edit.retries++;
          edit.lastAttempt = Date.now();
          await db.transaction('offlineEdits', 'readwrite')
            .objectStore('offlineEdits').put(edit);
        }
      }
    }
    updateClientTasks();
  } catch (err) {
    console.error('Sync queue processing failed:', err);
  }
}

async function updateClientTasks() {
  const clientsList = await self.clients.matchAll({ type: 'window' });
  clientsList.forEach(client => {
    client.postMessage({
      type: 'sync-complete',
      msg: 'Refresh your tasks list'
    });
  });
}

// ------------------------------
// Network Status Change Handling
// ------------------------------
self.addEventListener('online', () => {
  console.log('[ServiceWorker] Device is back online');
  updateClientNetworkStatus(true);
});

self.addEventListener('offline', () => {
  console.log('[ServiceWorker] Device is offline');
  updateClientNetworkStatus(false);
});

async function updateClientNetworkStatus(isOnline) {
  const clientsList = await self.clients.matchAll({ type: 'window' });
  clientsList.forEach(client => {
    client.postMessage({
      type: 'network-status',
      isOnline: isOnline
    });
  });
}
