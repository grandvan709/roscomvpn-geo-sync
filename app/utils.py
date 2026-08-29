import hashlib
import logging
import os
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


def setup_logging(log_file: Path | None = None):
    handlers = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n: int) -> str:
    s = float(n)
    for u in ("B", "KiB", "MiB", "GiB"):
        if s < 1024 or u == "GiB":
            return f"{int(s)}B" if u == "B" else f"{s:.1f}{u}"
        s /= 1024
    return f"{s:.1f}GiB"


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _log_retry(state) -> None:
    exc = state.outcome.exception() if state.outcome else None
    logging.warning(
        f"сетевой сбой, повтор {state.attempt_number} через "
        f"{state.next_action.sleep:.0f}с: {type(exc).__name__}: {exc}"
    )


def http_retry(attempts: int = 3):
    """Повтор сетевых сбоев httpx: обрыв соединения, таймаут, зависший TLS-хендшейк.

    Ретраится только `httpx.TransportError` — то есть транспорт. HTTP-статусы сюда
    не попадают: `raise_for_status()` поднимает `HTTPStatusError`, который к
    TransportError не относится, и повторять 404 смысла нет.

    Зачем: аплинк manager'а изредка роняет исходящий TLS на хендшейке (~1% прогонов,
    наблюдается с июля). Без повтора один такой чих валит весь прогон в FAILED.
    """
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
        before_sleep=_log_retry,
    )
