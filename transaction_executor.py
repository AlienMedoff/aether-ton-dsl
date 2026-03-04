"""
agents/transaction_executor.py — Mock TON Transaction Agent

In MOCK mode: simulates transactions without real network calls.
In TESTNET/MAINNET mode: calls real TON API via TonService.

Run: python -m agents.transaction_executor
"""

import logging
import os

from agents.base_agent import BaseAgent
from common.config import Config, TonMode

logger = logging.getLogger(__name__)


class TransactionExecutorAgent(BaseAgent):

    def process_task(self, task: dict) -> dict:
        payload = task.get("payload", {})
        action  = payload.get("action")

        if action == "send_transaction":
            return self._send(payload)

        return {"status": "FAILED", "reason": f"Unknown action: {action!r}"}

    def _send(self, payload: dict) -> dict:
        amount    = int(payload.get("amount", 0))
        recipient = payload.get("recipient", "")

        if self.cfg.ton_mode == TonMode.MOCK:
            logger.info(f"[MOCK] Sending {amount} TON to {recipient}")
            return {
                "status": "SUCCESS",
                "tx_hash": f"mock_tx_{amount}_{recipient}",
                "amount":  amount,
                "to":      recipient,
            }

        # TESTNET / MAINNET — use real TonService
        from common.ton_service import TONService
        import asyncio

        svc    = TONService()
        wallet = self.cfg.wallet_address or payload.get("wallet_address")
        if not wallet:
            return {"status": "FAILED", "reason": "wallet_address not set"}

        # Real implementation would call svc.send_transaction(...)
        # Kept as stub until on-chain integration is ready
        return {"status": "FAILED", "reason": "Real send not yet implemented — use MOCK mode"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    TransactionExecutorAgent().run()
