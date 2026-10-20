"""Origin-сервер статического контента (порт 8080).

Имитирует удалённый исходный сервер: добавляет задержку и не выставляет
заголовков кэширования.
"""

import os
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8080
ORIGIN_LATENCY = 0.15  # секунды: «дальний» сервер


class OriginHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        time.sleep(ORIGIN_LATENCY)
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Served-By", "origin")
        super().end_headers()


def main() -> None:
    handler = partial(OriginHandler, directory=ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    print(f"Origin: http://127.0.0.1:{PORT}/static/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
