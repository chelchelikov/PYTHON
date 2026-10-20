"""Сравнение загрузки статических ресурсов напрямую с origin и через CDN.

Для каждого ресурса выполняется по два запроса к origin и к CDN; печатаются
код ответа, время, размер и заголовки кэширования.
Использование: python check_cdn.py [CDN_BASE_URL]
"""

import sys
import time

import requests

ORIGIN = "http://127.0.0.1:8080/static"
CDN = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8081/static"
RESOURCES = ["images/standard.png", "images/deluxe.png", "images/suite.png",
             "css/style.css", "js/app.js"]
HEADERS = ("Content-Type", "Cache-Control", "Age", "X-Cache", "X-Served-By", "ETag",
           "Last-Modified")


def fetch(url: str) -> None:
    start = time.perf_counter()
    response = requests.get(url, timeout=10)
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  {url}\n    HTTP {response.status_code}, {elapsed:.1f} мс, "
          f"{len(response.content)} байт")
    for name in HEADERS:
        if name in response.headers:
            print(f"    {name}: {response.headers[name]}")


def main() -> None:
    for resource in RESOURCES:
        print(f"\n===== {resource} =====")
        for label, base in (("origin", ORIGIN), ("CDN", CDN)):
            for attempt in (1, 2):
                print(f" {label}, запрос {attempt}:")
                fetch(f"{base}/{resource}")


if __name__ == "__main__":
    main()
