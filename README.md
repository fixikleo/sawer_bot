# SaveKeeper Bot

Telegram-бот для сохранения сообщений с подписками (Telegram Stars),
промокодами, реферальной системой и админ-панелью.

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Отредактируй `config.py`:
- `BOT_TOKEN` — токен от @BotFather
- `ADMIN_ID` — твой Telegram ID (узнать: @userinfobot)
- `ADMIN_USERNAME` — твой username без @
- `PLANS` — тарифы (название, цена в ⭐, дней)

## Подключение Telegram Stars

1. @BotFather → `/mybots` → твой бот → **Payments** → **Telegram Stars**
2. Готово. Без этого `currency="XTR"` не сработает.

## Запуск

```bash
python bot.py
```

## Команды

**Пользователь:** `/start`, `/history`, `/search`, `/stats`, `/pro`, `/promo`, `/ref`, `/clear`

**Админ:** `/admin`

## Структура

```
savekeeper/
├── bot.py
├── config.py
├── database.py
├── keyboards.py
├── handlers/
│   ├── admin.py
│   ├── payments.py
│   ├── promo.py
│   └── user.py
├── requirements.txt
└── README.md
```

## Безопасность админа

Доступ к `/admin` работает только если **совпадают и ID, и username**.
Если сменишь username в Telegram — обнови `ADMIN_USERNAME`.