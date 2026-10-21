/* 赛博保姆 Service Worker
   策略：
   - 导航请求 network-first（保证拿到最新版本，断网回落缓存）
   - 同源静态资源 cache-first + 后台更新（图片、manifest、图标）
   - 跨域请求完全不接管
   升级时改 VERSION，activate 阶段清掉旧缓存。 */

const VERSION = 'v3.3.0';
const CACHE = 'cyber-nanny-' + VERSION;
const CORE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './assets/nanny-normal.webp',
  './assets/nanny-happy.webp',
  './assets/nanny-angry.webp',
  './assets/nanny-sleepy.webp',
  './assets/icon-192.png',
  './assets/icon-512.png',
  './assets/icon-maskable-512.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(CORE))
      .catch(() => {})            // 个别资源 404 也不该让整个安装失败
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET') return;

  let url;
  try{ url = new URL(req.url); }catch(err){ return; }
  if(url.origin !== self.location.origin) return;

  const isHTML = req.mode === 'navigate' ||
                 (req.headers.get('accept') || '').includes('text/html');

  if(isHTML){
    e.respondWith(
      fetch(req, { cache: 'no-cache' })
        .then(res => {
          if(res && res.ok){
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(req).then(hit => hit || caches.match('./index.html')))
    );
    return;
  }

  e.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req)
        .then(res => {
          if(res && res.ok){
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => hit);
      return hit || net;
    })
  );
});
