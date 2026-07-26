# Telegram Bot

A simple Telegram bot scaffold built with Python and `python-telegram-bot`.

## Setup

1. Create a bot via BotFather and get the bot token.
2. Set the bot token, required channel, and admin IDs in your environment, or place them in a `.env` file in this folder:

   ```powershell
   $env:TELEGRAM_BOT_TOKEN = "your-bot-token"
   $env:TELEGRAM_REQUIRED_CHANNEL = "@yourchannel"
   $env:TELEGRAM_ADMIN_IDS = "123456789"
   ```

   Or use the channel chat ID instead of a username:

   ```powershell
   $env:TELEGRAM_REQUIRED_CHANNEL = "-1001234567890"
   ```

   You can also use an invite link for the same channel:

   ```powershell
   $env:TELEGRAM_REQUIRED_CHANNEL = "https://t.me/+Iyrt7pnjwMVjOTBl"
   ```

   Make sure the bot is added to the required channel so it can verify membership.
   The bot also requires a group chat with at least 25 members to use group features.
   For private chat use, users must be approved by an admin.

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Run the bot:

   ```powershell
   python bot.py
   ```

## Features

- `/start`: Welcome message with usage requirements
- `/help`: Help text with all available commands
- `/status`: Show your current access status
- `/stats`: Show bot statistics (admin only)
- `/groups`: List groups where the bot has been used (admin only)
- `/approve <user_id>`: Approve a user for private bot use (admin only)
- `/num <phone_number>`: Search phone number details using the external API
- Echoes any text message back to the user

