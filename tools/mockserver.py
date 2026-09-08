#!/usr/bin/env python3
"""Testler icin sahte HLS sunucusu: saglikli / 403 / bos / master varyant."""
import http.server, socketserver, sys

SEG = b"\x47" + b"\x00" * 4095  # sahte TS segmenti

MEDIA = b"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:4
#EXT-X-MEDIA-SEQUENCE:1
#EXTINF:4.0,
seg1.ts
#EXTINF:4.0,
seg2.ts
"""

MASTER = b"""#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x720
media.m3u8
"""

PAGE = b"""<html><body><script>
var source = "http://127.0.0.1:%d/good.m3u8";
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/vnd.apple.mpegurl"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        port = self.server.server_address[1]

        if path == "/good.m3u8":
            return self._send(200, MEDIA)
        if path == "/master.m3u8":
            return self._send(200, MASTER)
        if path == "/media.m3u8":
            return self._send(200, MEDIA)

        # Hotlink korumali: dogru Referer yoksa 403
        if path == "/protected.m3u8":
            if self.headers.get("Referer") == "https://allowed.example/":
                return self._send(200, MEDIA)
            return self._send(403, b"forbidden", "text/plain")

        # Playlist 200 ama segment 403 (en sinsi hata)
        if path == "/badseg.m3u8":
            return self._send(
                200, MEDIA.replace(b"seg1.ts", b"denied.ts")
            )
        if path == "/denied.ts":
            return self._send(403, b"no", "text/plain")

        if path == "/empty.m3u8":
            return self._send(200, b"#EXTM3U\n#EXT-X-ENDLIST\n")
        if path == "/notm3u8.m3u8":
            return self._send(200, b"<html>hello</html>", "text/html")
        if path == "/dead.m3u8":
            return self._send(404, b"nope", "text/plain")
        if path == "/page.html":
            return self._send(200, PAGE % port, "text/html")
        if path.endswith(".ts"):
            return self._send(200, SEG, "video/mp2t")

        return self._send(404, b"nf", "text/plain")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"mock on {port}", flush=True)
        httpd.serve_forever()
