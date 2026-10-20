const CACHE_NAME = "data-insight-pwa-v1";
const ASSETS_TO_CACHE = [
  "/",
  "/manifest.json",
  "/static/style.css",
  "/static/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
  "/static/icons/favicon.ico",
  "https://cdn.jsdelivr.net/npm/chart.js"
];

// 1. Service Worker 설치 시 정적 자산 캐싱
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[Service Worker] 핵심 정적 자산 캐싱 완료");
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn("[Service Worker] 일부 자산 캐싱 실패 (무시 가능):", err);
      });
    })
  );
  self.skipWaiting();
});

// 2. 활성화 시 이전 버전 캐시 정리
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            console.log("[Service Worker] 구버전 캐시 정리:", key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// 3. 네트워크 요청 가로채기 (API 요청은 Network-First, 정적 리소스는 Stale-While-Revalidate)
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // POST 요청이나 백엔드 API 요청은 캐시하지 않고 네트워크로 직행
  if (
    event.request.method !== "GET" ||
    url.pathname.startsWith("/inspect") ||
    url.pathname.startsWith("/suggest") ||
    url.pathname.startsWith("/run") ||
    url.pathname.startsWith("/explain") ||
    url.pathname.startsWith("/query_visualize") ||
    url.pathname.startsWith("/verify_pin") ||
    url.pathname.startsWith("/health")
  ) {
    return;
  }

  // 정적 리소스 및 메인 페이지: 캐시 우선 / 백그라운드 업데이트
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        // 캐시가 있으면 먼저 반환하고, 백그라운드에서 최신 버전 fetch
        fetch(event.request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(event.request, networkResponse);
              });
            }
          })
          .catch(() => {
            /* 오프라인 시 조용히 무시 */
          });
        return cachedResponse;
      }

      // 캐시에 없으면 네트워크에서 가져온 후 캐시에 저장
      return fetch(event.request)
        .then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== "basic") {
            return networkResponse;
          }
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
          return networkResponse;
        })
        .catch(() => {
          // 완전 오프라인일 때 메인 페이지 반환
          if (event.request.mode === "navigate") {
            return caches.match("/");
          }
        });
    })
  );
});
