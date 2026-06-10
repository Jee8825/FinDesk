"""Ping graph nodes — the Planner→Executor→Critic shape with no-op work.

Phase 0: proves checkpoints, events, and the worker loop end-to-end before any
LLM enters the system (roadmap Phase 1 rationale).
"""

from __future__ import annotations

import asyncio

from findesk_shared import uuid7

from findesk_agents.graphs.ping.state import PingState


async def plan(state: PingState) -> dict:
    step_id = uuid7()
    await state.emitter.step("plan", "started", step_id)
    await asyncio.sleep(0.2)  # simulated thinking
    plan = ["check_pulse", "report"]
    await state.emitter.step("plan", "finished", step_id, plan=plan)
    return {"plan": plan}


async def execute(state: PingState) -> dict:
    executed: list[str] = []
    for task in state.plan:
        step_id = uuid7()
        await state.emitter.step(f"execute:{task}", "started", step_id)
        await asyncio.sleep(0.2)  # simulated tool call
        executed.append(task)
        await state.emitter.step(f"execute:{task}", "finished", step_id)
    return {"executed": executed}


async def critic(state: PingState) -> dict:
    step_id = uuid7()
    await state.emitter.step("critic", "started", step_id)
    ok = state.executed == state.plan
    summary = "pong — all planned steps executed" if ok else "plan/execution mismatch"
    await state.emitter.step("critic", "finished", step_id, verdict="pass" if ok else "fail")
    return {"summary": summary}
