/* CreatorForge service worker: minimal offline shell cache.
 * This is a local dashboard, not a public site. The worker caches the
 * app shell (HTML/CSS/JS + icons) so the installed PWA opens fast and
 * works when the backend is briefly unreachable. API responses
 * (/catalog, /chat/*, ...) are NEVER cached -- they always hit the
 * network so approvals and catalog data stay live.
 */
const CACHE = 'creatorforge-shell-v1';
const SHELL = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return; // let POSTs through
  const isApi = url.pathname.startsWith('/catalog')
    || url.pathname.startsWith('/chat')
    || url.pathname.startsWith('/identity')
    || url.pathname.startsWith('/pay')
    || url.pathname.startsWith('/post')
    || url.pathname.startsWith('/docs')
    || url.pathname.startsWith('/openapi');
  if (isApi) return; // network-only: never serve stale API data
  event.respondWith(
    caches.match(event.request).then(
      (cached) => cached || fetch(event.request)
    )
  );
});
