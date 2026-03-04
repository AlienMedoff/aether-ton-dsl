"""
orchestrator/scenario_runner.py — Scenario FSM

Fixes vs original sketch:
  - Timeout on brpop (not infinite wait)
  - Skips ACKs for other task_ids (not just discard them)
  - rollback publishes to RollbackAgent queue with full history
  - Session context written via AgentContextManager
"""

import json
import logging
import uuid
from typing import Optional

import redis

from common.config import Config, TonMode
from common.agent_context_manager import AgentContextManager, MemoryContextManager

logger = logging.getLogger(__name__)

ACK_TIMEOUT    = 10   # seconds to wait for agent ACK
MAX_ACK_MISSES = 20   # discard at most 20 wrong ACKs before giving up


class ScenarioRunner:

    def __init__(self, config: Optional[Config] = None):
        self.cfg        = config or Config.load()
        self.session_id = str(uuid.uuid4())

        if self.cfg.ton_mode == TonMode.MOCK:
            self.r  = None
            self.cm = MemoryContextManager(self.session_id)
        else:
            self.r  = redis.Redis(host=self.cfg.redis_host,
                                   port=self.cfg.redis_port,
                                   decode_responses=True)
            self.cm = AgentContextManager(self.r, self.session_id)

    def run_feature(self, steps: list) -> bool:
        self.cm.set("status", "RUNNING")
        completed = []

        for step in steps:
            tid    = str(uuid.uuid4())
            result = self._dispatch(tid, step)

            if result.get("status") == "SUCCESS":
                completed.append(step)
                self.cm.append_history({"step": step["text"], "result": result})
            else:
                logger.warning(f"Step failed: {step['text']} → {result}")
                self.cm.set("status", "FAILED")
                self._trigger_rollback(step, completed)
                return False

        self.cm.set("status", "COMPLETED")
        return True

    def _dispatch(self, tid: str, step: dict) -> dict:
        """Push task to agent queue and wait for ACK."""
        if self.cfg.ton_mode == TonMode.MOCK:
            # In MOCK mode — run synchronously without Redis
            return self._mock_execute(step["payload"])

        task = {"task_id": tid, "session_id": self.session_id,
                "payload": step["payload"]}
        self.r.lpush(f"queue:tasks:{step['agent']}", json.dumps(task))

        # Wait for matching ACK (skip ACKs for other tasks)
        for _ in range(MAX_ACK_MISSES):
            item = self.r.brpop("queue:acks", timeout=ACK_TIMEOUT)
            if not item:
                logger.error(f"ACK timeout for task {tid}")
                return {"status": "FAILED", "reason": "ACK timeout"}
            _, ack_json = item
            ack = json.loads(ack_json)
            if ack["task_id"] == tid:
                return ack["result"]
            # Wrong task_id — put back and retry
            self.r.lpush("queue:acks", ack_json)

        return {"status": "FAILED", "reason": "Too many ACK misses"}

    def _mock_execute(self, payload: dict) -> dict:
        """Synchronous mock execution — no Redis needed."""
        action = payload.get("action")
        amount = int(payload.get("amount", 0))

        if action == "check":
            balance = self.cm.get("balance", 0)
            ok = balance >= amount
            return {"status": "SUCCESS" if ok else "FAILED", "balance": balance}

        if action == "send_transaction":
            balance   = self.cm.get("balance", 0)
            recipient = payload.get("recipient", "")
            if balance < amount:
                return {"status": "FAILED", "reason": "insufficient balance"}
            self.cm.set("balance", balance - amount)
            return {"status": "SUCCESS", "new_balance": balance - amount, "to": recipient}

        if action == "verify":
            balance = self.cm.get("balance", 0)
            ok = balance == amount
            return {"status": "SUCCESS" if ok else "FAILED",
                    "balance": balance, "expected": amount}

        return {"status": "FAILED", "reason": f"Unknown action: {action}"}

    def _trigger_rollback(self, failed_step: dict, completed_steps: list) -> None:
        if not completed_steps:
            return
        if self.cfg.ton_mode == TonMode.MOCK:
            logger.info(f"[MOCK Rollback] Would undo {len(completed_steps)} step(s)")
            return
        payload = {"action": "rollback", "failed_step": failed_step["text"],
                   "completed_steps": completed_steps}
        tid  = str(uuid.uuid4())
        task = {"task_id": tid, "session_id": self.session_id, "payload": payload}
        self.r.lpush("queue:tasks:RollbackAgent", json.dumps(task))
        logger.info(f"Rollback triggered for {len(completed_steps)} step(s)")
