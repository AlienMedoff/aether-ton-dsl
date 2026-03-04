#!/usr/bin/env python3
"""
Безопасная настройка Telegram бота
Токен вводится пользователем и сохраняется только в .env
"""

import os
from pathlib import Path

def setup_bot_securely():
    """Безопасная настройка бота"""
    print("=== SECURE TELEGRAM BOT SETUP ===")
    print()
    
    # Проверяем существует ли .env
    env_file = Path(".env")
    
    if env_file.exists():
        print("Found existing .env file")
        with open(env_file, 'r') as f:
            content = f.read()
            if "TELEGRAM_BOT_TOKEN" in content:
                print("Token already configured in .env")
                return True
    
    # Запрашиваем токен у пользователя
    print("Please enter your Telegram Bot Token:")
    print("(Get token from @BotFather in Telegram)")
    print()
    
    token = input("Token: ").strip()
    
    if not token:
        print("ERROR: No token provided")
        return False
    
    # Проверяем формат токена
    if not token.startswith(("68", "69", "70", "71")) or len(token) < 40:
        print("WARNING: Token format looks invalid")
        print("Please double-check your token from @BotFather")
    
    # Сохраняем в .env
    try:
        with open(env_file, 'w') as f:
            f.write(f"TELEGRAM_BOT_TOKEN={token}\n")
            f.write("# Aether OS Configuration\n")
            f.write("TON_MODE=MOCK\n")
            f.write("AGENT_ID=main\n")
        
        print(f"SUCCESS: Token saved to .env")
        print(f"File: {env_file.absolute()}")
        print(f"Permissions: {oct(env_file.stat().st_mode)[-3:]}")
        
        # Проверяем .gitignore
        gitignore_file = Path(".gitignore")
        if gitignore_file.exists():
            with open(gitignore_file, 'r') as f:
                gitignore_content = f.read()
        else:
            gitignore_content = ""
        
        if ".env" not in gitignore_content:
            with open(gitignore_file, 'a') as f:
                f.write("\n# Security - never commit secrets\n")
                f.write(".env\n")
                f.write("*.key\n")
                f.write("secrets/\n")
            print("Added .env to .gitignore")
        
        return True
        
    except Exception as e:
        print(f"ERROR saving token: {e}")
        return False

def test_secure_setup():
    """Тест безопасной настройки"""
    print("\n=== TESTING SECURE SETUP ===")
    
    # Загружаем из .env
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("ERROR: Token not found in .env")
        return False
    
    print(f"Token loaded from .env: {token[:10]}...")
    print("SUCCESS: Secure setup working!")
    return True

if __name__ == "__main__":
    # Настройка
    if setup_bot_securely():
        # Тест
        if test_secure_setup():
            print("\n=== READY TO RUN BOT ===")
            print("Run: python real_telegram_bot.py")
            print("Your token is now secure and not in Git!")
        else:
            print("\nERROR: Setup test failed")
    else:
        print("\nERROR: Setup failed")
