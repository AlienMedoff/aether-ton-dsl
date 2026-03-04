#!/usr/bin/env python3
"""
Запуск реального Telegram бота с токеном
"""

import os
import asyncio
from dotenv import load_dotenv

# Устанавливаем токен (ЗАМЕНИ НА РЕАЛЬНЫЙ)
# Токен должен быть в .env файле
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    print("ERROR: TELEGRAM_BOT_TOKEN not found!")
    print("Please create .env file with token")
    exit(1)

# Импортируем и запускаем бота
try:
    from real_telegram_bot import main
    
    if __name__ == "__main__":
        print("🤖 Starting Aether OS Telegram Bot...")
        print("🔧 Bot: фазербот")
        print("📱 Token configured")
        print("🚀 Launching...")
        print("=" * 50)
        
        asyncio.run(main())
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("📦 Installing required packages...")
    
    import subprocess
    import sys
    
    # Устанавливаем зависимости
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram", "python-dotenv"])
    
    print("🔄 Retrying bot launch...")
    
    # Повторная попытка
    from real_telegram_bot import main
    asyncio.run(main())
    
except Exception as e:
    print(f"❌ Error starting bot: {e}")
    print("🔧 Check your token and internet connection")
