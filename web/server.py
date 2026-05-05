"""Small standard-library web server for the XRPFi browser demo."""

from __future__ import annotations

import asyncio
import json
import mimetypes
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any

WEB_ROOT = Path(__file__).parent
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
}

DemoRunner = Callable[[], Awaitable[dict[str, Any]]]

PRICE_TIMEOUT_SECONDS = 2.5
_PRICE_CACHE_LOCK = Lock()
_PRICE_CACHE: dict[str, Any] = {
    "flr_usd": 0.0076,
    "xrp_usd": 1.41,
    "timestamp": datetime.now(UTC).isoformat(),
    "is_stale": True,
}


async def _read_prices() -> dict[str, Any]:
    from src.integrations.ftso.client import FtsoClient

    client = FtsoClient(timeout=0.75)
    prices = await asyncio.wait_for(
        client.get_prices(["FLR/USD", "XRP/USD"]),
        timeout=PRICE_TIMEOUT_SECONDS,
    )
    by_name = {price.feed_name: price for price in prices}
    flr = by_name["FLR/USD"]
    xrp = by_name["XRP/USD"]
    timestamp = max(flr.timestamp, xrp.timestamp).isoformat()
    is_stale = flr.is_stale or xrp.is_stale
    return {
        "flr_usd": flr.price_usd,
        "xrp_usd": xrp.price_usd,
        "timestamp": timestamp,
        "is_stale": is_stale,
    }


def _get_prices_payload() -> dict[str, Any]:
    global _PRICE_CACHE

    try:
        payload = asyncio.run(_read_prices())
    except Exception:
        with _PRICE_CACHE_LOCK:
            return {**_PRICE_CACHE, "is_stale": True}

    with _PRICE_CACHE_LOCK:
        _PRICE_CACHE = payload
        return dict(_PRICE_CACHE)


def serve(runner: DemoRunner, host: str = "127.0.0.1", port: int = 8088) -> None:
    """Serve the browser UI and demo API until interrupted."""

    class DemoRequestHandler(BaseHTTPRequestHandler):
        server_version = "XRPFiDemo/1.0"

        def do_GET(self) -> None:
            if self.path == "/api/health":
                self._send_json({"ok": True})
                return

            if self.path == "/prices":
                self._send_json(_get_prices_payload())
                return

            file_name = STATIC_FILES.get(self.path)
            if file_name is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            self._send_static(file_name)

        def do_HEAD(self) -> None:
            file_name = STATIC_FILES.get(self.path)
            if file_name is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            self._send_static(file_name, include_body=False)

        def do_POST(self) -> None:
            if self.path != "/api/run":
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            try:
                result = asyncio.run(runner())
            except Exception as exc:
                self._send_json(
                    {"ok": False, "error": str(exc)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            self._send_json({"ok": True, "result": result})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_static(self, file_name: str, include_body: bool = True) -> None:
            path = WEB_ROOT / file_name
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer((host, port), DemoRequestHandler)
    url = f"http://{host}:{port}"
    print(f"XRPFi browser demo running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        httpd.server_close()
