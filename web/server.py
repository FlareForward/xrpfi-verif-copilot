"""Small standard-library web server for the XRPFi browser demo."""

from __future__ import annotations

import asyncio
import inspect
import json
import mimetypes
from asyncio import iscoroutine
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any

from src.session import load_sessions

WEB_ROOT = Path(__file__).parent
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/app.js": "app.js",
}

DemoRunner = Callable[..., Awaitable[dict[str, Any]] | dict[str, Any] | None]

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

    event_queue: Queue[dict[str, Any]] = Queue()
    run_lock = Lock()
    run_state: dict[str, Any] = {
        "state": "idle",
        "records": [],
        "result": None,
        "error": None,
    }

    def set_run_state(
        state: str | None = None,
        records: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with run_lock:
            if state is not None:
                run_state["state"] = state
            if records is not None:
                run_state["records"] = records
            if result is not None:
                run_state["result"] = result
            run_state["error"] = error

    def get_run_state() -> dict[str, Any]:
        with run_lock:
            return dict(run_state)

    def push_step(event: dict[str, Any]) -> None:
        event_queue.put(event)

    async def call_runner() -> dict[str, Any]:
        parameters = inspect.signature(runner).parameters
        result = runner(step_callback=push_step) if "step_callback" in parameters else runner()
        if iscoroutine(result):
            result = await result
        return result or {}

    def run_demo_background() -> None:
        set_run_state(state="running", records=[], result=None, error=None)
        try:
            result = asyncio.run(call_runner())
            records = result.get("records") or result.get("decisions") or []
            done_event = {"step": "done", "records": records, "result": result}
            event_queue.put(done_event)
            set_run_state(state="done", records=records, result=result)
        except Exception as exc:
            message = str(exc)
            event_queue.put({"step": "error", "error": message})
            set_run_state(state="error", error=message)

    def start_demo() -> bool:
        if get_run_state()["state"] == "running":
            return False
        while True:
            try:
                event_queue.get_nowait()
            except Empty:
                break
        thread = Thread(target=run_demo_background, daemon=True)
        thread.start()
        return True

    class DemoRequestHandler(BaseHTTPRequestHandler):
        server_version = "XRPFiDemo/1.0"

        def do_GET(self) -> None:
            if self.path == "/api/health":
                self._send_json({"ok": True})
                return

            if self.path == "/prices":
                self._send_json(_get_prices_payload())
                return

            if self.path == "/sessions":
                self._send_json({"ok": True, "sessions": load_sessions()})
                return

            if self.path == "/status":
                self._send_json(get_run_state())
                return

            if self.path == "/stream":
                self._send_stream()
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
            if self.path not in {"/api/run", "/run"}:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            started = start_demo()
            self._send_json({"ok": True, "state": get_run_state()["state"], "started": started})

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

        def _send_stream(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            while True:
                try:
                    event = event_queue.get(timeout=15)
                except Empty:
                    try:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    continue

                payload = json.dumps(event).encode("utf-8")
                try:
                    self.wfile.write(b"data: " + payload + b"\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                if event.get("step") in {"done", "error"}:
                    return

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


if __name__ == "__main__":
    from demo.judge_demo import run_judge_demo

    serve(run_judge_demo)
