#!/bin/bash
set -e

echo "=========================================="
echo "roscomvpn-geo-sync"
echo "=========================================="

if [[ -f /app/ssh-key ]]; then
    cp /app/ssh-key /tmp/ssh-key
    chmod 600 /tmp/ssh-key
    export SSH_KEY_RUNTIME=/tmp/ssh-key
fi

STARTUP_NOTIFY=1 python /app/main.py

CRON_SCHEDULE=$(python -c "import config; print(config.CRON_SCHEDULE)")
TZ=$(python -c "import config; print(config.TZ or '')")

echo ""
echo "Schedule: $CRON_SCHEDULE"
echo "Switching to periodic mode..."
echo "=========================================="

printf "TZ=%s\nSSH_KEY_RUNTIME=/tmp/ssh-key\n%s cd /app && STARTUP_NOTIFY=0 /usr/local/bin/python /app/main.py >> /app/logs/sync.log 2>&1\n" "$TZ" "$CRON_SCHEDULE" > /etc/cron.d/sync-cron
chmod 0644 /etc/cron.d/sync-cron
crontab /etc/cron.d/sync-cron

exec cron -f
