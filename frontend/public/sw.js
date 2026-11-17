const C = "sniper-v1", A = "sniper-assets-v1";
self.addEventListener("install", e => { e.waitUntil(caches.open(C).then(c => c.addAll(["/offline.html"]))); self.skipWaiting(); });
self.addEventListener("activate", e => e.waitUntil(clients.claim()));
self.addEventListener("fetch", e => {
  const r = e.request, u = new URL(r.url);
  if (r.mode === "navigate") { e.respondWith(fetch(r).catch(() => caches.match("/offline.html"))); return; }
  // v3.16: Vite build files are content-hashed (immutable), so they are served from cache after the first load. API calls are never cached.
  if (r.method === "GET" && u.origin === self.location.origin && u.pathname.startsWith("/assets/"))
    e.respondWith(caches.open(A).then(c => c.match(r).then(hit => hit || fetch(r).then(res => { if (res.ok) c.put(r, res.clone()); return res; }))));
});
