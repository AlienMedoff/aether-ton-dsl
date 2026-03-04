"""
main.py — Aether OS entry point

Wires all components and uses Redis for persistent task state.
"""

import asyncio
import logging
import os
from engine import (
    DAGOrchestrator, Task, TaskStatus,
    MockAgentRunner,
    MemoryTaskStore,
    Reaper,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

async def main():
    # ── Agent Setup ──────────────────────────────────────────────
    # Используем MockAgentRunner для тестирования
    agent = MockAgentRunner()

    # ── Store Setup (Memory Persistence для теста) ────────────────────
    # Используем MemoryTaskStore для простого тестирования
    store = MemoryTaskStore()
    
    logging.info("Using MemoryTaskStore for testing")

    # ── Orchestrator ─────────────────────────────────────────────
    # Reaper следит за зависшими задачами (stale_threshold=600 сек)
    from engine import Gatekeeper, SecurityFilter
    orch = DAGOrchestrator(
        agent=agent,
        store=store,
        gatekeeper=Gatekeeper(),
        security_filter=SecurityFilter(),
        reaper=Reaper(store, stale_threshold=600),
    )

    # ── Define DAG (Workflow) ────────────────────────────────────
    #   fetch_data ─┐
    #               ├─► process ─► validate ─► report
    #   fetch_meta ─┘

    await orch.add_task(Task(id="fetch_data",  payload={"source": "toncenter"}))
    await orch.add_task(Task(id="fetch_meta",  payload={"source": "ipfs"}))
    await orch.add_task(Task(id="process",     dependencies={"fetch_data", "fetch_meta"},
                              payload={"op": "merge"}))
    await orch.add_task(Task(id="validate",    dependencies={"process"}))
    await orch.add_task(Task(id="report",      dependencies={"validate"},
                              payload={"format": "markdown"}))

    # ── Start Engine ─────────────────────────────────────────────
    await orch.start()

    # ── Final Status Report ──────────────────────────────────────
    tasks = await store.all()
    print("\n" + "=" * 40)
    print("  Aether OS — Execution Report")
    print("=" * 40)
    for task in tasks:
        icon = "[OK]" if task.status == TaskStatus.COMPLETED else "[FAIL]"
        print(f"  {icon}  {task.id:15s} {task.status}")
        if task.error:
            print(f"      └─ {task.error[:80]}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Aether OS shutdown requested.")

