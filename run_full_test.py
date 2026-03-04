#!/usr/bin/env python3
"""
Полный тестовый скрипт для Aether OS
Запускает все тесты и демонстрирует работу системы
"""

import asyncio
import os
import sys
import subprocess
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

async def run_unit_tests():
    """Запуск unit тестов"""
    logger.info("🧪 Запуск unit тестов...")
    
    tests = [
        "tests/test_engine.py",
        "tests/test_config.py",
        "tests/test_dispatcher.py",
        "tests/test_providers.py",
        "tests/test_rollback_agent.py"
    ]
    
    for test_file in tests:
        if os.path.exists(test_file):
            logger.info(f"  📋 Запуск {test_file}")
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                test_file, "-v", "--tb=short"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"  ✅ {test_file} - PASSED")
            else:
                logger.error(f"  ❌ {test_file} - FAILED")
                logger.error(f"     {result.stdout}")
                logger.error(f"     {result.stderr}")
        else:
            logger.warning(f"  ⚠️  {test_file} - не найден")

async def run_integration_demo():
    """Запуск интеграционной демонстрации"""
    logger.info("🚀 Запуск интеграционной демонстрации...")
    
    # Установка переменных окружения для MOCK режима
    os.environ["TON_MODE"] = "MOCK"
    os.environ["TON_API_KEY"] = "mock"
    os.environ["AGENT_ID"] = "test_agent"
    
    try:
        # Импортируем и запускаем main.py
        from main import main
        await main()
        logger.info("✅ Интеграционная демонстрация завершена успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка в интеграционной демонстрации: {e}")

async def run_contract_tests():
    """Запуск тестов смарт-контрактов"""
    logger.info("📝 Запуск тестов смарт-контрактов...")
    
    # Проверяем наличие Node.js и npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"  📦 npm version: {result.stdout.strip()}")
            
            # Запуск Jest тестов
            result = subprocess.run([
                "npx", "jest", "tests/governance.spec.ts", 
                "--verbose", "--no-cache"
            ], capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:
                logger.info("✅ Тесты смарт-контрактов пройдены")
            else:
                logger.error("❌ Тесты смарт-контрактов не пройдены")
                logger.error(result.stdout)
                logger.error(result.stderr)
        else:
            logger.warning("⚠️  npm не найден, пропускаем тесты контрактов")
    except FileNotFoundError:
        logger.warning("⚠️  Node.js/npm не найдены, пропускаем тесты контрактов")

async def check_dependencies():
    """Проверка зависимостей"""
    logger.info("🔍 Проверка зависимостей...")
    
    # Проверка Python зависимостей
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.read().splitlines()
        
        for req in requirements:
            if req.strip() and not req.startswith("#"):
                package = req.split(">=")[0].split("==")[0].strip()
                try:
                    __import__(package.replace("-", "_"))
                    logger.info(f"  ✅ {package}")
                except ImportError:
                    logger.warning(f"  ⚠️  {package} - не установлен")
    except FileNotFoundError:
        logger.warning("⚠️  requirements.txt не найден")

async def generate_test_report():
    """Генерация отчета о тестировании"""
    logger.info("📊 Генерация отчета о тестировании...")
    
    report = {
        "timestamp": asyncio.get_event_loop().time(),
        "python_version": sys.version,
        "platform": sys.platform,
        "working_directory": os.getcwd(),
    }
    
    # Сохранение отчета
    import json
    with open("test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info("📄 Отчет сохранен в test_report.json")

async def main():
    """Главная функция тестирования"""
    logger.info("🌟 Начало полного тестирования Aether OS")
    logger.info("=" * 50)
    
    try:
        # 1. Проверка зависимостей
        await check_dependencies()
        print()
        
        # 2. Запуск unit тестов
        await run_unit_tests()
        print()
        
        # 3. Запуск интеграционной демонстрации
        await run_integration_demo()
        print()
        
        # 4. Запуск тестов смарт-контрактов
        await run_contract_tests()
        print()
        
        # 5. Генерация отчета
        await generate_test_report()
        
        logger.info("🎉 Полное тестирование завершено!")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при тестировании: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
