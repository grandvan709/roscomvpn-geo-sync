import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TZ = os.getenv("TZ", "UTC")
if TZ:
    os.environ["TZ"] = TZ
    try:
        time.tzset()
    except AttributeError:
        pass

CRON_SCHEDULE = os.getenv("CRON_SCHEDULE", "0 */12 * * *")

GEO_REPO = os.getenv("GEO_REPO", "Loyalsoldier/v2ray-rules-dat")
GEOIP_REPO = os.getenv("GEOIP_REPO") or GEO_REPO
GEOSITE_REPO = os.getenv("GEOSITE_REPO") or GEO_REPO
GEOIP_MIN_SIZE = int(os.getenv("GEOIP_MIN_SIZE", "100000"))
GEOSITE_MIN_SIZE = int(os.getenv("GEOSITE_MIN_SIZE", "100000"))

ROUTING_CONFIG_PATH = os.getenv("ROUTING_CONFIG_PATH", "/app/configs/GRANDNET.JSON")
ROUTING_CLIENTS = [c.strip().upper() for c in os.getenv("ROUTING_CLIENTS", "INCY,HAPP").split(",") if c.strip()]

RSYNC_HOST = os.getenv("RSYNC_HOST") or None
RSYNC_USER = os.getenv("RSYNC_USER") or None
RSYNC_PORT = int(os.getenv("RSYNC_PORT", "22"))
RSYNC_REMOTE_DEST = os.getenv("RSYNC_REMOTE_DEST", "./")
SSH_KEY_PATH = os.getenv("SSH_KEY_RUNTIME") or os.getenv("SSH_KEY_PATH", "/app/ssh-key")

GEO_PUBLIC_URL = os.getenv("GEO_PUBLIC_URL") or None

REMNAWAVE_API_URL = os.getenv("REMNAWAVE_API_URL") or None
REMNAWAVE_API_TOKEN = os.getenv("REMNAWAVE_API_TOKEN") or None
REMNAWAVE_CADDY_TOKEN = os.getenv("REMNAWAVE_CADDY_TOKEN") or None
INCY_RULE_NAME = os.getenv("INCY_RULE_NAME", "INCY Routing")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or None
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or None
TELEGRAM_THREAD_ID = os.getenv("TELEGRAM_THREAD_ID") or None

FILES_DIR = "/app/files"
LOGS_DIR = "/app/logs"
LOG_FILE = "/app/logs/sync.log"

RSYNC_ENABLED = bool(RSYNC_HOST and RSYNC_USER)
REMNAWAVE_ENABLED = bool(REMNAWAVE_API_URL and REMNAWAVE_API_TOKEN)
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def validate_config():
    if not CRON_SCHEDULE:
        raise ValueError("CRON_SCHEDULE is required")
    if not GEOIP_REPO or not GEOSITE_REPO:
        raise ValueError("GEO_REPO (or GEOIP_REPO/GEOSITE_REPO) is required")
    if not ROUTING_CONFIG_PATH:
        raise ValueError("ROUTING_CONFIG_PATH is required")
    if not Path(ROUTING_CONFIG_PATH).is_file():
        raise ValueError(f"ROUTING_CONFIG_PATH not found: {ROUTING_CONFIG_PATH}")
    if not ROUTING_CLIENTS:
        raise ValueError("ROUTING_CLIENTS must contain at least one client")
    for c in ROUTING_CLIENTS:
        if c not in ("INCY", "HAPP"):
            raise ValueError(f"Unknown client in ROUTING_CLIENTS: {c}")

    rsync_partial = [bool(RSYNC_HOST), bool(RSYNC_USER)]
    if any(rsync_partial) and not all(rsync_partial):
        raise ValueError("RSYNC_HOST and RSYNC_USER must be both set or both empty")

    remnawave_partial = [bool(REMNAWAVE_API_URL), bool(REMNAWAVE_API_TOKEN)]
    if any(remnawave_partial) and not all(remnawave_partial):
        raise ValueError("REMNAWAVE_API_URL and REMNAWAVE_API_TOKEN must be both set or both empty")

    if TELEGRAM_BOT_TOKEN and not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN set but TELEGRAM_CHAT_ID missing")
    if TELEGRAM_CHAT_ID and not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_CHAT_ID set but TELEGRAM_BOT_TOKEN missing")
