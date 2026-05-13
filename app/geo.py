import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from utils import atomic_write, sha256_bytes, sha256_file


@dataclass
class FileResult:
    filename: str
    status: str
    source: str
    size: int
    used_fallback: bool = False
    error: str = ""


class GeoFetcher:
    def __init__(self, files_dir: Path):
        self.files_dir = files_dir
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _http_get(self, url: str, timeout: int = 120) -> bytes:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.content

    def _fetch_github_release(self, repo: str, filename: str) -> tuple[bytes, str]:
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        meta = httpx.get(api_url, timeout=30).json()
        tag = meta.get("tag_name") or ""
        if not tag:
            raise ValueError("no tag_name in release")
        assets = meta.get("assets") or []
        dat_url = next((a["browser_download_url"] for a in assets if a.get("name") == filename), None)
        sha_url = next((a["browser_download_url"] for a in assets if a.get("name") == filename + ".sha256"), None)
        if not dat_url or not sha_url:
            raise ValueError(f"missing .dat or .sha256 asset for {filename} in release {tag}")

        dat = self._http_get(dat_url, timeout=120)
        sha_blob = self._http_get(sha_url, timeout=30).decode("ascii", errors="replace")
        expected = (sha_blob.split() or [""])[0].strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f".sha256 invalid content: {expected!r}")
        actual = sha256_bytes(dat)
        if actual != expected:
            raise ValueError(f"sha256 mismatch (expected {expected}, got {actual})")
        return dat, f"github:{tag}"

    def _fetch_jsdelivr(self, repo: str, filename: str, min_size: int) -> tuple[bytes, str]:
        url = f"https://cdn.jsdelivr.net/gh/{repo}/release/{filename}"
        dat = self._http_get(url, timeout=120)
        if len(dat) < min_size:
            raise ValueError(f"file too small: {len(dat)} (min {min_size})")
        if not dat or dat[0] != 0x0a:
            raise ValueError(f"unexpected magic byte: {dat[:1].hex()}")
        return dat, "jsdelivr"

    def process_file(self, repo: str, filename: str, min_size: int) -> FileResult:
        local = self.files_dir / filename
        used_fallback = False
        source = ""

        try:
            dat, source = self._fetch_github_release(repo, filename)
        except Exception as e:
            logging.warning(f"[{filename}] GitHub Releases failed: {e}; trying jsDelivr")
            try:
                dat, source = self._fetch_jsdelivr(repo, filename, min_size)
                source = f"{source} (fallback)"
                used_fallback = True
            except Exception as e2:
                return FileResult(filename, "failed", "-", 0, False, str(e2))

        size = len(dat)
        if local.exists() and sha256_file(local) == sha256_bytes(dat):
            return FileResult(filename, "unchanged", source, size, used_fallback)

        atomic_write(local, dat)
        return FileResult(filename, "updated", source, size, used_fallback)
