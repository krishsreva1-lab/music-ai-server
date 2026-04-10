// sw.js — Service Worker for background audio keep-alive
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));

// Keep service worker alive during audio playback
self.addEventListener('fetch', e => {
    // Passthrough — we just need the SW registered for media session
    e.respondWith(fetch(e.request).catch(() => new Response('')));
});