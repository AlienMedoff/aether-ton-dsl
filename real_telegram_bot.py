"""
Реальный Telegram Bot для Aether OS с aiogram
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import DAGOrchestrator, Task, TaskStatus, MemoryTaskStore, MockAgentRunner, Gatekeeper, SecurityFilter, Reaper

# Установка aiogram для реального бота
try:
    from aiogram import Bot, Dispatcher, types, F
    from aiogram.filters import Command
    AIogram_AVAILABLE = True
except ImportError:
    AIogram_AVAILABLE = False
    print("aiogram не установлен. Установите: pip install aiogram")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

class AetherOSTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.orchestrator = None
        self.store = MemoryTaskStore()
        self.user_tasks: Dict[int, str] = {}
        
    async def setup_orchestrator(self):
        """Настройка оркестратора"""
        agent = MockAgentRunner()
        self.orchestrator = DAGOrchestrator(
            agent=agent,
            store=self.store,
            gatekeeper=Gatekeeper(),
            security_filter=SecurityFilter(),
            reaper=Reaper(self.store, stale_threshold=600),
        )
        
    async def create_sample_workflow(self, user_id: int, workflow_type: str = "default"):
        """Создание примера workflow"""
        workflow_id = f"user_{user_id}_{workflow_type}"
        
        if workflow_type == "default":
            # Стандартный DAG: fetch -> process -> validate -> report
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_fetch", payload={"source": "toncenter", "user_id": user_id})
            )
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_process", 
                     dependencies={f"{workflow_id}_fetch"},
                     payload={"op": "merge", "user_id": user_id})
            )
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_validate",
                     dependencies={f"{workflow_id}_process"},
                     payload={"user_id": user_id})
            )
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_report",
                     dependencies={f"{workflow_id}_validate"},
                     payload={"format": "markdown", "user_id": user_id})
            )
            
        elif workflow_type == "parallel":
            # Параллельное выполнение
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_task1", payload={"source": "api1", "user_id": user_id})
            )
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_task2", payload={"source": "api2", "user_id": user_id})
            )
            await self.orchestrator.add_task(
                Task(id=f"{workflow_id}_merge",
                     dependencies={f"{workflow_id}_task1", f"{workflow_id}_task2"},
                     payload={"op": "combine", "user_id": user_id})
            )
        
        self.user_tasks[user_id] = workflow_id
        return workflow_id
    
    async def get_task_status(self, user_id: int) -> str:
        """Получение статуса задач пользователя"""
        if user_id not in self.user_tasks:
            return "Нет активных задач"
            
        workflow_id = self.user_tasks[user_id]
        tasks = await self.store.all()
        user_tasks = [t for t in tasks if workflow_id in t.id]
        
        if not user_tasks:
            return "Задачи не найдены"
            
        status_lines = []
        for task in user_tasks:
            icon = "✅" if task.status == TaskStatus.COMPLETED else "🔄" if task.status == TaskStatus.IN_PROGRESS else "⏳"
            status_lines.append(f"{icon} {task.id}: {task.status.value}")
            
        return "\n".join(status_lines)
    
    async def run_workflow(self, user_id: int, workflow_type: str = "default"):
        """Запуск workflow"""
        await self.setup_orchestrator()
        workflow_id = await self.create_sample_workflow(user_id, workflow_type)
        
        # Запуск в фоне
        asyncio.create_task(self.orchestrator.start())
        
        return f"Workflow '{workflow_id}' запущен! 🚀"

async def create_real_bot():
    """Создание реального Telegram бота"""
    if not AIogram_AVAILABLE:
        print("Ошибка: aiogram не установлен")
        print("Установите: pip install aiogram")
        return
        
    # Токен нужно получить у @BotFather
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        print("Ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        print("Создайте .env файл с:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token_here")
        return
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    aether_bot = AetherOSTelegramBot(BOT_TOKEN)
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "🌌 **Aether OS Bot**\n\n"
            "Добро пожаловать в систему управления DAG-оркестратором!\n\n"
            "Доступные команды:\n"
            "/help - помощь\n"
            "/status - статус задач\n"
            "/run - запустить стандартный workflow\n"
            "/run_parallel - запустить параллельный workflow\n"
            "/stop - остановить задачи\n\n"
            "Выберите команду для начала работы! 🚀",
            parse_mode="Markdown"
        )
    
    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        await message.answer(
            "📖 **Справка Aether OS**\n\n"
            "**Команды:**\n"
            "• `/start` - приветствие и информация\n"
            "• `/status` - показать статус всех задач\n"
            "• `/run` - запустить последовательный workflow\n"
            "• `/run_parallel` - запустить параллельный workflow\n"
            "• `/stop` - очистить все задачи\n\n"
            "**Workflow типы:**\n"
            "🔹 **Sequential** - fetch → process → validate → report\n"
            "🔹 **Parallel** - task1 + task2 → merge\n\n"
            "**Статусы задач:**\n"
            "⏳ CREATED - создана\n"
            "🔄 IN_PROGRESS - выполняется\n"
            "✅ COMPLETED - завершена\n"
            "❌ FAILED - ошибка\n\n"
            "Готов к работе! 🎯",
            parse_mode="Markdown"
        )
    
    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        status = await aether_bot.get_task_status(message.from_user.id)
        await message.answer(f"📊 **Статус задач:**\n\n{status}", parse_mode="Markdown")
    
    @dp.message(Command("run"))
    async def cmd_run(message: types.Message):
        result = await aether_bot.run_workflow(message.from_user.id, "default")
        await message.answer(f"🚀 {result}")
    
    @dp.message(Command("run_parallel"))
    async def cmd_run_parallel(message: types.Message):
        result = await aether_bot.run_workflow(message.from_user.id, "parallel")
        await message.answer(f"🚀 {result}")
    
    @dp.message(Command("stop"))
    async def cmd_stop(message: types.Message):
        if message.from_user.id in aether_bot.user_tasks:
            del aether_bot.user_tasks[message.from_user.id]
            # Очистка хранилища
            tasks = await aether_bot.store.all()
            for task in tasks:
                if str(message.from_user.id) in task.id:
                    task.status = TaskStatus.FAILED
                    task.error = "Stopped by user"
                    await aether_bot.store.set(task)
            await message.answer("🛑 Все задачи остановлены")
        else:
            await message.answer("Нет активных задач для остановки")
    
    @dp.message()
    async def echo_handler(message: types.Message):
        await message.answer(
            f"Неизвестная команда: {message.text}\n"
            "Используйте /help для справки"
        )
    
    print("Starting Aether OS Telegram Bot...")
    print("Bot is ready!")
    print("Commands available: /start, /help, /status, /run, /run_parallel, /stop")

def setup_instructions():
    """Инструкции по настройке"""
    print("""
🤖 **Настройка реального Telegram бота для Aether OS**

1. **Создание бота:**
   - Откройте Telegram и найдите @BotFather
   - Отправьте команду /newbot
   - Следуйте инструкциям для создания бота
   - Сохраните токен бота

2. **Установка зависимостей:**
   pip install aiogram python-dotenv

3. **Создание .env файла:**
   echo "TELEGRAM_BOT_TOKEN=your_bot_token_here" > .env

4. **Запуск бота:**
   python real_telegram_bot.py

5. **Использование:**
   - Найдите вашего бота в Telegram
   - Отправьте /start для начала
   - Используйте команды для управления workflow

**Функции бота:**
✅ Управление DAG-оркестратором
✅ Запуск последовательных и параллельных workflow
✅ Мониторинг статуса задач
✅ Остановка и очистка задач
✅ Интеграция с Aether OS

**Команды:**
/start - приветствие
/help - справка
/status - статус задач
/run - последовательный workflow
/run_parallel - параллельный workflow
/stop - остановить задачи
    """)

if __name__ == "__main__":
    if not AIogram_AVAILABLE:
        setup_instructions()
    else:
        # Проверяем наличие токена
        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            setup_instructions()
        else:
            asyncio.run(create_real_bot())
