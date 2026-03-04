# dispatcher.py
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class Dispatcher:
    """
    Orchestrator that routes tasks to the appropriate agents based on their status.
    """
    def __init__(self, store, agents: Dict[str, object]):
        self.store = store
        self.agents = agents
        self.running = True

    async def run_loop(self):
        """Main event loop to process pending tasks."""
        logger.info("Dispatcher started...")
        while self.running:
            try:
                # 1. Fetch next task from storage
                task_data = await self.store.get_next_pending()
                
                if not task_data:
                    await asyncio.sleep(1)
                    continue
                
                # 2. Route task based on status
                status = task_data.get("status")
                agent = self.agents.get(status)
                
                if agent:
                    logger.info(f"Dispatching task {task_data.get('id')} to {agent.__class__.__name__}")
                    await agent.process_task(task_data)
                else:
                    logger.warning(f"No agent registered for status: {status}")
            
            except Exception as e:
                logger.error(f"Error in dispatcher loop: {e}")
                await asyncio.sleep(5) # Prevent CPU spam on persistent errors

    def stop(self):
        self.running = False
