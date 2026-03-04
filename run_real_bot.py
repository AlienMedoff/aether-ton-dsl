#!/usr/bin/env python3
"""
Запуск реального Telegram бота с токеном
"""

import os
import sys
import subprocess

# Устанавливаем токен (ЗАМЕНИ НА РЕАЛЬНЫЙ)
# Токен должен быть в .env файле или переменных окружения
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    print("ERROR: TELEGRAM_BOT_TOKEN not found in environment variables!")
    print("Please set token in .env file or environment")
    exit(1)

# Устанавливаем aiogram если нужно
try:
    import aiogram
    print("aiogram already installed")
except ImportError:
    print("Installing aiogram...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram", "python-dotenv"])

# Запускаем бота
print("Starting Aether OS Telegram Bot...")
print("Bot: фазербот")
print("Token: configured")
print("=" * 40)

# Импортируем и запускаем
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Запускаем реальный бот как subprocess
import asyncio

if __name__ == "__main__":
    # Просто запускаем real_telegram_bot.py
    subprocess.run([sys.executable, "real_telegram_bot.py"])
