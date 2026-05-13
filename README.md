# roscomvpn-geo-sync

[![Docker Hub](https://img.shields.io/docker/v/grandvan/roscomvpn-geo-sync?label=docker%20hub&sort=semver)](https://hub.docker.com/r/grandvan/roscomvpn-geo-sync)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Собственное зеркало `geoip.dat` / `geosite.dat` от [hydraponique/roscomvpn-*](https://github.com/hydraponique) + автоматическая генерация и обновление routing-deeplinks для клиентов **INCY** и **Happ** в Remnawave-панели.

## Зачем

В 2026 году Роскомнадзор начал блокировать GitHub и его CDN. VPN-клиенты на Xray-ядре (INCY, Happ) используют geo-файлы для split-tunneling: какие домены гнать через VPN, какие напрямую. Если geo-файлы стали недоступны — маршрутизация ломается.

Этот сервис каждые 12 часов:
1. Скачивает свежие geo-файлы (с GitHub Releases по sha256, с fallback на jsDelivr).
2. Опционально — пушит их на ваш сервер через rsync, чтобы вы могли раздавать с собственного домена из российского IP-пространства.
3. Опционально — собирает routing-deeplinks (INCY + Happ) из upstream `JSONSUB.JSON` с подменой URL'ов на ваш домен и автоматически применяет их через Remnawave API.

Если не настраивать rsync и Remnawave API — deeplinks просто выводятся в лог, оттуда их можно скопировать в панель вручную.

## Что делает

| Фаза | Действие | Опциональность |
|---|---|---|
| 1a | Скачивает `geoip.dat` + `geosite.dat` с проверкой sha256 (GitHub Releases). Fallback — jsDelivr с проверкой размера + magic byte. | обязательно |
| 1b | Заливает свежие файлы на удалённый сервер через rsync + health-check публичного URL. | если задан `RSYNC_HOST` |
| 2a | Скачивает `INCY/JSONSUB.JSON` и `HAPP/JSONSUB.JSON` из `hydraponique/roscomvpn-routing`. Заменяет URL geo-файлов на ваш домен. Кодирует base64. Выводит deeplinks в лог. | обязательно |
| 2b | PATCH `/api/subscription-settings` в Remnawave: обновляет правило INCY Routing в Response Rules + поле Happ Routing. | если задан `REMNAWAVE_API_URL` + `REMNAWAVE_API_TOKEN` |
| Alert | Telegram-сообщение со сводкой каждый запуск (✅ OK / ⚠️ used fallback / ❌ FAILED). | если задан `TELEGRAM_BOT_TOKEN` |

## Quick start

```bash
# 1. Клонировать репо в любое место на сервере
git clone https://github.com/grandvan709/roscomvpn-geo-sync.git /opt/geo-mirror
cd /opt/geo-mirror

# 2. Скопировать шаблон конфига
cp .env.example .env
nano .env

# 3. (если нужен rsync) Положить SSH-ключ к удалённому серверу
cp /path/to/private-key ./ssh-key
chmod 600 ./ssh-key

# 4. Запустить
docker compose up -d
docker logs roscomvpn-geo-sync --tail 50
```

## Конфигурация

Все настройки — в `.env`. См. подробные комментарии в [.env.example](.env.example).

**Минимальный конфиг** (без rsync, без Remnawave, без Telegram):
```ini
CRON_SCHEDULE=0 */12 * * *
TZ=UTC
GEOIP_REPO=hydraponique/roscomvpn-geoip
GEOSITE_REPO=hydraponique/roscomvpn-geosite
ROUTING_REPO=hydraponique/roscomvpn-routing
ROUTING_BRANCH=main
ROUTING_CLIENTS=INCY,HAPP
```
В этом режиме скрипт качает geo-файлы в `./files/`, выводит deeplinks в логи (с оригинальными jsDelivr-URL'ами).

## Setup rsync на удалённый сервер

На удалённом сервере (тот, что будет раздавать `geo.example.com/*.dat`):

```bash
# 1. Создать директорию
mkdir -p /opt/geo-mirror/files
chown -R yourSshUser:yourSshUser /opt/geo-mirror

# 2. Установить rsync и rrsync (restricted rsync wrapper)
apt-get install rsync

# 3. Добавить публичный ключ в authorized_keys с rrsync-ограничением
echo 'command="/usr/bin/rrsync -wo /opt/geo-mirror/files/",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... geo-sync@manager' >> ~yourSshUser/.ssh/authorized_keys
```

Локально (на машине с контейнером):
```bash
# Сгенерировать ключ
ssh-keygen -t ed25519 -N '' -f ./ssh-key -C 'roscomvpn-geo-sync'
# Публичную часть (./ssh-key.pub) добавьте в authorized_keys выше

# В .env:
RSYNC_HOST=geo.example.com
RSYNC_USER=yourSshUser
RSYNC_PORT=22
RSYNC_REMOTE_DEST=./
GEO_PUBLIC_URL=https://geo.example.com
```

Затем на удалённом сервере настройте веб-сервер (Caddy / Nginx) для раздачи `/opt/geo-mirror/files/`. Пример Caddyfile:
```caddy
geo.example.com {
    root * /opt/geo-mirror/files
    file_server
    @geodat path *.dat
    header @geodat {
        Cache-Control "public, max-age=3600"
        Content-Type "application/octet-stream"
    }
}
```

## Setup Remnawave integration

1. В Remnawave UI → Subscription → Settings → Response Rules — создайте правило:
   - Name: `INCY Routing` (или другое, тогда укажите в `INCY_RULE_NAME`)
   - Condition: `user-agent CONTAINS incy` (case-insensitive)
   - Response type: `XRAY_JSON`
   - Response modifications → headers: добавьте header с key `routing` и любым тестовым value (скрипт перепишет его).
2. Создайте API token: Caddy auth-portal → API Keys → новый ключ с ролью `ADMIN` или `API`.
3. В `.env`:
   ```ini
   REMNAWAVE_API_URL=https://your-panel.example.com
   REMNAWAVE_API_TOKEN=<JWT bearer>
   INCY_RULE_NAME=INCY Routing
   ```

## Telegram alerts

1. Создайте бота через [@BotFather](https://t.me/BotFather).
2. Добавьте бота в группу/канал с правами «Send messages».
3. В `.env`:
   ```ini
   TELEGRAM_BOT_TOKEN=1234:AAA...
   TELEGRAM_CHAT_ID=-1001234567890
   TELEGRAM_THREAD_ID=42
   ```

Формат сообщения:
```
✅ roscomvpn-geo-sync — OK
geoip.dat: ⬆ updated [github:202605120620, 407.0KiB]
geosite.dat: ✓ no changes [github:202604152235, 66.3KiB]
rsync to remote: ✓ OK
routing-INCY: ⬆ updated
routing-HAPP: ⬆ updated
Routing applied to Remnawave: INCY + HAPP
```

## Архитектура

```
┌──────────────────────────────────────┐
│ Container: roscomvpn-geo-sync         │
│ cron: CRON_SCHEDULE                   │
│                                       │
│ Phase 1a: download geo (GitHub+jsD)   │
│ Phase 1b: rsync (optional)            │
│ Phase 2a: build deeplinks → logs      │
│ Phase 2b: PATCH Remnawave (optional)  │
│ Telegram summary (optional)           │
└──────────────────────────────────────┘
       │           │           │
   geo source  remote     Remnawave API
   (github)    (rsync)    (panel)
```

## License

Apache License 2.0
