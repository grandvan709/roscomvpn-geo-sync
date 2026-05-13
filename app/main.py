import logging
import sys
from pathlib import Path

import config
from utils import setup_logging, human_size
from geo import GeoFetcher
from rsync_uploader import RsyncUploader
from notifier import TelegramNotifier
from remnawave import RemnawaveClient
from routing import RoutingUpdater


class SyncManager:
    def __init__(self):
        config.validate_config()
        self.files_dir = Path(config.FILES_DIR)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.geo = GeoFetcher(self.files_dir)
        self.rsync = RsyncUploader(
            config.RSYNC_HOST, config.RSYNC_USER, config.RSYNC_PORT,
            config.RSYNC_REMOTE_DEST, config.SSH_KEY_PATH,
        ) if config.RSYNC_ENABLED else None
        self.tg = TelegramNotifier(
            config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, config.TELEGRAM_THREAD_ID,
        ) if config.TELEGRAM_ENABLED else None

    def run(self) -> int:
        logging.info("=== geo-sync run start ===")
        status_lines: list[str] = []
        critical: list[str] = []
        warnings: list[str] = []

        geoip_res = self.geo.process_file(config.GEOIP_REPO, "geoip.dat", config.GEOIP_MIN_SIZE)
        geosite_res = self.geo.process_file(config.GEOSITE_REPO, "geosite.dat", config.GEOSITE_MIN_SIZE)
        for r in (geoip_res, geosite_res):
            if r.status == "failed":
                critical.append(f"[{r.filename}] {r.error}")
                status_lines.append(f"<code>{r.filename}</code>: ❌ failed ({r.error[:120]})")
            else:
                icon = "⬆" if r.status == "updated" else "✓"
                if r.used_fallback:
                    warnings.append(f"[{r.filename}] jsDelivr fallback")
                status_lines.append(f"<code>{r.filename}</code>: {icon} {r.status} [{r.source}, {human_size(r.size)}]")

        updated_files = [self.files_dir / r.filename for r in (geoip_res, geosite_res) if r.status == "updated"]
        if self.rsync:
            if updated_files:
                rsync_res = self.rsync.upload(updated_files)
                if rsync_res.success:
                    status_lines.append("rsync to remote: ✓ OK")
                else:
                    status_lines.append("rsync to remote: ✗ FAILED")
                    critical.append(f"rsync failed: {rsync_res.stderr[:200]}")
            else:
                status_lines.append("rsync to remote: ⊝ skipped (no updates)")
        else:
            status_lines.append("rsync: ⊝ disabled in config")

        remnawave = None
        if config.REMNAWAVE_ENABLED:
            remnawave = RemnawaveClient(
                config.REMNAWAVE_API_URL,
                config.REMNAWAVE_API_TOKEN,
                config.REMNAWAVE_CADDY_TOKEN,
            )
        try:
            routing = RoutingUpdater(
                self.files_dir,
                config.ROUTING_REPO,
                config.ROUTING_BRANCH,
                config.ROUTING_CLIENTS,
                config.GEO_PUBLIC_URL,
                remnawave,
                config.INCY_RULE_NAME,
            )
            routing_result = routing.process()
        finally:
            if remnawave:
                remnawave.close()

        for c in routing_result.clients:
            if c.status == "failed":
                status_lines.append(f"<code>routing-{c.client_type}</code>: ❌ {c.error[:120]}")
                critical.append(f"[routing-{c.client_type}] {c.error}")
            else:
                icon = "⬆" if c.status == "updated" else "✓"
                status_lines.append(f"<code>routing-{c.client_type}</code>: {icon} {c.status}")

        if config.REMNAWAVE_ENABLED:
            if routing_result.panel_pushed:
                applied = " + ".join(routing_result.applied_to_panel)
                status_lines.append(f"Routing applied to Remnawave: {applied}")
            elif routing_result.panel_error:
                status_lines.append("Remnawave push: ✗ FAILED")
                critical.append(f"Remnawave: {routing_result.panel_error}")
        else:
            status_lines.append("Routing deeplinks regenerated (see container logs for values)")

        if critical:
            emoji, title = "❌", "FAILED"
        elif warnings:
            emoji, title = "⚠️", "used fallback"
        else:
            emoji, title = "✅", "OK"

        if critical:
            for e in critical:
                status_lines.append(f"<b>error:</b> {e[:300]}")

        if self.tg:
            self.tg.send(emoji, title, status_lines)

        logging.info(f"=== geo-sync run done: {title} ===")
        return 0 if not critical else 1


def main():
    setup_logging(Path(config.LOG_FILE) if Path(config.LOGS_DIR).exists() else None)
    try:
        sm = SyncManager()
        sys.exit(sm.run())
    except Exception as e:
        logging.exception(f"Fatal: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
