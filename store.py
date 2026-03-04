# store.py
import json
import logging
import redis.asyncio as redis
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class BaseStore:
    async def get_next_pending(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def set(self, task_data: Dict[str, Any]) -> None:
        raise NotImplementedError

class RedisStore(BaseStore):
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        # Используем ConnectionPool для эффективности
        self.pool = redis.ConnectionPool(host=host, port=port, db=db, decode_responses=True)
        self.client = redis.Redis(connection_pool=self.pool)
        self.queue_name = "tasks_queue"

    async def get_next_pending(self) -> Optional[Dict[str, Any]]:
        """Атомарно забирает ID задачи и возвращает её данные."""
        try:
            # LPOP — атомарная операция, никто другой не заберет ту же задачу
            task_id = await self.client.lpop(self.queue_name)
            if not task_id:
                return None
            
            data = await self.client.get(f"task:{task_id}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, task_data: Dict[str, Any]) -> None:
        """Сохраняет задачу и добавляет в очередь, если статус PROCESSING."""
        task_id = str(task_data["id"])
        
        # Pipeline — это "пакетная" отправка команд в Redis, экономит время
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.set(f"task:{task_id}", json.dumps(task_data))
            if task_data.get("status") == "PROCESSING":
                await pipe.rpush(self.queue_name, task_id)
            await pipe.execute()
