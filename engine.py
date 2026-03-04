import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    CREATED     = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFYING   = "VERIFYING"
    COMPLETED   = "COMPLETED"
    FAILED      = "FAILED"


class Task(BaseModel):
    id:           str
    dependencies: Set[str]      = Field(default_factory=set)
    status:       TaskStatus    = TaskStatus.CREATED
    retries:      int           = 0
    max_retries:  int           = 3
    test_path:    Optional[str] = None
    payload:      dict          = Field(default_factory=dict)
    result:       dict          = Field(default_factory=dict)
    error:        str           = ""
    heartbeat_at: float         = Field(default_factory=time.monotonic)
    syscall_log:  list          = Field(default_factory=list)

    class Config:
        use_enum_values = False


class GatekeeperResult(BaseModel):
    passed:   bool
    output:   str
    duration: float


class SyscallError(Exception):
    pass


class SyscallResult(BaseModel):
    ok:    bool
    data:  Any = None
    error: str = ""


class BaseTaskStore(ABC):
    @abstractmethod
    async def get(self, task_id: str) -> Optional[Task]: ...
    @abstractmethod
    async def set(self, task: Task) -> None: ...
    @abstractmethod
    async def all(self) -> list[Task]: ...


class MemoryTaskStore(BaseTaskStore):
    def __init__(self):
        self._tasks: Dict[str, Task] = {}

    async def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def set(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def all(self) -> list[Task]:
        return list(self._tasks.values())


class SystemCallAPI:
    ALLOWED_TYPES = frozenset(["markdown", "json", "code", "report"])

    def __init__(self, task: Task, store: BaseTaskStore):
        self._task  = task
        self._store = store

    def _log(self, call: str) -> None:
        self._task.syscall_log.append({"call": call})

    async def read_task_payload(self) -> SyscallResult:
        self._log("read_task_payload")
        return SyscallResult(ok=True, data=self._task.payload)

    async def write_artifact(self, type: str, content: str) -> SyscallResult:
        if type not in self.ALLOWED_TYPES:
            r = SyscallResult(ok=False, error="Type not allowed")
        elif len(content.encode()) > 1_000_000:
            r = SyscallResult(ok=False, error="Content exceeds 1 MB limit")
        else:
            self._task.result["_staged"] = {"type": type, "content": content}
            r = SyscallResult(ok=True)
        self._log("write_artifact")
        return r

    async def read_artifact(self, source_task_id: str) -> SyscallResult:
        dep = await self._store.get(source_task_id)
        if not dep:
            r = SyscallResult(ok=False, error="Task not found")
        elif dep.status != TaskStatus.COMPLETED:
            r = SyscallResult(ok=False, error="Task not completed yet")
        else:
            r = SyscallResult(ok=True, data=dep.result)
        self._log("read_artifact")
        return r

    async def emit_event(self, event: str, payload: dict = None) -> SyscallResult:
        self._log("emit_event")
        return SyscallResult(ok=True)

    async def update_heartbeat(self) -> SyscallResult:
        self._task.heartbeat_at = time.monotonic()
        await self._store.set(self._task)
        self._log("update_heartbeat")
        return SyscallResult(ok=True)

    def open(self, *a, **kw):
        raise SyscallError("forbidden")

    def __getattr__(self, name: str):
        raise SyscallError(f"Syscall {name!r} is not defined")


class AgentRunner(ABC):
    @abstractmethod
    async def run(self, task: Task, syscall: SystemCallAPI) -> dict: ...


class MockAgentRunner(AgentRunner):
    async def run(self, task: Task, syscall: SystemCallAPI) -> dict:
        await syscall.read_task_payload()
        await syscall.write_artifact("json", json.dumps({"output": f"mock_{task.id}"}))
        await syscall.emit_event("done", {"task_id": task.id})
        return {"output": "ok"}


class SecurityFilter:
    FORBIDDEN = ["rm -rf", "DROP TABLE", "os.system", "eval("]

    def validate(self, task: Task) -> tuple[bool, str]:
        content = task.result.get("_staged", {}).get("content", "")
        for p in self.FORBIDDEN:
            if p in content:
                return False, f"Forbidden pattern detected: {p!r}"
        if len(content.encode()) > 1_000_000:
            return False, "Result exceeds 1 MB limit"
        return True, ""

    def commit(self, task: Task) -> None:
        staged = task.result.pop("_staged", {})
        task.result["artifact"]     = staged
        task.result["committed_at"] = time.time()


class Gatekeeper:
    async def verify(self, task: Task) -> GatekeeperResult:
        return GatekeeperResult(passed=True, output="ok", duration=0.0)


class Reaper:
    def __init__(self, store: BaseTaskStore, stale_threshold: float = 600.0):
        self.store           = store
        self.stale_threshold = stale_threshold

    async def _sweep(self) -> None:
        for task in await self.store.all():
            if task.status != TaskStatus.IN_PROGRESS:
                continue
            if (time.monotonic() - task.heartbeat_at) <= self.stale_threshold:
                continue
            if task.retries >= task.max_retries:
                task.status = TaskStatus.FAILED
                task.error  = "Reaped: no heartbeat"
            else:
                task.status   = TaskStatus.CREATED
                task.retries += 1
            await self.store.set(task)


class DAGOrchestrator:
    def __init__(
        self,
        agent:           AgentRunner,
        store:           BaseTaskStore,
        gatekeeper:      Gatekeeper,
        security_filter: SecurityFilter,
        reaper:          Reaper,
    ):
        self.agent           = agent
        self.store           = store
        self.gatekeeper      = gatekeeper
        self.security_filter = security_filter
        self.reaper          = reaper
        self._events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def add_task(self, task: Task) -> None:
        self._events[task.id] = asyncio.Event()
        await self.store.set(task)

    async def start(self) -> None:
        await self._run_dag()

    async def _run_dag(self) -> None:
        while True:
            tasks = await self.store.all()

            still_active = [
                t for t in tasks
                if t.status in (TaskStatus.CREATED, TaskStatus.IN_PROGRESS, TaskStatus.VERIFYING)
            ]
            if not still_active:
                break

            dispatched = await self._dispatch_ready(tasks)

            if not dispatched:
                in_flight = [
                    t.id for t in tasks
                    if t.status in (TaskStatus.IN_PROGRESS, TaskStatus.VERIFYING)
                ]
                if in_flight:
                    await self._wait_for_any(in_flight)
                else:
                    break

    async def _wait_for_any(self, task_ids: list[str]) -> None:
        futures = [
            asyncio.ensure_future(self._events[tid].wait())
            for tid in task_ids
            if tid in self._events
        ]
        if not futures:
            return
        done, pending = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)
        for f in pending:
            f.cancel()

    async def _dispatch_ready(self, tasks: list[Task]) -> bool:
        completed: Set[str] = {t.id for t in tasks if t.status == TaskStatus.COMPLETED}
        ready = []

        async with self._lock:
            for task in tasks:
                if task.status != TaskStatus.CREATED:
                    continue
                if not task.dependencies.issubset(completed):
                    continue
                task.status       = TaskStatus.IN_PROGRESS
                task.heartbeat_at = time.monotonic()
                await self.store.set(task)
                ready.append(task)

        if not ready:
            return False

        for task in ready:
            asyncio.create_task(self._execute(task))
        return True

    async def _execute(self, task: Task) -> None:
        syscall = SystemCallAPI(task, self.store)

        for attempt in range(task.max_retries + 1):
            if attempt > 0:
                await asyncio.sleep(2.0 * attempt)

            try:
                g = await self.gatekeeper.verify(task)
                if not g.passed:
                    raise Exception(f"Gatekeeper failed: {g.output}")

                await self.agent.run(task, syscall)

                ok, err = self.security_filter.validate(task)
                if not ok:
                    raise Exception(err)
                self.security_filter.commit(task)

                async with self._lock:
                    task.status  = TaskStatus.COMPLETED
                    task.retries = attempt
                    await self.store.set(task)

                self._events[task.id].set()
                return

            except Exception as e:
                task.error = str(e)

                if attempt >= task.max_retries:
                    async with self._lock:
                        task.status  = TaskStatus.FAILED
                        task.retries = attempt
                        await self.store.set(task)
                    self._events[task.id].set()
                    return
                else:
                    async with self._lock:
                        task.status  = TaskStatus.CREATED
                        task.retries = attempt
                        await self.store.set(task)
                    # Будим старый waiter, подменяем event для следующего цикла
                    old_event = self._events[task.id]
                    self._events[task.id] = asyncio.Event()
                    old_event.set()
