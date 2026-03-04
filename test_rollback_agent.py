import pytest
from unittest.mock import AsyncMock
from rollback_agent import RollbackAgent
from registry import undo_registry

@pytest.mark.asyncio
async def test_rollback_agent_dlq_after_3_attempts():
    # Mocking storage
    store = AsyncMock()
    agent = RollbackAgent(store)
    
    # Mocking registry
    undo_registry.execute = AsyncMock(return_value={"ok": False, "error": "Fail"})
    
    # Data dictionary directly matching TaskModel schema
    task_data = {
        "id": "task_123",
        "status": "PROCESSING",
        "execution_payload": {"amount": 100},
        "rollback_context": {
            "completed_steps": [{"id": "1", "action": "send_transaction", "payload": {}}],
            "undone_steps": [],
            "rollback_attempts": 2  # This will become 3 in process_task
        }
    }
    
    # Process
    result = await agent.process_task(task_data)
    
    # Assert
    assert result["status"] == "DLQ_ENQUEUED"
    assert store.set.called # Ensure store was updated
