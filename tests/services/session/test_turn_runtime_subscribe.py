from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path

import pytest

from deeptutor.core.stream import StreamEvent, StreamEventType
from deeptutor.multi_user.context import reset_current_user, set_current_user
from deeptutor.multi_user.models import CurrentUser, UserScope
from deeptutor.services.session.pocketbase_store import PocketBaseSessionStore
from deeptutor.services.session.sqlite_store import SQLiteSessionStore
from deeptutor.services.session.turn_runtime import (
    TurnRuntimeManager,
    _resolve_turn_outcome,
    _TurnExecution,
)


def test_terminal_error_marks_turn_failed() -> None:
    error_message = "provider authentication failed"
    status, error = _resolve_turn_outcome(
        [
            {
                "type": "error",
                "content": error_message,
                "metadata": {"turn_terminal": True, "status": "failed"},
            }
        ],
        StreamEvent(
            type=StreamEventType.DONE,
            source="chat",
            metadata={"status": "failed"},
        ),
    )

    assert status == "failed"
    assert error == error_message


def test_non_terminal_error_keeps_completed_done_status() -> None:
    status, error = _resolve_turn_outcome(
        [
            {
                "type": "error",
                "content": "recoverable tool error",
                "metadata": {},
            }
        ],
        StreamEvent(
            type=StreamEventType.DONE,
            source="chat",
            metadata={"status": "completed"},
        ),
    )

    assert status == "completed"
    assert error == ""


@pytest.mark.asyncio
async def test_subscribe_turn_does_not_synthesize_done_for_running_turn(tmp_path) -> None:
    """A paused/replaced subscription must not make the UI think the turn ended."""

    store = SQLiteSessionStore(tmp_path / "chat_history.db")
    runtime = TurnRuntimeManager(store)
    session = await store.ensure_session(None)
    turn = await store.create_turn(session["id"], capability="chat")
    execution = _TurnExecution(
        turn_id=turn["id"],
        session_id=session["id"],
        capability="chat",
        payload={},
    )
    runtime._executions[turn["id"]] = execution

    events: list[dict] = []

    async def _collect() -> None:
        async for event in runtime.subscribe_turn(turn["id"], after_seq=0):
            events.append(event)

    task = asyncio.create_task(_collect())
    for _ in range(200):
        if execution.subscribers:
            break
        await asyncio.sleep(0.01)

    assert execution.subscribers
    await execution.subscribers[0].queue.put(None)
    await asyncio.wait_for(task, timeout=1)

    assert events == []
    persisted = await store.get_turn(turn["id"])
    assert persisted is not None
    assert persisted["status"] == "running"


@pytest.mark.asyncio
async def test_subscribe_turn_marks_orphan_running_turn_failed(tmp_path) -> None:
    """A DB-running turn with no in-process execution is stale after restart."""

    store = SQLiteSessionStore(tmp_path / "chat_history.db")
    runtime = TurnRuntimeManager(store)
    session = await store.ensure_session(None)
    turn = await store.create_turn(session["id"], capability="chat")

    events: list[dict] = []
    async for event in runtime.subscribe_turn(turn["id"], after_seq=0):
        events.append(event)

    persisted = await store.get_turn(turn["id"])
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert "restart" in persisted["error"].lower()
    assert [event["type"] for event in events] == ["error", "done"]
    assert events[-1]["metadata"]["status"] == "failed"


@pytest.mark.asyncio
async def test_start_turn_clears_orphan_running_turn_before_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A stale active turn should not block the next user message after restart."""

    store = SQLiteSessionStore(tmp_path / "chat_history.db")
    runtime = TurnRuntimeManager(store)
    session = await store.ensure_session(None)
    stale = await store.create_turn(session["id"], capability="chat")

    async def _noop_run_turn(_execution):
        return None

    monkeypatch.setattr(runtime, "_run_turn", _noop_run_turn)

    _, new_turn = await runtime.start_turn(
        {
            "type": "start_turn",
            "session_id": session["id"],
            "capability": "chat",
            "content": "hello",
            "tools": [],
            "knowledge_bases": [],
            "attachments": [],
            "language": "en",
            "config": {},
        }
    )

    assert new_turn["id"] != stale["id"]
    persisted = await store.get_turn(stale["id"])
    assert persisted is not None
    assert persisted["status"] == "failed"


# ---------------------------------------------------------------------------
# Session-level subscription (passive cross-terminal sync)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_session_lives_across_turns(tmp_path) -> None:
    """A session subscription outlives individual turns: it must survive the
    turn-end sentinel and keep delivering the next turn's events (including
    per-turn seq numbers that restart at 1)."""

    store = SQLiteSessionStore(tmp_path / "chat_history.db")
    runtime = TurnRuntimeManager(store)
    session = await store.ensure_session(None)
    sid = session["id"]

    received: list[dict] = []

    async def _collect() -> None:
        async for event in runtime.subscribe_session(sid, after_seq=0):
            received.append(event)

    task = asyncio.create_task(_collect())
    for _ in range(200):
        if runtime._session_subscribers.get(sid):
            break
        await asyncio.sleep(0.01)
    assert runtime._session_subscribers.get(sid), "subscription must register"

    # No active turn: the subscription stays alive but delivers nothing.
    await asyncio.sleep(0.05)
    assert received == []

    # Turn 1 runs and finishes; the subscriber sees its events.
    turn1 = await store.create_turn(sid, capability="chat")
    execution1 = _TurnExecution(
        turn_id=turn1["id"], session_id=sid, capability="chat", payload={}
    )
    runtime._executions[turn1["id"]] = execution1
    await runtime._publish_live_event(
        execution1,
        StreamEvent(
            type=StreamEventType.SESSION,
            source="turn_runtime",
            metadata={"session_id": sid, "turn_id": turn1["id"]},
        ),
    )
    await runtime._publish_live_event(
        execution1,
        StreamEvent(
            type=StreamEventType.DONE,
            source="chat",
            metadata={"status": "completed"},
        ),
    )
    await store.update_turn_status(turn1["id"], "completed")
    runtime._executions.pop(turn1["id"], None)
    for _ in range(200):
        if len(received) >= 2:
            break
        await asyncio.sleep(0.01)
    assert [event["type"] for event in received] == ["session", "done"]

    # Turn 2 starts on the same session: the same subscription still
    # receives it (no None sentinel ended the subscription at turn 1).
    turn2 = await store.create_turn(sid, capability="chat")
    execution2 = _TurnExecution(
        turn_id=turn2["id"], session_id=sid, capability="chat", payload={}
    )
    runtime._executions[turn2["id"]] = execution2
    await runtime._publish_live_event(
        execution2,
        StreamEvent(
            type=StreamEventType.SESSION,
            source="turn_runtime",
            metadata={"session_id": sid, "turn_id": turn2["id"]},
        ),
    )
    # Per-turn seq restarts at 1 — this seq-2 content event must NOT be
    # filtered out even though turn 1 already consumed seqs 1-2.
    await runtime._publish_live_event(
        execution2,
        StreamEvent(type=StreamEventType.CONTENT, source="chat", content="hi", metadata={}),
    )
    await store.update_turn_status(turn2["id"], "completed")
    runtime._executions.pop(turn2["id"], None)
    for _ in range(200):
        if len(received) >= 4:
            break
        await asyncio.sleep(0.01)
    assert [event["type"] for event in received] == [
        "session",
        "done",
        "session",
        "content",
    ]
    assert received[-1]["turn_id"] == turn2["id"]

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_subscribe_session_replays_inflight_backlog_and_deregisters(tmp_path) -> None:
    """A mid-turn subscriber gets the already-published live events (honouring
    ``after_seq``), and closing the generator unsubscribes it."""

    store = SQLiteSessionStore(tmp_path / "chat_history.db")
    runtime = TurnRuntimeManager(store)
    session = await store.ensure_session(None)
    sid = session["id"]
    turn = await store.create_turn(sid, capability="chat")
    execution = _TurnExecution(
        turn_id=turn["id"], session_id=sid, capability="chat", payload={}
    )
    runtime._executions[turn["id"]] = execution
    for i in range(2):
        await runtime._publish_live_event(
            execution,
            StreamEvent(
                type=StreamEventType.CONTENT, source="chat", content=f"c{i}", metadata={}
            ),
        )

    received: list[dict] = []
    ag = runtime.subscribe_session(sid, after_seq=1)
    async for event in ag:
        received.append(event)
        if len(received) == 1:
            break
    # Explicit close: a bare ``break`` leaves the generator's finally
    # scheduled on the loop, so cleanup is not synchronous. ``aclose()``
    # (like the WS router's task cancellation) drives it to completion.
    await ag.aclose()

    assert received[0]["seq"] == 2
    # aclose ran the finally block: the registry must be clean.
    assert not runtime._session_subscribers.get(sid)


@pytest.mark.asyncio
async def test_subscribe_session_broadcasts_to_multiple_subscribers(tmp_path) -> None:
    """Every session subscriber receives every published event (fan-out)."""

    store = SQLiteSessionStore(tmp_path / "chat_history.db")
    runtime = TurnRuntimeManager(store)
    session = await store.ensure_session(None)
    sid = session["id"]
    turn = await store.create_turn(sid, capability="chat")
    execution = _TurnExecution(
        turn_id=turn["id"], session_id=sid, capability="chat", payload={}
    )
    runtime._executions[turn["id"]] = execution

    results: dict[str, list[dict]] = {"a": [], "b": []}
    generators = [runtime.subscribe_session(sid, after_seq=0) for _ in ("a", "b")]

    async def _collect(name: str, ag) -> None:
        async for event in ag:
            results[name].append(event)
            if len(results[name]) == 1:
                break

    tasks = [
        asyncio.create_task(_collect("a", generators[0])),
        asyncio.create_task(_collect("b", generators[1])),
    ]
    for _ in range(200):
        if len(runtime._session_subscribers.get(sid, [])) == 2:
            break
        await asyncio.sleep(0.01)
    assert len(runtime._session_subscribers[sid]) == 2

    await runtime._publish_live_event(
        execution,
        StreamEvent(
            type=StreamEventType.CONTENT, source="chat", content="fanout", metadata={}
        ),
    )
    await asyncio.gather(*tasks)
    for ag in generators:
        await ag.aclose()
    assert [event["type"] for event in results["a"]] == ["content"]
    assert [event["type"] for event in results["b"]] == ["content"]
    assert not runtime._session_subscribers.get(sid)


# ---------------------------------------------------------------------------
# Ownership scoping the route-layer subscribe_session guard relies on
# ---------------------------------------------------------------------------


class _FakeRecord:
    def __init__(self, pb_id: str, data: dict) -> None:
        self.id = pb_id
        for key, value in data.items():
            setattr(self, key, value)


class _FakeCollection:
    """Minimal PocketBase collection: create + get_full_list with filters."""

    def __init__(self) -> None:
        self._rows: list[_FakeRecord] = []
        self._seq = 0

    def _matches(self, record: _FakeRecord, query_params: dict | None) -> bool:
        import re

        flt = (query_params or {}).get("filter") or ""
        for field, expected in re.findall(r'(\w+)\s*=\s*"([^"]*)"', flt):
            if str(getattr(record, field, "")) != expected:
                return False
        return True

    def create(self, data: dict) -> _FakeRecord:
        self._seq += 1
        record = _FakeRecord(f"pb{self._seq:04d}", data)
        self._rows.append(record)
        return record

    def get_full_list(self, query_params: dict | None = None) -> list[_FakeRecord]:
        return [r for r in self._rows if self._matches(r, query_params)]


class _FakeClient:
    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollection] = {}

    def collection(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())


@contextmanager
def _as_user(uid: str):
    scope = UserScope(kind="user", user_id=uid, root=Path("/tmp") / uid)  # noqa: S108
    token = set_current_user(CurrentUser(id=uid, username=uid, role="user", scope=scope))
    try:
        yield
    finally:
        reset_current_user(token)


@pytest.mark.asyncio
async def test_pocketbase_get_session_is_user_scoped(monkeypatch, tmp_path) -> None:
    """The route-layer ownership guard relies on ``get_session`` returning None
    for another user's session — verify that scoping holds on PocketBase."""

    client = _FakeClient()
    monkeypatch.setattr(
        "deeptutor.services.pocketbase_client.get_pb_client", lambda: client, raising=True
    )
    store = PocketBaseSessionStore()

    with _as_user("alice"):
        session = await store.create_session()
        sid = session["session_id"]
        assert await store.get_session(sid) is not None

    with _as_user("bob"):
        # Bob must not be able to resolve (and thus subscribe to) Alice's
        # session — this is the guard condition in unified_ws.py.
        assert await store.get_session(sid) is None

    with _as_user("alice"):
        assert await store.get_session(sid) is not None
