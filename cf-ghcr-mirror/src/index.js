// ghcr.wangshun.work -> ghcr.io 反代
// 透传方法、头、body 与响应流(镜像层可达数百 MB,Workers 流式转发不占 CPU 配额)。
// 唯一改写:WWW-Authenticate 的 realm 指回本反代,让 docker login/token 流量也走 CF。
const UPSTREAM_HOST = "ghcr.io";

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204 });
    }

    const incoming = new URL(request.url);
    const proxyHost = incoming.hostname;

    const upstream = new URL(request.url);
    upstream.hostname = UPSTREAM_HOST;

    const response = await fetch(new Request(upstream, request));

    const wwwAuth = response.headers.get("www-authenticate");
    if (wwwAuth && wwwAuth.includes(UPSTREAM_HOST)) {
      const headers = new Headers(response.headers);
      headers.set(
        "www-authenticate",
        wwwAuth.replaceAll(`https://${UPSTREAM_HOST}`, `https://${proxyHost}`)
      );
      return new Response(response.body, { status: response.status, headers });
    }

    return response;
  },
};
