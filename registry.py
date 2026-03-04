# registry.py
from typing import Callable, Awaitable, Dict, Any

class UndoRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Any, Any], Awaitable[Dict]]] = {}

    def register(self, action_type: str):
        def decorator(func: Callable[[Any, Any], Awaitable[Dict]]):
            self._handlers[action_type] = func
            return func
        return decorator

    async def execute(self, action_type: str, task: Any, step: Any) -> Dict:
        if action_type not in self._handlers:
            return {"ok": False, "error": f"Missing handler for {action_type}"}
        return await self._handlers[action_type](task, step)

# Global registry instance
undo_registry = UndoRegistry()
