#!/usr/bin/env python3
"""
Тест подключения Telegram бота
"""

import os
import asyncio
from aiogram import Bot

async def test_bot():
    """Тест подключения бота"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found!")
        print("Please set token in .env file")
        return False
    
    print("Testing Telegram Bot connection...")
    print(f"Token: {token[:10]}...")
    
    try:
        bot = Bot(token=token)
        bot_info = await bot.get_me()
        
        print(f"SUCCESS!")
        print(f"Bot ID: {bot_info.id}")
        print(f"Bot Name: {bot_info.first_name}")
        print(f"Bot Username: @{bot_info.username}")
        print(f"Bot is ready to receive messages!")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_bot())
