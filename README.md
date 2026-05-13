<h1 align=center>Авто-зеркало <code>geoip.dat</code> / <code>geosite.dat</code> + авто-обновление routing-deeplinks в <code>Remnawave</code></h1>

> **Собственное зеркало** geo-файлов от [hydraponique/roscomvpn-*](https://github.com/hydraponique) для VPN-инфры на Xray-ядре (INCY, Happ) и **автоматическое обновление** routing-deeplinks в Remnawave-панели через API

<p align=center>Данный репозиторий был создан и поддерживается в связи с тем, что <b>Роскомнадзор</b> начал блокировать GitHub и его CDN. VPN-клиенты на Xray-ядре (INCY, Happ) используют geo-файлы для split-tunneling — без них маршрутизация ломается. Этот сервис позволяет раздавать geo-файлы с собственного домена и автоматически обновлять routing-deeplinks в Remnawave-панели.</p>

---

## 🚀 Возможности

- ✅ Скачивание `geoip.dat` и `geosite.dat` с GitHub Releases и проверкой sha256
- ✅ Fallback на jsDelivr с проверкой размера и magic byte при недоступности GitHub
- ✅ Атомарная замена локального кэша (старая версия не теряется при сбое)
- ✅ Загрузка свежих файлов на удалённый сервер раздачи через rsync (опционально)
- ✅ Health-check публичного URL раздачи после rsync (опционально)
- ✅ Автоматическая генерация routing-deeplinks для INCY и Happ из upstream `JSONSUB.JSON`
- ✅ Автоматический PATCH `/api/subscription-settings` в Remnawave: правило INCY Routing + поле Happ Routing (опционально)
- ✅ Вывод готовых deeplinks в логи — для ручной вставки в панель если автоматизация отключена
- ✅ Telegram-уведомления о результатах каждого запуска (✅ OK / ⚠️ used fallback / ❌ FAILED)
- ✅ Регулярное выполнение по cron-расписанию (настраивается через `.env`)
- ✅ Валидация конфигурации при старте
- ✅ Автоматические повторы при сбоях сети (tenacity)
- ✅ Подробное логирование

## 📋 Требования

- Docker
- (опционально) Удалённый сервер с настроенным rsync для раздачи geo-файлов с собственного домена
- (опционально) Remnawave-панель + API-токен для автоматического PATCH deeplinks
- (опционально) Telegram-бот для уведомлений

---

## 🔧 Установка

### 1. Устанавливаем Docker
```bash
sudo curl -fsSL https://get.docker.com | sh
```

### 2. Создаем папку `/opt/geo-mirror` и переходим в нее
```bash
sudo mkdir -p /opt/geo-mirror && cd /opt/geo-mirror
```

### 3. Скачиваем файлы `.env.example` (его сразу ренеймим в `.env`) и `docker-compose.yml`
```bash
sudo wget -O .env https://raw.githubusercontent.com/grandvan709/roscomvpn-geo-sync/refs/heads/master/.env.example && \
sudo wget -O docker-compose.yml https://raw.githubusercontent.com/grandvan709/roscomvpn-geo-sync/refs/heads/master/docker-compose.yml
```

### 4. Заполняем файл `.env` необходимыми значениями (см раздел "Конфигурация")
```bash
sudo nano .env
```

### 5. (опционально, если используется rsync) Кладём приватный SSH-ключ
```bash
sudo cp /path/to/private-key /opt/geo-mirror/ssh-key
sudo chmod 600 /opt/geo-mirror/ssh-key
```

> Если rsync не используется — закомментируйте строку `./ssh-key:/app/ssh-key:ro` в `docker-compose.yml`, иначе Docker создаст пустую директорию вместо файла и контейнер упадёт.

## ⚙️ Конфигурация

### Обязательные переменные

<table>
  <tr>
    <th>Переменная</th>
    <th>По умолчанию</th>
    <th>Описание</th>
  </tr>
  <tr>
    <td><code>GEOIP_REPO</code></td>
    <td><code>hydraponique/roscomvpn-geoip</code></td>
    <td>GitHub-репозиторий с релизами <code>geoip.dat</code></td>
  </tr>
  <tr>
    <td><code>GEOSITE_REPO</code></td>
    <td><code>hydraponique/roscomvpn-geosite</code></td>
    <td>GitHub-репозиторий с релизами <code>geosite.dat</code></td>
  </tr>
  <tr>
    <td><code>ROUTING_REPO</code></td>
    <td><code>hydraponique/roscomvpn-routing</code></td>
    <td>GitHub-репозиторий с <code>INCY/JSONSUB.JSON</code> и <code>HAPP/JSONSUB.JSON</code></td>
  </tr>
  <tr>
    <td><code>ROUTING_BRANCH</code></td>
    <td><code>main</code></td>
    <td>Ветка репозитория, откуда тянуть JSONSUB</td>
  </tr>
  <tr>
    <td><code>ROUTING_CLIENTS</code></td>
    <td><code>INCY,HAPP</code></td>
    <td>Клиенты, для которых строить deeplinks (через запятую). Поддерживается: <code>INCY</code>, <code>HAPP</code></td>
  </tr>
</table>

### Опциональные переменные

| Переменная | По умолчанию | Описание |
|-----------|:----------:|---------|
| `TZ` | `UTC` | Часовой пояс контейнера ([список](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)) |
| `CRON_SCHEDULE` | `0 */12 * * *` | Расписание cron (по умолчанию — каждые 12 часов) |
| `GEOIP_MIN_SIZE` | `10000` | Минимальный размер `geoip.dat` (байт). Защита от обрезанных загрузок при fallback на jsDelivr |
| `GEOSITE_MIN_SIZE` | `10000` | Минимальный размер `geosite.dat` (байт) |

### rsync на удалённый сервер (опционально)

Если эти переменные не заданы — geo-файлы сохраняются только в локальный кэш `./files/`, rsync пропускается.

| Переменная | По умолчанию | Описание |
|-----------|:----------:|---------|
| `RSYNC_HOST` | — | Хост удалённого сервера раздачи |
| `RSYNC_USER` | — | SSH-пользователь на удалённом сервере |
| `RSYNC_PORT` | `22` | SSH-порт |
| `RSYNC_REMOTE_DEST` | `./` | Целевая директория rsync. Для `rrsync`-restricted цели используйте `./` |
| `SSH_KEY_PATH` | `/app/ssh-key` | Путь к SSH-ключу внутри контейнера (не менять, маунт через docker-compose) |
| `GEO_PUBLIC_URL` | — | Публичный URL раздачи (например `https://geo.example.com`). Если задан — подставляется в JSONSUB и используется для health-check после rsync. Если НЕ задан — в JSONSUB остаются оригинальные URL'ы (`cdn.jsdelivr.net`) |

### Push deeplinks в Remnawave-панель (опционально)

Если `REMNAWAVE_API_URL` и `REMNAWAVE_API_TOKEN` не заданы оба — PATCH в панель пропускается, deeplinks выводятся только в логах (для ручного копирования в Response Rules / Happ Routing).

| Переменная | По умолчанию | Описание |
|-----------|:----------:|---------|
| `REMNAWAVE_API_URL` | — | URL Remnawave-панели (без `/api`) |
| `REMNAWAVE_API_TOKEN` | — | Bearer JWT API-токен (создаётся в Remnawave UI → Settings → API Keys) |
| `REMNAWAVE_CADDY_TOKEN` | — | Опционально: `X-Api-Key` заголовок (если ваша панель за Caddy auth-portal требует его для `/api/*`) |
| `INCY_RULE_NAME` | `INCY Routing` | Имя правила в Response Rules, содержащего header с key=`routing` для INCY-клиентов |

### Telegram-уведомления (опционально)

После каждого запуска бот отправляет итоговое сообщение со сводкой (✅ OK / ⚠️ used fallback / ❌ FAILED). Если переменные не заданы — Telegram-уведомления отключены, статус виден только в логах.

| Переменная | Описание |
|-----------|---------|
| `TELEGRAM_BOT_TOKEN` | Токен бота (получить у [@BotFather](https://t.me/BotFather)) |
| `TELEGRAM_CHAT_ID` | ID чата/группы (узнать через [@userinfobot](https://t.me/userinfobot) или [@getidsbot](https://t.me/getidsbot)) |
| `TELEGRAM_THREAD_ID` | ID топика в супергруппе (опционально) |

### Примеры CRON_SCHEDULE

```env
CRON_SCHEDULE='0 */12 * * *'     # каждые 12 часов (по умолчанию)
CRON_SCHEDULE='0 */6 * * *'      # каждые 6 часов
CRON_SCHEDULE='0 4 * * *'        # один раз в день в 04:00
CRON_SCHEDULE='*/30 * * * *'     # каждые 30 минут (для тестов)
CRON_SCHEDULE='0 0 * * 0'        # один раз в неделю в воскресенье
```

**Формат cron:** `минуты часы дни_месяца месяцы дни_недели`

---

## 🌐 Setup rsync на удалённый сервер раздачи

На сервере, который будет раздавать `geo.example.com/*.dat`:

### 1. Создать директорию для файлов
```bash
sudo mkdir -p /opt/geo-mirror/files
sudo chown -R yourSshUser:yourSshUser /opt/geo-mirror
```

### 2. Установить `rsync` и `rrsync` (restricted rsync wrapper)
```bash
sudo apt-get install rsync
```

### 3. Сгенерировать SSH-ключ на сервере, где будет запускаться контейнер
```bash
ssh-keygen -t ed25519 -N '' -f /opt/geo-mirror/ssh-key -C 'roscomvpn-geo-sync'
sudo chmod 600 /opt/geo-mirror/ssh-key
```

### 4. Добавить публичный ключ в `authorized_keys` на raздающем сервере (с `rrsync`-ограничением)
```bash
echo 'command="/usr/bin/rrsync -wo /opt/geo-mirror/files/",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty <содержимое /opt/geo-mirror/ssh-key.pub>' >> ~yourSshUser/.ssh/authorized_keys
```

> `rrsync -wo` — write-only режим, ключ может только заливать файлы в одну директорию, никаких shell-команд.

### 5. Настроить веб-сервер для раздачи. Пример Caddyfile
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

### 6. В `.env` контейнера прописать соответствующие значения
```env
RSYNC_HOST=geo.example.com
RSYNC_USER=yourSshUser
RSYNC_PORT=22
RSYNC_REMOTE_DEST=./
GEO_PUBLIC_URL=https://geo.example.com
```

---

## 🔗 Setup Remnawave-интеграции (Phase 2b)

### 1. В Remnawave-панели создать правило в Response Rules

В UI Remnawave → **Subscription → Settings → Response Rules** — добавить правило:
- **Name:** `INCY Routing` (или другое, тогда укажите в `INCY_RULE_NAME`)
- **Condition:** `user-agent CONTAINS incy` (case-insensitive)
- **Response type:** `XRAY_JSON`
- **Response modifications → headers:** добавить header с key `routing` и любым тестовым value (скрипт перепишет его при первом запуске)

### 2. Создать API-токен в Remnawave

В UI Remnawave → **Settings → API Keys** → создать новый ключ с ролью `ADMIN` или `API`. Скопировать Bearer JWT.

### 3. В `.env` контейнера прописать
```env
REMNAWAVE_API_URL=https://your-panel.example.com
REMNAWAVE_API_TOKEN=eyJ...
INCY_RULE_NAME=INCY Routing
```

> Поле **Happ Routing** в `Subscription → Settings → Announce & Routing` обновляется автоматически — отдельной настройки не требует.

---

## 🚀 Запуск

### Первый запуск
```bash
cd /opt/geo-mirror && sudo docker compose up -d
```

### Проверка логов
```bash
cd /opt/geo-mirror && sudo docker compose logs -f -t
```

### Остановка
```bash
cd /opt/geo-mirror && sudo docker compose down
```

### Перезагрузка
```bash
cd /opt/geo-mirror && sudo docker compose down && sudo docker compose up -d
```

---

## 📊 Структура логов

```
2026-05-13 04:39:32,904 [INFO] === geo-sync run start ===
2026-05-13 04:39:33,565 [INFO] HTTP Request: GET https://api.github.com/repos/hydraponique/roscomvpn-geoip/releases/latest "HTTP/1.1 200 OK"
2026-05-13 04:39:34,422 [INFO] HTTP Request: GET .../releases/download/202605120620/geoip.dat "HTTP/1.1 302 Found"
2026-05-13 04:39:39,679 [INFO] HTTP Request: GET https://raw.githubusercontent.com/hydraponique/roscomvpn-routing/main/INCY/JSONSUB.JSON "HTTP/1.1 200 OK"
2026-05-13 04:39:39,681 [INFO] INCY Routing: ://routing/onadd/eyJOYW1lIjoiUm9zY29tVlBOIEpTT04i...
2026-05-13 04:39:40,129 [INFO] HTTP Request: GET https://raw.githubusercontent.com/hydraponique/roscomvpn-routing/main/HAPP/JSONSUB.JSON "HTTP/1.1 200 OK"
2026-05-13 04:39:40,129 [INFO] Happ Routing: happ://routing/onadd/eyJOYW1lIjoiUm9zY29tVlBOIEpTT04i...
2026-05-13 04:39:40,129 [INFO] === geo-sync run done: OK ===

Schedule: 0 */12 * * *
Switching to periodic mode...
==========================================
```

### Пример Telegram-сообщения

```
✅ roscomvpn-geo-sync — OK
geoip.dat: ⬆ updated [github:202605120620, 407.0KiB]
geosite.dat: ✓ no changes [github:202604152235, 66.3KiB]
rsync to remote: ✓ OK
routing-INCY: ⬆ updated
routing-HAPP: ⬆ updated
Routing applied to Remnawave: INCY + HAPP
```

> Сам deeplink (длинная base64-строка) в Telegram **не вставляется** — он только в логах контейнера. Это снижает шум в чате.

---

## 💡 Обновление ПО

### 1. Переходим в нашу папку
```bash
cd /opt/geo-mirror
```

### 2. Останавливаем контейнер
```bash
sudo docker compose down
```

### 3. Скачиваем новый образ
```bash
sudo docker compose pull
```

### 4. Запускаем контейнер и смотрим логи после запуска новой версии
```bash
sudo docker compose up -d && sudo docker compose logs -f -t
```

### 5. Проверка docker-compose.yml и прочих файлов
Перед обновлениями и запусками — убедитесь, что ваши файлы **docker-compose.yml** и **.env** *(и прочие, которые могут быть в будущем)* соответствуют последним версиям из репозитория!

> Чтобы не писать `sudo` перед каждой командой `docker` — нужно внести пользователя, из под которого вы работаете, в группу **docker** следующей командой: `sudo usermod -aG docker <username>`. А затем перезайти на сервер.
---

> **Ставь ⭐** и не пропусти регулярные обновления для поддержания актуальности скрипта и оптимальной автоматизации

> USDT TRC20: TL6gHETnKqNWV4D6GjiKKahkBsAwcyWfo8

<p align=center>
    <a href="https://t.me/grand_van" target="_blank" rel="noopener noreferrer">
        <img src="https://img.shields.io/badge/Telegram-GrandVan-purple?logo=telegram&logoColor=white&labelColor=blue" alt="Chat me on Telegram">
    </a>
</p>
