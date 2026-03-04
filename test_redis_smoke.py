# test_redis_smoke.py
import asyncio
from store import RedisStore
import os

async def test_connection():
    # Используем тот же адрес, что в main.py
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    store = RedisTaskStore(redis_url)
    
    print(f"Connecting to {redis_url}...")
    try:
        # Пытаемся записать тестовую задачу
        test_task = {"id": "smoke_test", "status": "PROCESSING", "payload": "ping"}
        await store.set(test_task)
        print("✅ Success: Wrote to Redis")
        
        # Пытаемся прочитать
        result = await store.get_next_pending()
        print(f"✅ Success: Read from Redis: {result}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
