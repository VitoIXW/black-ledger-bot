# black-ledger-bot
Black Ledger Bot brings Luigi to life, your trusted accountant. He keeps track of debts, favors, and outstanding balances of your defaulters… friends. Luigi is discreet, loyal, and never asks unnecessary questions.

## Run tests

```bash
docker compose run --rm --build test
```

## Run Telegram bot

Create a Telegram bot with BotFather and copy the token into `.env`:

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your_token_here
ALLOWED_TELEGRAM_USER_IDS=your_telegram_user_id
DISCOVER_TELEGRAM_USER_ID=0
DB_PATH=/data/black_ledger.db
TZ=Europe/Madrid
```

The bot is locked to the Telegram user ids in `ALLOWED_TELEGRAM_USER_IDS`.

If you do not know your Telegram user id yet, temporarily set:

```env
ALLOWED_TELEGRAM_USER_IDS=
DISCOVER_TELEGRAM_USER_ID=1
```

Start the bot, send `/start`, copy the id Luigi sends back, then stop the bot and set:

```env
ALLOWED_TELEGRAM_USER_IDS=that_id
DISCOVER_TELEGRAM_USER_ID=0
```

Start the bot:

```bash
docker compose up --build app
```

Open Telegram, send `/start`, and use the buttons Luigi sends.
