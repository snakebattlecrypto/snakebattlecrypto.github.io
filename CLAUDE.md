# Snake Battle — Project Context

## Текущее состояние (что уже сделано)

### Landing Page (index.html) — ГОТОВ, на проде
- Домен: **snakebattle.cc** (GitHub Pages)
- Стиль: тёмный фон, neon cyan/magenta, glassmorphism (по pitch deck)
- Секции: Hero, Feature pills (4 карточки), How It Works (4 step-cards), Waitlist форма, Footer
- Интерактивные змейки на canvas (бегут по сетке при движении курсора)
- Навигация: лого слева, "Join Waitlist" справа (мобильная адаптация)
- Соцсети: Telegram, X, Instagram, YouTube, TikTok (3+2 flex на мобильном) — с реальными ссылками
- Favicon: SVG змейка в neon стиле проекта
- Footer ссылки: Whitepaper (docs.snakebattle.cc), Pitch Deck (deck.snakebattle.cc)
- Форма шлёт POST на api.snakebattle.cc/api/waitlist
- После сабмита — ссылка на бота t.me/snakebattlecryptobot
- 409 (already verified) — зелёная галочка + кнопка на бота
- 429 — user-friendly сообщение "Too many requests"
- "Failed to fetch" — сообщение "Connection error"
- Реферальный код сохраняется в sessionStorage при визите через ?ref=
- Мобильная адаптация: step-cards 2x2, компактные секции, адаптивный nav

### Backend (FastAPI) — ГОТОВ, на проде
- Путь: `backend/` в этом же репо
- API: `POST /api/waitlist`, `POST /api/telegram/webhook`, `GET /health`
- **4 Uvicorn workers** за Nginx reverse proxy
- **Redis email queue** — async отправка через background worker с retry (3 попытки, 5/15/30s)
- Email через Resend API (httpx async client)
- Rate limit: 5 кодов/час на email (БД), 10/мин на IP (slowapi), 2r/s на IP (Nginx)
- Код живёт 15 мин, генерируется через `secrets.choice` (криптографически безопасный)
- DB connection pool: pool_size=5, max_overflow=10, pre_ping=True, recycle=1800
- Atomic waitlist position через pg_advisory_xact_lock + MAX(waitlist_position)
- Webhook аутентификация через secret_token (SHA-256 от bot token)
- Brute-force защита кодов через Redis INCR+EXPIRE (10 попыток/15 мин, shared across workers)
- Self-referral защита (сравнение user IDs при верификации)
- Валидация referral кода в БД перед сохранением, max_length=8
- Referral только при первичной регистрации (нет ретроактивной инъекции)
- MultipleResultsFound обработан для коллизий 6-значных кодов
- Логирование неудачных попыток верификации
- Fallback на прямую Resend отправку если Redis недоступен
- Стек: FastAPI, SQLAlchemy async, asyncpg, pydantic 2.8.2, httpx, redis, slowapi

### Telegram Bot (@snakebattlecryptobot) — ГОТОВ, на проде
- aiogram 3.13, webhook mode с secret token
- Команды:
  - /start — проверяет статус: если verified → реферальная ссылка + ссылки на канал/чат, иначе просит код
  - /status — позиция в waitlist + кол-во рефералов
  - /referral — реферальная ссылка + счётчик (guard на None referral_code)
  - /help — список команд
- Верификация 6-значным кодом с SELECT FOR UPDATE (row locking)
- Referral code генерация с collision retry (5 попыток, secrets.choice)
- IntegrityError handling для double-tap protection
- После верификации — ссылки на TG канал (t.me/snakebattlecrypto) и чат (t.me/snakebattlecryptochat)

### Инфраструктура
- **GitHub:** github.com/snakebattlecrypto/snakebattlecrypto.github.io (main ветка)
- **Сервер:** 195.201.232.33 (Hetzner Ubuntu, 4GB RAM)
- **Docker:** backend-app-1 + backend-db-1 (PostgreSQL 16) + backend-redis-1 (Redis 7)
- **Docker healthchecks:** на всех 3 контейнерах (app через /health, db через pg_isready, redis через redis-cli ping)
- **Redis:** с паролем (requirepass), persistent volume
- **Nginx:** reverse proxy → api.snakebattle.cc, SSL через certbot, rate limiting (2 зоны)
- **Cloudflare:** proxy включен на api рекорде, SSL Full (strict), real_ip_header CF-Connecting-IP
- **DNS (Cloudflare):**
  - A @ → GitHub Pages (лендинг)
  - CNAME api → 195.201.232.33 (Proxied, API)
  - CNAME docs → mazetezr.github.io (Whitepaper)
  - CNAME deck → mazetezr.github.io (Pitch Deck)
- **Email:** Resend API (домен snakebattle.cc, httpx async client)
- **Uvicorn:** --workers 4, --forwarded-allow-ips 127.0.0.1
- **Путь на сервере:** ~/snakebattle/backend/

### Внешние ресурсы
- **Whitepaper:** docs.snakebattle.cc (GitHub Pages: mazetezr/snake-battle-documentation)
- **Pitch Deck:** deck.snakebattle.cc (GitHub Pages: mazetezr/snake-battle-presentation)

### Деплой
1. Пуш в GitHub
2. На сервере: `cd ~/snakebattle && git pull && cd backend && sudo docker compose up -d --build`
3. Nginx конфиг (если менялся): `sudo cp ~/snakebattle/backend/nginx/api.snakebattle.cc.conf /etc/nginx/sites-available/ && sudo certbot --nginx -d api.snakebattle.cc` (выбрать 1 reinstall) → `sudo nginx -t && sudo systemctl reload nginx`

### Известные ограничения
- pydantic 2.8.2 (не 2.9) — конфликт с aiogram 3.13
- config.py: `extra = "ignore"` для лишних ENV переменных
- ~~SES в sandbox~~ — мигрировали на Resend API
- Email enumeration через 409 vs 200 — осознанный trade-off для UX
- Нет Alembic миграций — таблицы через create_all на старте

---

## Сделано 2026-04-05

### Landing Page
- Удалён Facebook из footer соцсетей
- Проставлены реальные ссылки на все 5 соцсетей (Telegram, X, Instagram, YouTube, TikTok)
- Мобильный grid соцсетей: 2x3 grid → 3+2 flex layout (для 5 элементов)
- Добавлен SVG favicon (змейка в neon cyan/magenta стиле)

### Telegram Bot
- Ссылки на TG канал и чат после успешной верификации
- Ссылки на TG канал и чат в /start для уже верифицированных

---

## Сделано 2026-04-04

### Performance Hardening
- Uvicorn 1→4 workers
- Redis email queue с retry логикой (вместо синхронной отправки SES)
- Неблокирующий SES через run_in_executor + singleton boto3 клиент
- DB connection pool tuning (pool_size=5, max_overflow=10, pre_ping, recycle)
- Nginx rate limiting (2 зоны: api_waitlist 2r/s, api_general 10r/s)
- slowapi IP rate limiting (10/мин на waitlist endpoint)
- Cloudflare proxy + real_ip_header для Nginx
- Docker healthcheck для app контейнера

### Security Fixes (раунд 1 — рефералы)
- secrets вместо random для генерации кодов
- Индекс на referred_by
- max_length=8 на ref в Pydantic
- Валидация что ref существует в БД
- SELECT FOR UPDATE для предотвращения race condition при верификации
- Collision retry для referral code (5 попыток)
- Self-referral prevention (сравнение user IDs)
- Guard на None referral_code в /referral
- sessionStorage для ref на фронте
- IntegrityError handling для double-tap

### Security Fixes (раунд 2 — критические)
- Webhook secret token (SHA-256 от bot token + X-Telegram-Bot-Api-Secret-Token)
- Brute-force protection через Redis INCR+EXPIRE (работает across workers)
- slowapi --forwarded-allow-ips 127.0.0.1 (вместо *)
- Redis requirepass
- Email queue без plaintext кодов (код берётся из БД при отправке)

### Security Fixes (раунд 3 — оставшиеся)
- Atomic waitlist position через pg_advisory_xact_lock
- Позиция из MAX(waitlist_position) вместо MAX(id)
- Thread-safe SES singleton (double-checked locking)
- Убрана ретроактивная инъекция реферала
- MultipleResultsFound обработан для коллизий кодов
- Логирование неудачных попыток верификации
- Frontend: обработка non-JSON ответов (Nginx 429, connection errors)
- Fallback на прямую SES отправку если Redis down

### Frontend
- Мобильная адаптация лендинга (step-cards 2x2, компактные секции, nav)
- Footer соцсети 2x2 grid на мобильном
- Уменьшенные кнопки соцсетей
- Ссылки Whitepaper + Pitch Deck в footer
- Copyright 2025→2026

### Bot
- /start показывает статус если уже верифицирован

---

## ТЗ (оригинальная спецификация)

Лендинг (snakebattle.cc)
Секции (сверху вниз)

Hero: Логотип + слоган «Play & Earn. Multiplayer PvP with Real Crypto Stakes» + трейлер (embed)
Как это работает: 3–4 карточки (Deposit → Choose League → Play & Hunt → Withdraw)
Waitlist-форма: Поле email + кнопка «Join Waitlist»
Соцсети: Кнопки Telegram / Twitter / Discord (если будет)

Waitlist-механика (подробный flow)
Пользователь вводит email на лендинге
        ↓
Система отправляет 6-значный код на email
        ↓
Email сохраняется в БД: статус = "pending"
        ↓
Лендинг показывает экран:
  "Проверь почту → введи код в нашем Telegram-боте"
  + кнопка/ссылка на бота
        ↓
Пользователь открывает бота, нажимает /start
        ↓
Бот просит ввести код из письма
        ↓
Бот проверяет:
  - Код валидный?
  - Не истёк (15 мин)?
  - Не использован?
        ↓
Если всё ок:
  - Привязывает telegram_id к email
  - Статус = "verified"
  - Генерирует реферальную ссылку
  - Отправляет приветственное сообщение
        ↓
Если код неверный / истёк:
  - Бот предлагает запросить новый код
    (через кнопку, отправляется новый код на тот же email)
Защита

Один email = один telegram_id (и наоборот)
Код живёт 15 минут
При запросе нового кода старый аннулируется
Rate limit: максимум 5 запросов кода в час на один email

Стек (примерный)

Frontend: HTML/CSS/JS — статика, хостинг на GitHub Pages
Backend: Python (FastAPI)
БД: PostgreSQL
Email: AWS SES

3. Telegram-бот
Команды:
- /start — Проверяет статус, приветствие или показ реферальной ссылки
- /status — Показывает статус: pending / verified
- /referral — Показывает реферальную ссылку и количество приглашённых
- /help — Справка

Реферальная механика
После верификации пользователь получает ссылку: snakebattle.cc/?ref=XXXX
Когда новый пользователь приходит по ссылке — реферер записывается в БД
В боте: «Ты привёл: 12 человек. Твоя позиция в waitlist: #347»
