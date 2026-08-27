const CACHE = 'tp-v57';
const API_CACHE = 'tp-api';   // данные API — переживают обновления приложения
// ВАЖНО: пути со штампом ?v= должны совпадать со <script src> в index.html — иначе страница
// просит один URL, а в кэше лежит другой, и обновление до пользователя не доезжает.
const ASSET_V = '20260827a';
const PRECACHE = ['/', '/index.html', '/login.html', `/app.js?v=${ASSET_V}`, `/offline.js?v=${ASSET_V}`, '/manifest.json',
                  '/vendor/tailwind.js', '/vendor/alpine.min.js', '/vendor/chart.min.js', '/vendor/jsbarcode.min.js'];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)));
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then(keys =>
            // удаляем старые версии shell-кэша, НО сохраняем API-кэш (данные для офлайна)
            Promise.all(keys.filter(k => k !== CACHE && k !== API_CACHE).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// fetch с таймаутом — при «зависшем TLS» (ТСПУ/перебои) не ждём вечно, а отдаём кэш
function fetchTimeout(req, ms) {
    return new Promise((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('timeout')), ms);
        fetch(req).then(r => { clearTimeout(t); resolve(r); }, err => { clearTimeout(t); reject(err); });
    });
}

self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url);

    // API: GET — network-first с резервом из кэша (офлайн-чтение последних данных).
    //      Записи (POST/PUT/DELETE) приложение само ставит в очередь до вызова сети — здесь просто пропускаем.
    if (url.pathname.startsWith('/api/')) {
        if (e.request.method !== 'GET') return;  // пусть идёт в сеть; офлайн обрабатывает app
        e.respondWith(
            fetchTimeout(e.request, 4000).then(res => {
                if (res && res.ok) { const clone = res.clone(); caches.open(API_CACHE).then(c => c.put(e.request, clone)); }
                return res;
            }).catch(() => caches.open(API_CACHE).then(c => c.match(e.request)).then(c =>
                c || new Response(JSON.stringify({ detail: 'Нет сети и нет кэша' }), { status: 503, headers: { 'Content-Type': 'application/json' } })
            ))
        );
        return;
    }

    // App shell (навигация, HTML, app.js, offline.js): NETWORK-FIRST — фиксы приходят сразу,
    // а сломанная сборка не залипает в кэше; офлайн — из кэша.
    const isShell = e.request.mode === 'navigate'
        || url.pathname === '/' || url.pathname.endsWith('.html')
        || url.pathname === '/app.js' || url.pathname === '/offline.js';
    if (isShell) {
        // 12 с, а не 4: на медленном канале (ТСПУ) короткий таймаут молча закреплял за
        // пользователем старую сборку из кэша — фронт отставал от бэкенда неделями.
        e.respondWith(
            fetchTimeout(e.request, 12000).then(res => {
                if (res.ok) { const clone = res.clone(); caches.open(CACHE).then(c => c.put(e.request, clone)); }
                return res;
            }).catch(() => caches.match(e.request).then(c => c || caches.match('/index.html')))
        );
        return;
    }

    // Статика (vendor, иконки, manifest): cache-first.
    e.respondWith(
        caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
            if (res.ok) { const clone = res.clone(); caches.open(CACHE).then(c => c.put(e.request, clone)); }
            return res;
        }))
    );
});
