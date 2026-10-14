/* Cache apenas a interface. Consultas e respostas da ANA nunca são armazenadas. */
const CACHE = 'pluvioana-web-v3';
const UI = ['/', '/index.html', '/style.css', '/app.js', '/manifest.webmanifest',
            '/icons/icon-192.png', '/icons/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(UI)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('pluvioana-') && key !== CACHE).map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin ||
      url.pathname.startsWith('/api/')) return;
  if (!UI.includes(url.pathname)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy=response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request,copy));
    }
    return response;
  }).catch(() => caches.match(event.request)));
});
