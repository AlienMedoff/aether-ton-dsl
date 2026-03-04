import sys
sys.path.append('/content/ton-tx-dsl')

import pytest
import asyncio
from registry import undo_registry
from rollback_agent import RollbackAgent

# Test handler
@undo_registry.register("test_action")
async def undo_test_action(task, step):
    return {"ok": True, "value": "rollback_success"}

@pytest.mark.asyncio
async def test_registry_integration():
    # 1. Check registration
    assert "test_action" in undo_registry._handlers
    
    # 2. Check execution
    class MockTask:
        payload = {"completed_steps": [{"id": "1", "action": "test_action"}], "undone_steps": []}
        status = "IN_PROGRESS"
    
    class MockStore:
        async def set(self, task): pass
    
    agent = RollbackAgent(MockStore())
    result = await agent.process_task(MockTask())
    
    assert result["status"] == "SUCCESS"
    print("\n✅ Регистрация и выполнение отката работают.")

if __name__ == "__main__":
    asyncio.run(test_registry_integration())
