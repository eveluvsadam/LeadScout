"""Run LeadScout as a native macOS desktop window — no browser needed.

Starts the FastAPI server on a local port inside a background thread, then
opens a native window (macOS's built-in WebKit, via pywebview) pointing at it.
Launch with:  python -m app.desktop
"""
import socket
import threading
import time
import urllib.request

import uvicorn

from .main import app as fastapi_app

HOST = "127.0.0.1"


def _free_port() -> int:
    s = socket.socket()
    s.bind((HOST, 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serve(port: int) -> None:
    """Run uvicorn in this (background) thread without touching signal handlers."""
    server = uvicorn.Server(uvicorn.Config(
        fastapi_app, host=HOST, port=port, log_level="warning"))
    # Signal handlers can only be installed on the main thread; skip them here.
    server.install_signal_handlers = lambda: None
    server.run()


def _wait_until_up(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            return True
        except Exception:
            time.sleep(0.15)
    return False


def main() -> None:
    port = _free_port()
    url = f"http://{HOST}:{port}"
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    if not _wait_until_up(url):
        raise RuntimeError("LeadScout server failed to start.")

    import webview  # imported here so a missing GUI dep gives a clear message
    webview.create_window("LeadScout", url, width=1240, height=880,
                          min_size=(900, 640))
    webview.start()


if __name__ == "__main__":
    main()
