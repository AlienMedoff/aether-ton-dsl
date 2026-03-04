# rollback_agent.py
import logging
from registry import undo_registry
from models import TaskModel

logger = logging.getLogger(__name__)

class RollbackAgent:
    def __init__(self, store):
        self.store = store

    async def process_task(self, task_data: dict) -> dict:
        """
        Processes task rollback using typed TaskModel to prevent state corruption.
        """
        # Validate data against schema
        task = TaskModel(**task_data)
        ctx = task.rollback_context
        
        # Reverse completed steps to undo in LIFO order
        reversed_steps = list(reversed(ctx.completed_steps))
        
        for step in reversed_steps:
            if step.id in ctx.undone_steps:
                continue
            
            # Execute rollback via registry
            result = await undo_registry.execute(step.action, task, step)
            
            # Handle failure with retry logic
            if not result.get("ok"):
                ctx.rollback_attempts += 1
                
                # Check if max retries reached, move to Dead Letter Queue (DLQ)
                if ctx.rollback_attempts >= 3:
                    task.status = "FAILED_DLQ"
                    ctx.error = result.get("error")
                    # Save serialized model to store
                    await self.store.set(task.model_dump())
                    return {"status": "DLQ_ENQUEUED"}
                
                # Save progress and retry later
                await self.store.set(task.model_dump())
                return {"status": "RETRYING"}
            
            # Success: mark step as undone and save progress
            ctx.undone_steps.append(step.id)
            await self.store.set(task.model_dump())
        
        return {"status": "SUCCESS"}
