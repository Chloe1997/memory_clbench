"""Baseline harness (Pydantic AI).

One *session* per question:
  1. new conversation; MEMORY.md (first N lines) is injected into the prompt
  2. agent explores with run_sql and answers ("ANSWER: <value>")
  3. same conversation receives feedback (the stated correct answer) and may
     update memory
  4. transcript saved to transcripts/qXX.json  (layer 1: searchable event log)
After each question the harness calls `dream()` - a no-op in the baseline.

Memory layers in this baseline:
  transcripts  -> saved, but never read back (students: add a search tool)
  notes        -> free-form files under memory/
  representations (wiki) -> none
  injected context -> MEMORY.md head
  dreaming     -> no-op hook

Students: subclass BaselineHarness and override `system_prompt`,
`build_tools`, `user_prompt`, `feedback_prompt`, `dream`, or add guardrails
inside the tool wrappers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.usage import UsageLimits

from .env import Question
from .tools import MemoryStore, SqlTool


@dataclass
class Deps:
    sql: SqlTool
    mem: MemoryStore | None


# ---- tool functions -------------------------------------------------------- #
def list_tables(ctx: RunContext[Deps]) -> str:
    """List all tables and their CREATE statements."""
    return ctx.deps.sql.run("SELECT name, sql FROM sqlite_master WHERE type='table'")


def run_sql(ctx: RunContext[Deps], sql: str) -> str:
    """Run a SQL query against the SQLite database and return up to 30 rows."""
    return ctx.deps.sql.run(sql)


def _safe(fn, *a) -> str:
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001  -> show the model the error, don't crash
        return f"ERROR: {e}"


def memory_view(ctx: RunContext[Deps], path: str = "/") -> str:
    """List memory files (path='/') or read one file (e.g. path='MEMORY.md')."""
    return _safe(ctx.deps.mem.view, path)


def memory_write(ctx: RunContext[Deps], path: str, content: str) -> str:
    """Create or overwrite a memory file."""
    return _safe(ctx.deps.mem.write, path, content)


def memory_str_replace(ctx: RunContext[Deps], path: str, old: str, new: str) -> str:
    """Replace one exact occurrence of `old` with `new` in a memory file."""
    return _safe(ctx.deps.mem.str_replace, path, old, new)


def memory_delete(ctx: RunContext[Deps], path: str) -> str:
    """Delete a memory file."""
    return _safe(ctx.deps.mem.delete, path)


ANSWER_RE = re.compile(r"ANSWER:\s*(.+)", re.IGNORECASE)


def parse_answer(text: str) -> str:
    m = ANSWER_RE.findall(text or "")
    if m:
        return m[-1].strip().strip("`*").strip()
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1].strip() if lines else ""


class BaselineHarness:
    def __init__(self, model, sql: SqlTool, mem: MemoryStore | None,
                 transcript_dir: Path, request_limit: int = 15):
        self.sql, self.mem = sql, mem
        self.transcript_dir = transcript_dir
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self.limits = UsageLimits(request_limit=request_limit)
        self.agent = Agent(model, deps_type=Deps, system_prompt=self.system_prompt(),
                           tools=self.build_tools(), retries=2)

    # ---- override points ---------------------------------------------------- #
    def system_prompt(self) -> str:
        base = ("You answer analytics questions about a SQLite database using the tools. "
                "Explore the schema before answering. Questions come in a long sequence "
                "and the database may change over time. "
                "End your reply with one final line: `ANSWER: <value>`.")
        if self.mem is not None:
            base += (" You have a persistent memory folder; it is the only thing that "
                     "survives between questions, and MEMORY.md is shown to you at the "
                     "start of every question.")
        return base

    def build_tools(self) -> list:
        tools = [Tool(list_tables), Tool(run_sql)]
        if self.mem is not None:
            tools += [Tool(memory_view), Tool(memory_write),
                      Tool(memory_str_replace), Tool(memory_delete)]
        return tools

    def user_prompt(self, q: Question) -> str:
        if self.mem is None:
            return f"Question {q.idx + 1}: {q.text}"
        return (f"<memory_index>\n{self.mem.injected_context()}\n</memory_index>\n\n"
                f"Question {q.idx + 1}: {q.text}")

    def feedback_prompt(self, q: Question, answer: str, correct: bool) -> str:
        return (f"Feedback: the correct answer was {q.feedback_answer}. Your answer "
                f"({answer or 'none'}) was {'correct' if correct else 'incorrect'}. "
                "You may now update your memory before the next question. Reply DONE when finished.")

    def dream(self, q: Question) -> None:
        """Offline consolidation between sessions. Baseline: do nothing."""
        return None

    # ---- main loop step ----------------------------------------------------- #
    def step(self, q: Question, judge) -> dict:
        deps = Deps(self.sql, self.mem)
        self.sql.qidx = q.idx
        raw, answer, err, history = "", "", None, []
        try:
            r = self.agent.run_sync(self.user_prompt(q), deps=deps, usage_limits=self.limits)
            raw, history = r.output, r.all_messages()
            answer = parse_answer(raw)
        except Exception as e:  # noqa: BLE001  (limit exceeded, bad tool JSON, ...)
            err = f"{type(e).__name__}: {e}"
        told_correct = judge(answer, q.feedback_answer)
        if self.mem is not None:
            try:
                r2 = self.agent.run_sync(self.feedback_prompt(q, answer, told_correct),
                                         deps=deps, message_history=history or None,
                                         usage_limits=self.limits)
                history = r2.all_messages()
            except Exception as e:  # noqa: BLE001
                err = (err or "") + f" | feedback: {type(e).__name__}: {e}"
        if history:
            from pydantic_core import to_json
            (self.transcript_dir / f"q{q.idx:02d}.json").write_bytes(to_json(history, indent=1))
        self.dream(q)
        return {"idx": q.idx, "phase": q.phase, "kind": q.kind, "question": q.text,
                "answer": answer, "raw": raw, "gold": q.gold, "error": err}
