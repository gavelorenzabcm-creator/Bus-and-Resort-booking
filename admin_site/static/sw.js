// Minimal service worker for the BusResort Admin PWA.
// Its main job is to satisfy the browser's installability requirement
// (a fetch handler must be registered). It also does light caching of the
// app shell so the dashboard opens instantly even on a flaky connection.

const CACHE_NAME = "busresort-admin-shell-v1";
const APP_SHELL = [
  "/admin",
  "/admin/static/icons/icon-192.png",
  "/admin/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Network-first for everything: admin data must always be fresh.
// Falls back to cache only if the network request fails outright
// (e.g. briefly offline), so bookings/stats are never served stale.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => {});
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});