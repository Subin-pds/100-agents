const CACHE = 'jarvis-shell-v2';
const SHELL = ['/', '/manifest.json', '/icon.svg', '/car-bg.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Network-first for the shell, bypassing HTTP cache too (cache: 'no-store')
// so every deploy shows up on next load. The cache is only a fallback for
// when the network is unreachable (tunnel, dead zone) — freshness matters
// more than offline support for a car assistant that's redeployed often.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || !SHELL.includes(url.pathname)) return;
  event.respondWith(
    fetch(event.request, { cache: 'no-store' })
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});
