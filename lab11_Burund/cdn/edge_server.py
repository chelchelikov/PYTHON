"""Локальная имитация CDN edge-сервера (порт 8081).

При первом запросе ресурс забирается с origin (X-Cache: MISS) и кладётся в кэш
edge-сервера; повторные запросы в пределах max-age отдаются из кэша (X-Cache: HIT)
с заголовком Age. Для всех ресурсов выставляется Cache-Control: public, max-age=...
"""

import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORIGIN = "http://127.0.0.1:8080"
PORT = 8081
MAX_AGE = {".png": 86400, ".jpg": 86400, ".css": 3600, ".js": 3600, ".html": 60}
DEFAULT_MAX_AGE = 300

_cache: dict[str, tuple[float, int, dict[str, str], bytes]] = {}
_lock = threading.Lock()


def max_age_for(path: str) -> int:
    for extension, seconds in MAX_AGE.items():
        if path.endswith(extension):
            return seconds
    return DEFAULT_MAX_AGE


class EdgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        now = time.time()
        max_age = max_age_for(self.path)
        with _lock:
            entry = _cache.get(self.path)
        if entry and now - entry[0] < max_age:
            stored_at, status, headers, body = entry
            self._reply(status, headers, body, "HIT", int(now - stored_at), max_age)
            return
        try:
            with urllib.request.urlopen(ORIGIN + self.path, timeout=5) as response:
                status, body = response.status, response.read()
                headers = {"Content-Type": response.headers.get("Content-Type",
                                                                "application/octet-stream")}
        except urllib.error.HTTPError as error:
            self._reply(error.code, {"Content-Type": "text/plain"}, error.read(), "MISS", 0, 0)
            return
        except urllib.error.URLError:
            self._reply(502, {"Content-Type": "text/plain; charset=utf-8"},
                        "Origin недоступен".encode(), "MISS", 0, 0)
            return
        with _lock:
            _cache[self.path] = (now, status, headers, body)
        self._reply(status, headers, body, "MISS", 0, max_age)

    def _reply(self, status, headers, body, cache_state, age, max_age):
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        if max_age:
            self.send_header("Cache-Control", f"public, max-age={max_age}")
        self.send_header("Age", str(age))
        self.send_header("X-Cache", cache_state)
        self.send_header("X-Served-By", "edge-local-1")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[edge] {self.path} {args[1] if len(args) > 1 else ''}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EdgeHandler)
    print(f"CDN edge: http://127.0.0.1:{PORT}/static/  (origin {ORIGIN})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
