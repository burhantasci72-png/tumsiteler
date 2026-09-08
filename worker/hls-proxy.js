/**
 * Cloudflare Worker - HLS proxy
 *
 * Tarayicilar JS'ten Referer / Origin / User-Agent basliklarini AYARLAYAMAZ
 * (forbidden header names). Bu yuzden hotlink korumali yayinlar web
 * oynaticida 403 verir. Ayrica yayin sunuculari CORS basligi gondermez,
 * bu da hls.js'in manifesti okumasini engeller.
 *
 * Bu worker iki sorunu da cozer:
 *   1. Upstream'e dogru Referer/Origin/User-Agent enjekte eder.
 *   2. Yanita permissive CORS baslıklari ekler.
 *   3. m3u8 icerigindeki segment/anahtar/varyant adreslerini yeniden yazar
 *      ki alt istekler de proxy uzerinden gecsin.
 *
 * Dagitim:
 *   npx wrangler deploy
 *
 * Kullanim:
 *   https://<worker>/hls?url=<m3u8>&ref=<referer>&ua=<user-agent>
 */

const DEFAULT_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

// Sadece bu uzantilar/proxy trafigine izin ver (acik proxy olmasin diye).
const ALLOWED_HOSTS = null; // ornek: ["example.com"] ; null = hepsi

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,HEAD,OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Access-Control-Expose-Headers": "*",
};

function bad(message, status = 400) {
  return new Response(message, { status, headers: CORS });
}

function isPlaylist(contentType, url) {
  const type = (contentType || "").toLowerCase();
  return (
    type.includes("mpegurl") ||
    type.includes("m3u") ||
    url.toLowerCase().includes(".m3u8")
  );
}

/** Proxy adresi uretir; alt istekler de ayni referer/ua ile gecsin. */
function proxify(target, base, ref, ua) {
  const absolute = new URL(target, base).toString();
  const params = new URLSearchParams({ url: absolute });
  if (ref) params.set("ref", ref);
  if (ua && ua !== DEFAULT_UA) params.set("ua", ua);
  return `/hls?${params.toString()}`;
}

/**
 * m3u8 govdesini yeniden yazar:
 *  - segment / varyant satirlari
 *  - #EXT-X-KEY URI="..."
 *  - #EXT-X-MAP URI="..."
 *  - #EXT-X-MEDIA URI="..."
 */
function rewritePlaylist(body, base, ref, ua) {
  const rewriteAttr = (line, attr) =>
    line.replace(new RegExp(`${attr}="([^"]+)"`, "g"), (_m, uri) =>
      `${attr}="${proxify(uri, base, ref, ua)}"`
    );

  return body
    .split("\n")
    .map((raw) => {
      const line = raw.trim();
      if (!line) return raw;

      if (line.startsWith("#")) {
        let out = line;
        if (out.startsWith("#EXT-X-KEY") || out.startsWith("#EXT-X-SESSION-KEY")) {
          out = rewriteAttr(out, "URI");
        } else if (out.startsWith("#EXT-X-MAP")) {
          out = rewriteAttr(out, "URI");
        } else if (out.startsWith("#EXT-X-MEDIA")) {
          out = rewriteAttr(out, "URI");
        }
        return out;
      }

      // Segment veya varyant playlist satiri
      return proxify(line, base, ref, ua);
    })
    .join("\n");
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    const requestUrl = new URL(request.url);
    if (requestUrl.pathname === "/" || requestUrl.pathname === "/health") {
      return new Response("hls-proxy ok", { headers: CORS });
    }
    if (requestUrl.pathname !== "/hls") {
      return bad("not found", 404);
    }

    const target = requestUrl.searchParams.get("url");
    if (!target) return bad("missing url");

    let upstream;
    try {
      upstream = new URL(target);
    } catch {
      return bad("invalid url");
    }
    if (!/^https?:$/.test(upstream.protocol)) return bad("bad scheme");
    if (ALLOWED_HOSTS && !ALLOWED_HOSTS.includes(upstream.hostname)) {
      return bad("host not allowed", 403);
    }

    const ref = requestUrl.searchParams.get("ref") || "";
    const ua = requestUrl.searchParams.get("ua") || DEFAULT_UA;

    const headers = new Headers({
      "User-Agent": ua,
      Accept: "*/*",
      "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    });
    if (ref) {
      headers.set("Referer", ref);
      try {
        headers.set("Origin", new URL(ref).origin);
      } catch {
        /* gecersiz referer - Origin atlanir */
      }
    }
    // Video seek / segment araligi destegi
    const range = request.headers.get("Range");
    if (range) headers.set("Range", range);

    let response;
    try {
      response = await fetch(upstream.toString(), {
        headers,
        redirect: "follow",
        cf: { cacheTtl: 0, cacheEverything: false },
      });
    } catch (err) {
      return bad(`upstream error: ${err}`, 502);
    }

    const outHeaders = new Headers(CORS);
    const contentType = response.headers.get("Content-Type") || "";
    if (contentType) outHeaders.set("Content-Type", contentType);
    for (const key of ["Content-Range", "Accept-Ranges", "Content-Length"]) {
      const value = response.headers.get(key);
      if (value) outHeaders.set(key, value);
    }
    outHeaders.set("Cache-Control", "no-store");

    if (!response.ok) {
      return new Response(`upstream ${response.status}`, {
        status: response.status,
        headers: outHeaders,
      });
    }

    // Playlist ise yeniden yaz, degilse (segment) akisi oldugu gibi gecir.
    // Yonlendirme SONRASI adres kontrol edilir: cozucu adresler (/?ID=kanal)
    // .m3u8 icermez ama 302 ile gercek playlist'e gider.
    const finalUrl = response.url || upstream.toString();
    if (isPlaylist(contentType, finalUrl) || isPlaylist(contentType, upstream.pathname)) {
      const body = await response.text();
      outHeaders.set("Content-Type", "application/vnd.apple.mpegurl");
      outHeaders.delete("Content-Length");
      return new Response(rewritePlaylist(body, finalUrl, ref, ua), {
        status: 200,
        headers: outHeaders,
      });
    }

    return new Response(response.body, { status: response.status, headers: outHeaders });
  },
};
