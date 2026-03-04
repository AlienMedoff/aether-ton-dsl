# models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class StepModel(BaseModel):
    """Represents an individual action step in the transaction workflow."""
    id: str
    action: str
    payload: Dict[str, Any] = {}

class RollbackContext(BaseModel):
    """Maintains state for rollback operations to ensure idempotency."""
    completed_steps: List[StepModel] = []
    undone_steps: List[str] = []
    rollback_attempts: int = 0
    error: Optional[str] = None

class TaskModel(BaseModel):
    """The unified task model separating business logic from orchestration state."""
    id: str
    status: str = "PROCESSING"
    # Business data independent of rollback logic
    execution_payload: Dict[str, Any]
    # State used specifically for orchestration and rollback
    rollback_context: RollbackContext = Field(default_factory=RollbackContext)
