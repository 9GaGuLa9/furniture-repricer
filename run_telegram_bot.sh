#!/bin/bash
# Furniture Repricer - Telegram Bot Script
# Запуск Telegram бота для управління

set -e

cd "$(dirname "$0")"

# Активувати venv
source venv/bin/activate

# Запустити бота
echo "Starting Telegram bot..."
echo "Use /help to see available commands"
echo "Press Ctrl+C to stop"

python3 app/telegram_commands.py
