"""
tests/test_engine.py — Full test suite for Production OS Core v2

Run: pytest tests/test_engine.py -v
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch

from engine import (
    DAGOrchestrator, Task, TaskStatus,
    MemoryTaskStore, AgentRunner, MockAgentRunner,
    Gatekeeper, GatekeeperResult, Reaper,
    SecurityFilter, SystemCallAPI, SyscallError, SyscallResult,
)


# ============================================================
# HELPERS
# ============================================================

def task(id: str, deps: set = None, max_retries: int = 3, test_path: str = None) -> Task:
    return Task(id=id, dependencies=deps or set(), max_retries=max_retries, test_path=test_path)


class PassGatekeeper(Gatekeeper):
    async def verify(self, task: Task) -> GatekeeperResult:
        return GatekeeperResult(passed=True, output="ok", duration=0.0)


class FailGatekeeper(Gatekeeper):
    async def verify(self, task: Task) -> GatekeeperResult:
        return GatekeeperResult(passed=False, output="tests failed", duration=0.0)


class FailNTimesAgent(AgentRunner):
    def __init__(self, n: int):
        self.n = n
        self.calls = 0

    async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
        self.calls += 1
        if self.calls <= self.n:
            raise RuntimeError(f"Intentional failure #{self.calls}")
        await syscall.write_artifact("json", '{"ok": true}')
        return {"output": "recovered"}


def make_orch(agent=None, gatekeeper=None, security_filter=None) -> DAGOrchestrator:
    return DAGOrchestrator(
        agent=agent or MockAgentRunner(),
        store=MemoryTaskStore(),
        gatekeeper=gatekeeper or PassGatekeeper(),
        security_filter=security_filter or SecurityFilter(),
        reaper=Reaper(MemoryTaskStore(), stale_threshold=9999),  # Disabled in tests
    )


# ============================================================
# 1. BASIC EXECUTION
# ============================================================

class TestBasicExecution:

    @pytest.mark.asyncio
    async def test_single_task_completes(self):
        orch = make_orch()
        await orch.add_task(task("t1"))
        await orch.start()
        t = await orch.store.get("t1")
        assert t.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_result_written(self):
        orch = make_orch()
        await orch.add_task(task("t1"))
        await orch.start()
        t = await orch.store.get("t1")
        assert "artifact" in t.result
        assert t.result["artifact"]["type"] == "json"

    @pytest.mark.asyncio
    async def test_five_independent_tasks_all_complete(self):
        orch = make_orch()
        for i in range(5):
            await orch.add_task(task(f"t{i}"))
        await orch.start()
        for t in await orch.store.all():
            assert t.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_syscall_log_populated(self):
        orch = make_orch()
        await orch.add_task(task("t1"))
        await orch.start()
        t = await orch.store.get("t1")
        calls = [e["call"] for e in t.syscall_log]
        assert "read_task_payload" in calls
        assert "write_artifact" in calls
        assert "emit_event" in calls


# ============================================================
# 2. DEPENDENCY RESOLUTION
# ============================================================

class TestDependencies:

    @pytest.mark.asyncio
    async def test_child_runs_after_parent(self):
        order = []

        class OrderAgent(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                order.append(t.id)
                await syscall.write_artifact("json", "{}")
                return {}

        orch = make_orch(agent=OrderAgent())
        await orch.add_task(task("parent"))
        await orch.add_task(task("child", deps={"parent"}))
        await orch.start()
        assert order.index("parent") < order.index("child")

    @pytest.mark.asyncio
    async def test_chain_a_b_c(self):
        order = []

        class OA(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                order.append(t.id)
                await syscall.write_artifact("json", "{}")
                return {}

        orch = make_orch(agent=OA())
        await orch.add_task(task("a"))
        await orch.add_task(task("b", deps={"a"}))
        await orch.add_task(task("c", deps={"b"}))
        await orch.start()
        assert order == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_fan_in(self):
        orch = make_orch()
        await orch.add_task(task("a"))
        await orch.add_task(task("b"))
        await orch.add_task(task("merge", deps={"a", "b"}))
        await orch.start()
        merge = await orch.store.get("merge")
        assert merge.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_read_artifact_from_dependency(self):
        """Child reads parent artifact via read_artifact syscall."""
        class ProducerAgent(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                await syscall.write_artifact("json", '{"value": 42}')
                return {"value": 42}

        class ConsumerAgent(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                r = await syscall.read_artifact("parent")
                assert r.ok
                await syscall.write_artifact("json", '{"consumed": true}')
                return {}

        class RouterAgent(AgentRunner):
            def __init__(self):
                self.producer = ProducerAgent()
                self.consumer = ConsumerAgent()

            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                if t.id == "parent":
                    return await self.producer.run(t, syscall)
                return await self.consumer.run(t, syscall)

        orch = make_orch(agent=RouterAgent())
        await orch.add_task(task("parent"))
        await orch.add_task(task("child", deps={"parent"}))
        await orch.start()

        child = await orch.store.get("child")
        assert child.status == TaskStatus.COMPLETED


# ============================================================
# 3. RETRY + EXPONENTIAL BACKOFF
# ============================================================

class TestRetries:

    @pytest.mark.asyncio
    async def test_succeeds_after_one_retry(self):
        agent = FailNTimesAgent(n=1)
        orch  = make_orch(agent=agent)
        t1    = task("t1", max_retries=3)
        await orch.add_task(t1)
        with patch("engine.asyncio.sleep", new_callable=AsyncMock):
            await orch.start()
        saved = await orch.store.get("t1")
        assert saved.status == TaskStatus.COMPLETED
        assert saved.retries == 1
        assert agent.calls == 2

    @pytest.mark.asyncio
    async def test_fails_after_exhausting_retries(self):
        agent = FailNTimesAgent(n=99)
        t1    = task("t1", max_retries=2)
        orch  = make_orch(agent=agent)
        await orch.add_task(t1)
        with patch("engine.asyncio.sleep", new_callable=AsyncMock):
            await orch.start()
        saved = await orch.store.get("t1")
        assert saved.status == TaskStatus.FAILED
        assert agent.calls == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_error_stored_on_failure(self):
        class BoomAgent(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                raise ValueError("boom!")

        t1   = task("t1", max_retries=0)
        orch = make_orch(agent=BoomAgent())
        await orch.add_task(t1)
        await orch.start()
        saved = await orch.store.get("t1")
        assert "boom!" in saved.error

    @pytest.mark.asyncio
    async def test_gatekeeper_failure_triggers_retry(self):
        t1   = task("t1", max_retries=1)
        orch = make_orch(gatekeeper=FailGatekeeper())
        await orch.add_task(t1)
        with patch("engine.asyncio.sleep", new_callable=AsyncMock):
            await orch.start()
        saved = await orch.store.get("t1")
        assert saved.status == TaskStatus.FAILED


# ============================================================
# 4. SYSCALL PROTOCOL
# ============================================================

class TestSyscallProtocol:

    def make_syscall(self, task_id: str = "t1") -> tuple[Task, SystemCallAPI]:
        t     = Task(id=task_id, payload={"key": "value"})
        store = MemoryTaskStore()
        sc    = SystemCallAPI(t, store)
        return t, sc

    @pytest.mark.asyncio
    async def test_read_payload_returns_payload(self):
        t, sc = self.make_syscall()
        r = await sc.read_task_payload()
        assert r.ok
        assert r.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_write_valid_artifact_staged(self):
        t, sc = self.make_syscall()
        r = await sc.write_artifact("json", '{"x": 1}')
        assert r.ok
        assert t.result["_staged"]["type"] == "json"

    @pytest.mark.asyncio
    async def test_write_invalid_type_rejected(self):
        t, sc = self.make_syscall()
        r = await sc.write_artifact("exe", "malware")
        assert not r.ok
        assert "not allowed" in r.error

    @pytest.mark.asyncio
    async def test_write_oversized_artifact_rejected(self):
        t, sc = self.make_syscall()
        big   = "x" * 1_100_000  # 1.1 MB
        r     = await sc.write_artifact("json", big)
        assert not r.ok
        assert "1 MB" in r.error

    @pytest.mark.asyncio
    async def test_read_artifact_from_not_completed_task(self):
        store = MemoryTaskStore()
        dep   = Task(id="dep", status=TaskStatus.IN_PROGRESS)
        await store.set(dep)
        t  = Task(id="t1")
        sc = SystemCallAPI(t, store)
        r  = await sc.read_artifact("dep")
        assert not r.ok
        assert "not completed" in r.error

    @pytest.mark.asyncio
    async def test_read_artifact_not_found(self):
        t, sc = self.make_syscall()
        r = await sc.read_artifact("nonexistent")
        assert not r.ok
        assert "not found" in r.error

    @pytest.mark.asyncio
    async def test_forbidden_open_raises(self):
        t, sc = self.make_syscall()
        with pytest.raises(SyscallError, match="forbidden"):
            sc.open("file.txt", "w")

    @pytest.mark.asyncio
    async def test_undefined_syscall_raises(self):
        t, sc = self.make_syscall()
        with pytest.raises(SyscallError, match="not defined"):
            _ = sc.delete_everything

    @pytest.mark.asyncio
    async def test_every_call_logged(self):
        t, sc = self.make_syscall()
        await sc.read_task_payload()
        await sc.write_artifact("json", "{}")
        await sc.emit_event("done", {})
        calls = [e["call"] for e in t.syscall_log]
        assert calls == ["read_task_payload", "write_artifact", "emit_event"]

    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(self):
        store = MemoryTaskStore()
        t     = Task(id="t1")
        old_hb = t.heartbeat_at
        await asyncio.sleep(0.01)
        sc    = SystemCallAPI(t, store)
        await sc.update_heartbeat()
        assert t.heartbeat_at > old_hb


# ============================================================
# 5. SECURITY FILTER
# ============================================================

class TestSecurityFilter:

    def make_task_with_staged(self, content: str, type_: str = "json") -> Task:
        t = Task(id="t1")
        t.result["_staged"] = {"type": type_, "content": content}
        return t

    def test_clean_content_passes(self):
        sf = SecurityFilter()
        t  = self.make_task_with_staged('{"hello": "world"}')
        ok, reason = sf.validate(t)
        assert ok

    def test_forbidden_pattern_rejected(self):
        sf = SecurityFilter()
        for pattern in ["rm -rf", "DROP TABLE", "os.system", "eval("]:
            t = self.make_task_with_staged(f"some text with {pattern} inside")
            ok, reason = sf.validate(t)
            assert not ok, f"Expected rejection for pattern {pattern!r}"
            assert pattern in reason

    def test_oversized_content_rejected(self):
        sf = SecurityFilter()
        t  = self.make_task_with_staged("x" * 1_100_000)
        ok, reason = sf.validate(t)
        assert not ok
        assert "1 MB" in reason

    def test_commit_moves_staged_to_artifact(self):
        sf = SecurityFilter()
        t  = self.make_task_with_staged('{"ok": true}')
        sf.commit(t)
        assert "_staged" not in t.result
        assert "artifact" in t.result
        assert t.result["artifact"]["content"] == '{"ok": true}'
        assert "committed_at" in t.result


# ============================================================
# 6. REAPER
# ============================================================

class TestReaper:

    @pytest.mark.asyncio
    async def test_reaper_requeues_stale_task(self):
        store = MemoryTaskStore()
        t     = Task(id="t1", status=TaskStatus.IN_PROGRESS, max_retries=3)
        t.heartbeat_at = time.monotonic() - 700  # 700s ago — stale
        await store.set(t)

        reaper = Reaper(store, stale_threshold=600)
        await reaper._sweep()

        updated = await store.get("t1")
        assert updated.status == TaskStatus.CREATED
        assert updated.retries == 1

    @pytest.mark.asyncio
    async def test_reaper_fails_exhausted_task(self):
        store = MemoryTaskStore()
        t     = Task(id="t1", status=TaskStatus.IN_PROGRESS, max_retries=2, retries=2)
        t.heartbeat_at = time.monotonic() - 700
        await store.set(t)

        reaper = Reaper(store, stale_threshold=600)
        await reaper._sweep()

        updated = await store.get("t1")
        assert updated.status == TaskStatus.FAILED
        assert "Reaped" in updated.error

    @pytest.mark.asyncio
    async def test_reaper_ignores_fresh_tasks(self):
        store = MemoryTaskStore()
        t     = Task(id="t1", status=TaskStatus.IN_PROGRESS)
        t.heartbeat_at = time.monotonic()  # Just updated
        await store.set(t)

        reaper = Reaper(store, stale_threshold=600)
        await reaper._sweep()

        updated = await store.get("t1")
        assert updated.status == TaskStatus.IN_PROGRESS  # Unchanged

    @pytest.mark.asyncio
    async def test_reaper_ignores_completed_tasks(self):
        store = MemoryTaskStore()
        t     = Task(id="t1", status=TaskStatus.COMPLETED)
        t.heartbeat_at = time.monotonic() - 9999  # Very old but COMPLETED
        await store.set(t)

        reaper = Reaper(store, stale_threshold=60)
        await reaper._sweep()

        updated = await store.get("t1")
        assert updated.status == TaskStatus.COMPLETED


# ============================================================
# 7. EVENT-DRIVEN DISPATCH
# ============================================================

class TestEventDriven:

    @pytest.mark.asyncio
    async def test_tasks_run_in_parallel(self):
        """5 independent tasks each sleeping 0.1s → ~0.1s total, not 0.5s."""
        class SlowAgent(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                await asyncio.sleep(0.1)
                await syscall.write_artifact("json", "{}")
                return {}

        orch = make_orch(agent=SlowAgent())
        for i in range(5):
            await orch.add_task(task(f"t{i}"))

        start   = time.monotonic()
        await orch.start()
        elapsed = time.monotonic() - start

        assert elapsed < 0.4, f"Ran sequentially ({elapsed:.2f}s) — parallel expected"

    @pytest.mark.asyncio
    async def test_no_double_dispatch(self):
        call_counts: dict = {}

        class CountAgent(AgentRunner):
            async def run(self, t: Task, syscall: SystemCallAPI) -> dict:
                call_counts[t.id] = call_counts.get(t.id, 0) + 1
                await syscall.write_artifact("json", "{}")
                return {}

        orch = make_orch(agent=CountAgent())
        await orch.add_task(task("t1"))
        await orch.start()
        assert call_counts["t1"] == 1

    @pytest.mark.asyncio
    async def test_completion_event_fires(self):
        """Event for task fires immediately after completion."""
        orch = make_orch()
        await orch.add_task(task("t1"))

        event = orch._events["t1"]
        assert not event.is_set()

        await orch.start()
        assert event.is_set()
