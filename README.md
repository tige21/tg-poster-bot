# tg-poster-bot

Многоаккаунтный Telegram-бот для автоматической публикации постов в группы и автокомментирования. Управляется через aiogram-бот (admin UI). Пользовательские аккаунты подключаются через Telethon с поддержкой SOCKS5/SOCKS4/HTTP прокси.

---

## Содержание

- [Архитектура](#архитектура)
- [Требования](#требования)
- [Быстрый старт (локально)](#быстрый-старт-локально)
- [Настройка переменных окружения](#настройка-переменных-окружения)
- [Получение API_ID и API_HASH](#получение-api_id-и-api_hash)
- [Команды бота](#команды-бота)
- [Пошаговый тест: первый постинг](#пошаговый-тест-первый-постинг)
- [Пошаговый тест: автокомментирование](#пошаговый-тест-автокомментирование)
- [Деплой на VPS (systemd)](#деплой-на-vps-systemd)
- [Запуск тестов](#запуск-тестов)
- [Структура проекта](#структура-проекта)
- [Частые проблемы](#частые-проблемы)

---

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│                   Один процесс Python                │
│                                                     │
│  aiogram Bot (admin UI)                             │
│       │                                             │
│  APScheduler ──► task_runner.py ──► Telethon client │
│                                                     │
│  asyncio event loop                                 │
│       │                                             │
│  monitor.py (autocomment) ──► Telethon client       │
│                                                     │
│  SQLite (data/bot.db)                               │
└─────────────────────────────────────────────────────┘
```

- **aiogram 3.x** — admin-бот, принимает команды, FSM для диалогов
- **Telethon** — пользовательские аккаунты, которые реально постят в группы
- **APScheduler** — расписание задач (daily/interval/once)
- **SQLite** — вся персистентность: аккаунты, прокси, группы, посты, задачи, логи

---

## Требования

- Python 3.11+
- Telegram-бот (создать через @BotFather)
- Telegram API ключи (получить на my.telegram.org)
- Хотя бы один Telegram user-аккаунт для постинга

---

## Быстрый старт (локально)

```bash
# 1. Клонировать / перейти в директорию
cd /путь/к/tg-poster-bot

# 2. Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env
cp .env.example .env
# Отредактировать .env — заполнить все значения (см. ниже)

# 5. Запустить
python main.py
```

Ожидаемый вывод:
```
2026-01-01 12:00:00 __main__ INFO Bot started. Admin: 123456789
```

---

## Настройка переменных окружения

Файл `.env` (скопировать из `.env.example`):

```env
# Токен бота от @BotFather
BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Твой Telegram user ID (не username, а числовой ID)
# Узнать: написать @userinfobot или @getmyid_bot
ADMIN_CHAT_ID=123456789

# API ключи — получить на https://my.telegram.org
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890

# Пути к данным (можно оставить по умолчанию)
DB_PATH=data/bot.db
MEDIA_DIR=data/media
```

### Получение API_ID и API_HASH

1. Открыть https://my.telegram.org
2. Войти через номер телефона
3. Перейти в **API development tools**
4. Заполнить форму (название приложения — любое, например "poster")
5. Скопировать `App api_id` и `App api_hash`

> Эти ключи используются для подключения Telethon-аккаунтов. У всех аккаунтов в боте будут одни и те же API_ID/API_HASH (можно использовать официальные ключи Telegram).

### Как узнать свой ADMIN_CHAT_ID

Написать `/start` боту [@userinfobot](https://t.me/userinfobot) — он ответит твоим числовым ID.

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Показать меню |
| `/proxies` | Список прокси |
| `/add_proxy` | Добавить прокси |
| `/del_proxy <id>` | Удалить прокси |
| `/accounts` | Список аккаунтов |
| `/add_account` | Добавить аккаунт (авторизация по номеру телефона) |
| `/set_proxy <acc_id> <proxy_id>` | Привязать прокси к аккаунту |
| `/groups` | Список групп |
| `/add_group` | Добавить группу/канал |
| `/posts` | Библиотека постов |
| `/add_post` | Создать пост (текст или фото+подпись) |
| `/del_post <id>` | Удалить пост |
| `/tasks` | Список задач |
| `/add_task` | Создать задачу постинга или автокомментирования |
| `/toggle_task <id>` | Включить/выключить задачу |

---

## Пошаговый тест: первый постинг

### Шаг 1. Добавить прокси (опционально)

Если аккаунт нужно запускать через прокси:

```
/add_proxy
socks5 1.2.3.4 1080 username password
```

Бот проверит доступность через TCP-пинг и ответит:
```
✅ Прокси #1 добавлен: OK, 142ms
SOCKS5 1.2.3.4:1080
```

Без прокси — пропустить этот шаг.

### Шаг 2. Добавить Telegram-аккаунт

```
/add_account
```

Бот попросит номер телефона:
```
Введи номер телефона в формате +79991234567:
```

Ввести номер → Telegram пришлёт SMS/код в приложение → ввести код:
```
📲 Код отправлен. Введи его:
```

Если у аккаунта включена двухфакторная аутентификация (2FA):
```
🔐 Требуется пароль двухфакторной аутентификации:
```

Ввести пароль. После успешной авторизации:
```
✅ Аккаунт #1 (+79991234567) добавлен!
```

> Session string сохраняется в SQLite — при перезапуске бота повторная авторизация не нужна.

### Шаг 3. Привязать прокси к аккаунту (если добавлял)

```
/set_proxy 1 1
```
(аккаунт #1, прокси #1)

### Шаг 4. Добавить группу

```
/add_group
```

Ввести `@username` группы или invite-ссылку (`https://t.me/joinchat/...`):
```
✅ Группа #1 добавлена: @test_group
```

> Аккаунт должен быть участником группы, иначе при постинге получишь ошибку.

### Шаг 5. Создать пост

**Текстовый пост:**
```
/add_post
```
Ввести название (для поиска в меню):
```
Тест 1
```
Ввести текст поста:
```
Привет! Это тестовый пост 🚀
```
Ответ:
```
✅ Пост #1 «Тест 1» сохранён.
```

**Пост с фото:** отправить фото с подписью на шаге ввода контента.

### Шаг 6. Создать задачу постинга

```
/add_task
```

Диалог:
```
Выбери аккаунт (введи номер ID):
  #1 +79991234567
```
Ввести: `1`

```
Выбери пост (введи ID):
  #1 Тест 1
```
Ввести: `1`

```
Введи ID групп через запятую:
  #1 @test_group
```
Ввести: `1`

```
Тип задачи:
  post — публиковать посты по расписанию
  autocomment — комментировать новые посты
```
Ввести: `post`

```
Расписание:
  daily HH:MM — каждый день в указанное время
  interval N  — каждые N минут
  once YYYY-MM-DDTHH:MM — один раз
```

Варианты:
- `interval 1` — каждую минуту (для теста)
- `daily 10:00` — каждый день в 10:00
- `once 2026-06-01T15:00` — один раз 1 июня в 15:00

Ввести: `interval 1`

```
✅ Задача #1 создана:
  Тип: post
  Расписание: interval 1
```

Через минуту пост появится в группе. Проверить в `/tasks`:
```
✅ #1 [post] acc#1 post#1 (interval:1)
```

### Пауза / возобновление задачи

```
/toggle_task 1
```
```
Задача #1 ⏸ приостановлена.
```

---

## Пошаговый тест: автокомментирование

Автокомментирование отслеживает новые посты в указанных группах и автоматически оставляет комментарий от аккаунта.

### Требования

- Группа должна иметь открытые комментарии
- Аккаунт должен быть участником группы

### Создать задачу autocomment

При создании задачи (`/add_task`) на шаге "Тип задачи" выбрать:
```
autocomment
```

Расписание для autocomment всё равно нужно ввести (оно используется как `delay_seconds` — задержка перед комментарием в секундах):
```
interval 30
```
(комментарий появится через случайное время от 5 до 30 секунд после нового поста)

После создания задачи монитор запускается в фоне. Как только в группе появится новый пост — аккаунт прокомментирует его содержимым поста #1.

---

## Деплой на VPS (systemd)

### 1. Загрузить проект на VPS

```bash
rsync -av \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='data/' \
  --exclude='.env' \
  --exclude='__pycache__' \
  /Users/GID/Documents/projects/tg-poster-bot/ \
  root@<IP_VPS>:/root/tg-poster-bot/
```

### 2. На VPS: настроить окружение

```bash
ssh root@<IP_VPS>
cd /root/tg-poster-bot

# Создать venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Создать .env
cp .env.example .env
nano .env  # заполнить BOT_TOKEN, ADMIN_CHAT_ID, API_ID, API_HASH

# Создать директорию данных
mkdir -p data/media
```

### 3. Установить systemd-сервис

```bash
cp tg-poster.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable tg-poster
systemctl start tg-poster
```

### 4. Проверить статус

```bash
systemctl status tg-poster
# или смотреть логи в реальном времени:
journalctl -u tg-poster -f
```

Ожидаемый вывод:
```
● tg-poster.service - Telegram Poster Bot
     Active: active (running)
...
Jan 01 12:00:00 vps python[1234]: 2026-01-01 12:00:00 __main__ INFO Bot started. Admin: 123456789
```

### 5. Обновить бота

```bash
# Загрузить новую версию
rsync -av --exclude='.venv' --exclude='data/' --exclude='.env' \
  /путь/к/проекту/ root@<IP>:/root/tg-poster-bot/

# Перезапустить
ssh root@<IP> "systemctl restart tg-poster"
```

---

## Запуск тестов

```bash
# Активировать venv
source .venv/bin/activate  # или venv/bin/activate

# Все тесты
pytest tests/ -v --asyncio-mode=auto

# Только конкретный модуль
pytest tests/test_models.py -v
pytest tests/test_poster.py -v
```

Ожидаемый результат: `23 passed`.

Покрытие тестами:
| Модуль | Что тестируется |
|--------|----------------|
| `test_models.py` | Все CRUD-операции SQLite (8 тестов) |
| `test_proxy_checker.py` | ok / slow / fail через мок TCP-соединения (3 теста) |
| `test_account_pool.py` | Создание пула, добавление, удаление клиентов (3 теста) |
| `test_poster.py` | send_post / send_comment с текстом и фото (5 тестов) |
| `test_task_runner.py` | build_trigger для daily/interval/once/invalid (4 теста) |

---

## Структура проекта

```
tg-poster-bot/
├── main.py                    # Точка входа — запускает всё
├── config.py                  # Переменные окружения
├── requirements.txt
├── .env.example               # Шаблон .env
├── tg-poster.service          # systemd unit
│
├── db/
│   ├── database.py            # init_db(), get_conn(), 7 таблиц SQLite
│   └── models.py              # CRUD: proxies, accounts, groups,
│                              #        posts, tasks, autocomment_state, send_log
│
├── core/
│   ├── proxy_checker.py       # TCP-пинг прокси → ok/slow/fail
│   ├── account_pool.py        # Пул Telethon-клиентов (account_id → TelegramClient)
│   ├── poster.py              # send_post() / send_comment()
│   └── monitor.py             # Autocomment: слушает NewMessage через Telethon events
│
├── scheduler/
│   └── task_runner.py         # APScheduler: daily/interval/once → _run_post_task()
│
├── bot/
│   ├── router.py              # /start, admin guard
│   └── handlers/
│       ├── proxies.py         # /proxies /add_proxy /del_proxy
│       ├── accounts.py        # /accounts /add_account (FSM: phone→code→2FA)
│       ├── groups.py          # /groups /add_group
│       ├── posts.py           # /posts /add_post /del_post
│       └── tasks.py           # /tasks /add_task /toggle_task
│
└── tests/
    ├── test_models.py
    ├── test_proxy_checker.py
    ├── test_account_pool.py
    ├── test_poster.py
    └── test_task_runner.py
```

---

## Частые проблемы

### Бот не отвечает на команды

Проверить `ADMIN_CHAT_ID` — бот игнорирует все сообщения не от admin. Узнать свой ID: написать @userinfobot.

### `SessionPasswordNeededError` при добавлении аккаунта

Включена 2FA. Бот сам попросит пароль — просто ввести его в следующем сообщении.

### `FloodWaitError: A wait of Xs is required`

Telegram ограничил частоту отправки. Бот автоматически ждёт указанное время и продолжает. Уменьшить частоту задач через `/toggle_task` и пересоздать с бо́льшим интервалом.

### `UserNotParticipantError` при постинге

Аккаунт не является участником группы. Вступить в группу с этого аккаунта вручную через Telegram-приложение.

### `ChatWriteForbiddenError`

В группе запрещено писать участникам или нужна верификация. Проверить права аккаунта в группе.

### Аккаунт помечен как `banned` в `/accounts`

Telegram заблокировал аккаунт. Использовать другой аккаунт или проверить причину блокировки в Telegram-приложении.

### Session string не сохраняется между перезапусками

Проверить путь `DB_PATH` в `.env` — файл `bot.db` должен быть доступен для записи. По умолчанию создаётся в `data/bot.db` относительно рабочей директории.

### `ModuleNotFoundError` при запуске

Не активировано виртуальное окружение или не установлены зависимости:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```
