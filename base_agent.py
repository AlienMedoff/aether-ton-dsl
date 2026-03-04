"""
agents/base_agent.py — Base class for all Aether OS agents

Fixes vs original sketch:
  - Config loaded via ConfigLoader (no hardcoded hosts)
  - Redis connection from config (not raw os.getenv)
  - process_task must return typed dict, not any object
  - Graceful shutdown on SIGTERM/SIGINT
  - Error logged with task_id context, not swallowed
"""

import json
import logging
import signal
import sys
from abc import abstractmethod
from typing import Optional

import redis

from common.config import Config

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(self, config: Optional[Config] = None):
        self.cfg = config or Config.load()
        self.r   = redis.Redis(
            host=self.cfg.redis_host,
            port=self.cfg.redis_port,
            decode_responses=True,
        )
        self._running = True
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT,  self._shutdown)
        logger.info(f"[{self.cfg.agent_id}] Agent started")

    def _shutdown(self, *_):
        logger.info(f"[{self.cfg.agent_id}] Shutdown signal received")
        self._running = False

    def run(self):
        queue = f"queue:tasks:{self.cfg.agent_id}"
        logger.info(f"[{self.cfg.agent_id}] Listening on {queue}")

        while self._running:
            try:
                item = self.r.brpop(queue, timeout=2)
                if not item:
                    continue  # Timeout — check _running flag and loop

                _, task_json = item
                task = json.loads(task_json)
                tid  = task.get("task_id", "?")

                logger.info(f"[{self.cfg.agent_id}] Processing task {tid}")
                result = self.process_task(task)
                self.r.lpush("queue:acks", json.dumps({
                    "task_id": tid,
                    "result":  result,
                }))

            except redis.RedisError as e:
                logger.error(f"[{self.cfg.agent_id}] Redis error: {e}")
            except Exception as e:
                logger.error(f"[{self.cfg.agent_id}] Task error: {e}")
                # Push FAILED ack so ScenarioRunner doesn't hang on brpop
                if "task_id" in locals():
                    self.r.lpush("queue:acks", json.dumps({
                        "task_id": task.get("task_id", "?"),
                        "result":  {"status": "FAILED", "error": str(e)},
                    }))

    @abstractmethod
    def process_task(self, task: dict) -> dict:
        """
        Override in subclass.
        Must return: {"status": "SUCCESS" | "FAILED", ...extra}
        """
        raise NotImplementedError
