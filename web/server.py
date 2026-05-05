"""Small standard-library web server for the XRPFi browser demo."""

from __future__ import annotations

import asyncio
import json
import mimetypes
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

WEB_ROOT = Path(__file__).parent
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
}

DemoRunner = Callable[[], Awaitable[dict[str, Any]]]


def serve(runner: DemoRunner, host: str = "127.0.0.1", port: int = 8088) -> None:
    """Serve the browser UI and demo API until interrupted."""

    class DemoRequestHandler(BaseHTTPRequestHandler):
        server_version = "XRPFiDemo/1.0"

        def do_GET(self) -> None:
            if self.path == "/api/health":
                self._send_json({"ok": True})
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
