import asyncio
import json
import os
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from websockets.server import serve

try:  # Optional for lightweight testing environments
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - handled in __init__
    WhisperModel = None  # type: ignore

SR = 16000


def check_environment(host: str, port: int, log_dir: str) -> None:
    """Validate basic runtime assumptions before starting the server."""
    os.makedirs(log_dir, exist_ok=True)
    if not os.access(log_dir, os.W_OK):
        raise RuntimeError(f"Log directory {log_dir!r} is not writable")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((host, port)) == 0:
            raise RuntimeError(f"Port {port} already in use on {host}")


class Logger:
    """Minimal structured logger with request IDs."""

    def __init__(self) -> None:
        self.level = os.getenv("LOG_LEVEL", "INFO").upper()

    def _log(
        self, level: str, msg: str, request_id: str | None = None
    ) -> None:
        if level not in {"INFO", "WARN", "ERROR"}:
            return
        if level == "INFO" and self.level not in {"INFO"}:
            return
        if level == "WARN" and self.level not in {"INFO", "WARN"}:
            return
        rid = request_id or "-"
        print(
            f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {level} [{rid}] {msg}"
        )

    def info(self, msg: str, request_id: str | None = None) -> None:
        self._log("INFO", msg, request_id)

    def warn(self, msg: str, request_id: str | None = None) -> None:
        self._log("WARN", msg, request_id)

    def error(self, msg: str, request_id: str | None = None) -> None:
        self._log("ERROR", msg, request_id)


log = Logger()


class ASRServer:
    def __init__(
        self,
        model_size: str | None = None,
        compute_type: str | None = None,
        model: object | None = None,
    ) -> None:
        if model is not None:
            self.model = model
        else:
            if WhisperModel is None:
                raise RuntimeError("faster-whisper is not installed")
            ms = model_size or os.getenv("ASR_MODEL_SIZE", "medium")
            ct = compute_type or os.getenv("ASR_COMPUTE_TYPE", "int8_float16")
            self.model = WhisperModel(ms, compute_type=ct)
        self.lang: str | None = None
        self.buf = np.zeros(0, dtype=np.float32)
        self.last_emit = 0.0
        self.last_partial = ""
        self.last_partial_time = 0.0

    def set_language(self, code):
        self.lang = code or None

    def append_pcm16(self, b: bytes):
        pcm = np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768.0
        self.buf = np.concatenate([self.buf, pcm])

    def pop_window(self, seconds=2.0, keep=1.0):
        need = int(SR * seconds)
        if len(self.buf) < need:
            return None
        window = self.buf[-need:]
        self.buf = self.buf[-int(SR * keep):]
        return window

    def transcribe_window(self, audio: np.ndarray):
        segs, info = self.model.transcribe(
            audio,
            language=self.lang,
            vad_filter=True,
            beam_size=1,
        )
        text = "".join(s.text for s in segs).strip()
        return text


HOST = os.getenv("ASR_HOST", "127.0.0.1")
PORT = int(os.getenv("ASR_PORT", "8765"))
LOG_DIR = os.getenv("ASR_LOG_DIR", "logs")


def start_health_server(host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # pragma: no cover - trivial
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            pass  # pragma: no cover

    server = HTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


if os.getenv("ASR_SKIP_MODEL_LOAD") == "1":
    _dummy = type("M", (), {"transcribe": lambda self, audio, **k: ([], None)})()
    asr = ASRServer(model=_dummy)
else:
    asr = ASRServer()


async def handler(ws):
    req_id = uuid.uuid4().hex[:8]
    log.info("client connected", req_id)
    await ws.send(json.dumps({"type": "info", "message": "asr-ready"}))
    try:
        async for msg in ws:
            if isinstance(msg, bytes):
                asr.append_pcm16(msg)
                now = time.time()
                if now - asr.last_emit > 0.25:
                    window = asr.pop_window(seconds=2.0, keep=1.25)
                    if window is not None:
                        text = asr.transcribe_window(window)
                        if text and text != asr.last_partial:
                            await ws.send(
                                json.dumps({"type": "partial", "text": text})
                            )
                            asr.last_partial = text
                            asr.last_partial_time = now
                        elif (
                            text == asr.last_partial
                            and now - asr.last_partial_time > 1.0
                        ):
                            await ws.send(
                                json.dumps({"type": "final", "text": text})
                            )
                            asr.last_partial = ""
                        asr.last_emit = now
            else:
                try:
                    obj = json.loads(msg)
                    if obj.get("type") == "control" and "setLanguage" in obj:
                        asr.set_language(obj["setLanguage"])
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "info",
                                    "message": f"lang-set:{asr.lang or 'auto'}",  # noqa: E501
                                }
                            )
                        )
                    elif obj.get("type") == "client-error":
                        log.warn(f"client-error: {obj.get('message', '')}", req_id)  # noqa: E501
                except Exception as e:
                    log.error(f"bad msg: {e}", req_id)
                    await ws.send(json.dumps({"type": "error", "message": str(e)}))  # noqa: E501
    except Exception as e:  # pragma: no cover - network errors
        log.error(f"ws:{e}", req_id)
        try:
            await ws.send(json.dumps({"type": "error", "message": f"ws:{e}"}))
        except Exception:
            pass


async def main() -> None:
    check_environment(HOST, PORT, LOG_DIR)
    if os.getenv("ENABLE_HEALTH_ENDPOINT") == "1":
        start_health_server(HOST, PORT + 1)
    async with serve(handler, HOST, PORT, max_size=2**23):
        log.info(f"server listening on ws://{HOST}:{PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
