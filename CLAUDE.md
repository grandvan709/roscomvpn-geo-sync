# CLAUDE.md

## Язык общения

Всегда общаться с пользователем на русском языке.

## Стиль кода

Никогда не добавлять комментарии в код (ни строчные `#`, ни docstring). Если информация важна для контекста — записывать её в этот CLAUDE.md, а не в исходный код.

## Описание проекта

roscomvpn-geo-sync — open-source инструмент для собственного зеркалирования geo-файлов (`geoip.dat`, `geosite.dat`) из репозиториев `hydraponique/roscomvpn-*` и автоматического обновления routing-deeplinks для клиентов INCY и Happ в Remnawave-панели.

Запускается в Docker-контейнере. Cron внутри контейнера запускает `/app/main.py` по расписанию из `.env` (`CRON_SCHEDULE`).

## Структура файлов

- `app/` — Python-модули (копируются в `/app/` внутри контейнера через `COPY app/ .`)
  - `main.py` — `SyncManager`: orchestrator. Запускает Phase 1a → 1b → 2a → 2b, формирует Telegram-сводку.
  - `config.py` — загрузка `.env` через `python-dotenv`, валидация (`validate_config`), флаги `RSYNC_ENABLED`, `REMNAWAVE_ENABLED`, `TELEGRAM_ENABLED` вычисляются по наличию полей.
  - `geo.py` — `GeoFetcher`: Phase 1a. Качает с GitHub Releases (sha256 verify), fallback на jsDelivr (size + magic byte 0x0a). Атомарная запись в `/app/files/`.
  - `rsync_uploader.py` — `RsyncUploader`: Phase 1b. `subprocess.run(["rsync", ...])` через SSH с заданным ключом.
  - `routing.py` — `RoutingUpdater`: Phase 2a (build deeplinks, всегда) + Phase 2b (push в Remnawave, опционально). Префиксы deeplink: `://routing/onadd/` для INCY, `happ://routing/onadd/` для HAPP.
  - `remnawave.py` — `RemnawaveClient`: тонкий httpx-клиент. GET/PATCH `/api/subscription-settings`. Retry через tenacity (3 попытки) на сетевых ошибках.
  - `notifier.py` — `TelegramNotifier`: один метод `send(emoji, title, body_lines)`.
  - `utils.py` — `setup_logging`, `sha256_bytes`, `sha256_file`, `human_size`, `atomic_write`.
- `entrypoint.sh` — точка входа: копирует SSH-ключ в `/tmp/ssh-key` с `chmod 600` (mounted-файл может не иметь правильных прав), запускает первый прогон `STARTUP_NOTIFY=1 python main.py`, потом настраивает crontab.
- `Dockerfile` — `python:3.13-slim` + `cron rsync openssh-client ca-certificates`.
- `docker-compose.yml` — image `grandvan/roscomvpn-geo-sync:latest`, маунты `.env` / `./files` / `./logs` / `./ssh-key`.
- `.env.example` — шаблон со всеми переменными и подробными комментариями.
- `requirements.txt` — `httpx`, `python-dotenv`, `tenacity`.

## Ключевые механизмы

### Phase 1a — geo-файлы

- Primary: GET `https://api.github.com/repos/<REPO>/releases/latest` → находим asset `geoip.dat` и `geoip.dat.sha256` → качаем оба → проверяем sha256.
- Fallback: `https://cdn.jsdelivr.net/gh/<REPO>/release/<filename>` → проверяем размер > min_size + первый байт `0x0a` (protobuf tag).
- Атомарная запись (`atomic_write`) — `tmp` → `os.replace`, чтобы не оставить полу-записанный файл при сбое.
- Сравнение нового sha256 с локальным `files/<filename>` — если совпало, статус `unchanged`, иначе `updated`.

### Phase 1b — rsync

- `RsyncUploader.upload()` синхает **только обновлённые** файлы.
- SSH-ключ берётся из `SSH_KEY_RUNTIME` (если задан, обычно `/tmp/ssh-key` после copy в entrypoint), иначе из `SSH_KEY_PATH`.
- Опции SSH: `StrictHostKeyChecking=accept-new`, `BatchMode=yes` — не зависает на интерактивных промптах.

### Phase 2a — build deeplinks

- Качаем `https://raw.githubusercontent.com/<ROUTING_REPO>/<BRANCH>/<CLIENT>/JSONSUB.JSON` для каждого `client_type` из `ROUTING_CLIENTS`.
- Если задан `GEO_PUBLIC_URL` — подменяем `data["Geoipurl"]` и `data["Geositeurl"]`.
- Сериализация: `json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"`. Trailing `\n` критичен — INCY/Happ ждут такой формат.
- base64 — стандартный `base64.b64encode(...).decode("ascii")`.
- Префиксы захардкожены в `CLIENT_PREFIXES`:
  - `INCY` → `://routing/onadd/<base64>` (без схемы)
  - `HAPP` → `happ://routing/onadd/<base64>` (со схемой)
- Логирование: `logging.info(f"{label}: {deeplink}")` — пользователь видит full deeplink в `docker logs` и в `./logs/sync.log`.

### Phase 2b — push в Remnawave

- GET `/api/subscription-settings` → берём `uuid` и `responseRules`.
- В `responseRules.rules` ищем правило по `name == INCY_RULE_NAME`. Если не найдено — `ValueError` (Phase 2b фейлит).
- Модифицируем `responseModifications.headers[].value` (или добавляем header с key=`routing`).
- В payload PATCH'а — `{uuid, responseRules, happRouting}` (только нужные поля; остальные не трогаем).
- При успехе — атомарно сохраняем JSONSUB-снапшоты в `./files/routing-{CLIENT}.json` для следующего сравнения.

### Состояние

Состояния в отдельном `state.json` **нет**. Сами файлы в `./files/` — это состояние:
- `geoip.dat`, `geosite.dat` — последняя успешная версия (для sha256-сравнения)
- `routing-INCY.json`, `routing-HAPP.json` — последний успешно применённый/скачанный JSONSUB

При первом запуске файлов нет → всё «updated».

### Уведомления

- `STARTUP_NOTIFY=1` — первый прогон через entrypoint. Telegram-алерт шлётся.
- `STARTUP_NOTIFY=0` — cron-запуски. Telegram-алерт тоже шлётся (для видимости).
- Сводка не содержит сырых deeplinks — они только в логах.

## Контракты

### Remnawave API

- `GET /api/subscription-settings` → `{response: {uuid, responseRules, happRouting, ...}}` или `{uuid, ...}` без wrapper'а (зависит от версии).
- `PATCH /api/subscription-settings` body: `{uuid, ...fields_to_update}`. Остальные поля сохраняются.
- Auth: `Authorization: Bearer <JWT>`. Опционально `X-Api-Key: <caddy_token>` для панелей с Caddy auth-portal.
- Версия Remnawave проверялась: backend 2.7.4.

### Deeplink format

JSON content внутри base64:
- Компактный (no spaces): `json.dumps(d, separators=(",", ":"))`.
- Кодировка UTF-8.
- Trailing `\n` обязателен.

Тег `LastUpdated` берётся как есть из upstream JSONSUB.JSON. Мы его НЕ модифицируем — hydraponique бампает его сам через GitHub Actions, когда меняются geo-файлы.

## GitHub Actions

- Workflow `.github/workflows/docker-publish.yml`:
  - On push to `master` → собирает образ → пушит `grandvan/roscomvpn-geo-sync:latest` на Docker Hub.
  - On tag `N.N.N` (без `v`-префикса, регex `[0-9]+.[0-9]+.[0-9]+`) → дополнительно пушит `:1.0.0`.
  - On `workflow_dispatch` → ручной запуск.
- Secrets: `DOCKERHUB_USERNAME` (`grandvan`), `DOCKERHUB_TOKEN` (PAT из Docker Hub).
- Cache: GitHub Actions cache (`type=gha`) для слоёв.

## Branch model

- `master` — продакшен. CI собирает Docker-образ.
- `develop` — рабочая ветка. PR `develop → master` после ручного тестирования.
