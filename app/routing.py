import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from utils import atomic_write, sha256_bytes, sha256_file
from remnawave import RemnawaveClient


CLIENT_PREFIXES = {
    "INCY": "://routing/onadd/",
    "HAPP": "happ://routing/onadd/",
}

CLIENT_LABELS = {
    "INCY": "INCY Routing",
    "HAPP": "Happ Routing",
}


@dataclass
class RoutingClientResult:
    client_type: str
    status: str
    deeplink: str = ""
    error: str = ""


@dataclass
class RoutingResult:
    clients: list = field(default_factory=list)
    panel_pushed: bool = False
    panel_error: str = ""
    applied_to_panel: list = field(default_factory=list)


class RoutingUpdater:
    def __init__(
        self,
        files_dir: Path,
        routing_repo: str,
        routing_branch: str,
        clients: list[str],
        geo_public_url: str | None,
        remnawave: RemnawaveClient | None,
        incy_rule_name: str,
    ):
        self.files_dir = files_dir
        self.repo = routing_repo
        self.branch = routing_branch
        self.clients = clients
        self.geo_public_url = geo_public_url
        self.remnawave = remnawave
        self.incy_rule_name = incy_rule_name

    def _fetch_jsonsub(self, client_type: str) -> dict:
        url = f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{client_type}/JSONSUB.JSON"
        r = httpx.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
        return r.json()

    def _replace_urls(self, data: dict) -> dict:
        if self.geo_public_url:
            base = self.geo_public_url.rstrip("/")
            data["Geoipurl"] = f"{base}/geoip.dat"
            data["Geositeurl"] = f"{base}/geosite.dat"
        return data

    def _serialize(self, data: dict) -> bytes:
        return (json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")

    def _build_deeplink(self, client_type: str, serialized: bytes) -> str:
        b64 = base64.b64encode(serialized).decode("ascii")
        return CLIENT_PREFIXES[client_type] + b64

    def process(self) -> RoutingResult:
        result = RoutingResult()
        prepared: dict[str, tuple[str, bytes, Path]] = {}

        for client_type in self.clients:
            try:
                data = self._fetch_jsonsub(client_type)
            except Exception as e:
                result.clients.append(RoutingClientResult(client_type, "failed", error=str(e)))
                continue

            data = self._replace_urls(data)
            serialized = self._serialize(data)
            cache_path = self.files_dir / f"routing-{client_type}.json"
            new_hash = sha256_bytes(serialized)
            status = "updated"
            if cache_path.exists() and sha256_file(cache_path) == new_hash:
                status = "unchanged"

            deeplink = self._build_deeplink(client_type, serialized)
            logging.info(f"{CLIENT_LABELS[client_type]}: {deeplink}")

            prepared[client_type] = (deeplink, serialized, cache_path)
            result.clients.append(RoutingClientResult(client_type, status, deeplink=deeplink))

        if self.remnawave and prepared:
            try:
                self._push_to_panel(prepared)
                result.panel_pushed = True
                result.applied_to_panel = list(prepared.keys())
                for _, serialized, cache_path in prepared.values():
                    atomic_write(cache_path, serialized)
            except Exception as e:
                result.panel_error = str(e)
                logging.error(f"panel push failed: {e}")
        elif not self.remnawave:
            for _, serialized, cache_path in prepared.values():
                atomic_write(cache_path, serialized)

        return result

    def _push_to_panel(self, prepared: dict[str, tuple[str, bytes, Path]]):
        settings = self.remnawave.get_subscription_settings()
        uuid = settings.get("uuid")
        if not uuid:
            raise ValueError("subscription-settings has no uuid")
        response_rules = settings.get("responseRules") or {"version": "1", "rules": []}

        payload = {"uuid": uuid}

        if "INCY" in prepared:
            incy_deeplink = prepared["INCY"][0]
            rules = response_rules.get("rules", [])
            matches = [r for r in rules if r.get("name") == self.incy_rule_name]
            if len(matches) == 0:
                raise ValueError(f"rule '{self.incy_rule_name}' not found in panel responseRules")
            if len(matches) > 1:
                raise ValueError(f"multiple rules named '{self.incy_rule_name}' found")
            rule = matches[0]
            mods = rule.setdefault("responseModifications", {})
            headers = mods.setdefault("headers", [])
            replaced = False
            for h in headers:
                if h.get("key") == "routing":
                    h["value"] = incy_deeplink
                    replaced = True
                    break
            if not replaced:
                headers.append({"key": "routing", "value": incy_deeplink})
            payload["responseRules"] = response_rules

        if "HAPP" in prepared:
            payload["happRouting"] = prepared["HAPP"][0]

        self.remnawave.patch_subscription_settings(payload)
