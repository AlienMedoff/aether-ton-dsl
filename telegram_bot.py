"""
Telegram Bot для управления Aether OS
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import DAGOrchestrator, Task, TaskStatus, MemoryTaskStore, MockAgentRunner, Gatekeeper, SecurityFilter, Reaper

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

class AetherOSBot:
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
            # Стандартный DAG: fetch → process → validate → report
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

# Mock Telegram Bot API (для демонстрации)
class MockTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.aether_bot = AetherOSBot(token)
        self.commands = {
            '/start': self.cmd_start,
            '/help': self.cmd_help,
            '/status': self.cmd_status,
            '/run': self.cmd_run,
            '/run_parallel': self.cmd_run_parallel,
            '/stop': self.cmd_stop,
        }
        
    async def cmd_start(self, user_id: int, args: list = None):
        """Команда /start"""
        return """
🌌 **Aether OS Bot**

Добро пожаловать в систему управления DAG-оркестратором!

Доступные команды:
/help - помощь
/status - статус задач
/run - запустить стандартный workflow
/run_parallel - запустить параллельный workflow
/stop - остановить задачи

Выберите команду для начала работы! 🚀
        """
        
    async def cmd_help(self, user_id: int, args: list = None):
        """Команда /help"""
        return """
📖 **Справка Aether OS**

**Команды:**
• `/start` - приветствие и информация
• `/status` - показать статус всех задач
• `/run` - запустить последовательный workflow
• `/run_parallel` - запустить параллельный workflow  
• `/stop` - очистить все задачи

**Workflow типы:**
🔹 **Sequential** - fetch → process → validate → report
🔹 **Parallel** - task1 + task2 → merge

**Статусы задач:**
⏳ CREATED - создана
🔄 IN_PROGRESS - выполняется
✅ COMPLETED - завершена
❌ FAILED - ошибка

Готов к работе! 🎯
        """
        
    async def cmd_status(self, user_id: int, args: list = None):
        """Команда /status"""
        return await self.aether_bot.get_task_status(user_id)
        
    async def cmd_run(self, user_id: int, args: list = None):
        """Команда /run"""
        return await self.aether_bot.run_workflow(user_id, "default")
        
    async def cmd_run_parallel(self, user_id: int, args: list = None):
        """Команда /run_parallel"""
        return await self.aether_bot.run_workflow(user_id, "parallel")
        
    async def cmd_stop(self, user_id: int, args: list = None):
        """Команда /stop"""
        if user_id in self.aether_bot.user_tasks:
            del self.aether_bot.user_tasks[user_id]
            # Очистка хранилища
            tasks = await self.aether_bot.store.all()
            for task in tasks:
                if str(user_id) in task.id:
                    task.status = TaskStatus.FAILED
                    task.error = "Stopped by user"
                    await self.aether_bot.store.set(task)
            return "🛑 Все задачи остановлены"
        return "Нет активных задач для остановки"
    
    async def handle_message(self, user_id: int, text: str):
        """Обработка сообщения"""
        parts = text.strip().split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command in self.commands:
            return await self.commands[command](user_id, args)
        else:
            return f"Неизвестная команда: {command}\nИспользуйте /help для справки"

async def demo_bot():
    """Демонстрация работы бота"""
    print("Демонстрация Telegram Bot для Aether OS")
    print("=" * 50)
    
    bot = MockTelegramBot("mock_token")
    
    # Симуляция команд пользователя
    user_id = 12345
    
    commands = [
        "/start",
        "/run", 
        "/status",
        "/run_parallel",
        "/status",
        "/stop"
    ]
    
    for cmd in commands:
        print(f"\nПользователь: {cmd}")
        response = await bot.handle_message(user_id, cmd)
        print(f"Bot: {response}")
        
        # Небольшая задержка для демонстрации
        await asyncio.sleep(0.5)
    
    print("\n" + "=" * 50)
    print("Демонстрация завершена!")

if __name__ == "__main__":
    asyncio.run(demo_bot())
