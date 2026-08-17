"""Shared Claude CLI runner used by both scout and discover agents."""

import json
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import IO

# Running Claude processes, tracked so they can be killed from outside (the Stop
# button). A set rather than a single global so a scout run and a discover run
# can be in flight at once without clobbering each other's handle.
_lock = threading.Lock()
_running: "set[subprocess.Popen[str]]" = set()

# Set when the user clicks Stop, so a batched run ends instead of starting the
# next batch. Cleared at the start of each fresh run.
_stop_requested = threading.Event()

# The scout/discover agents only research the web and return JSON; the Python
# code writes the YAML. So they need no project context and only two tools.
# Running from a scratch dir (not PROJECT_ROOT) skips loading the project
# CLAUDE.md; --strict-mcp-config drops all MCP servers; --tools strips the
# schemas of every built-in tool except these two out of the context
# (--allowedTools alone does NOT do that: it only grants permission, the
# other tools' schemas still ship, ~17k tokens of them); --allowedTools then
# pre-approves the two survivors so headless runs never stall on permission.
_AGENT_TOOLS = "WebSearch,WebFetch"

# Replaces Claude Code's default coding-agent system prompt with a minimal
# research brief. The task instructions live in the per-run prompt; this only
# sets the role and the two rules that matter. Measured (Aug 2026, haiku): a
# default invocation receives ~27k input tokens, this trimmed setup ~2.3k.
_AGENT_SYSTEM_PROMPT = (
    "You are a precise web research agent. You find facts by fetching and searching the web "
    "with the WebFetch and WebSearch tools. Report only what you actually find on the pages, "
    "never guess or invent. When the user asks for a specific output format, reply with exactly "
    "that and nothing else."
)


def prev_log_path(log_file: Path) -> Path:
    """Sibling path where the previous run's log is kept (e.g. scout_debug.prev.log)."""
    return log_file.with_name(f"{log_file.stem}.prev{log_file.suffix}")


def reset_log(log_file: Path) -> None:
    """Start a fresh log for a run, keeping the previous run's log to look back at.

    The run's batches append to the fresh file; the prior run (stopped or finished)
    is rotated to a `.prev.log` sibling instead of being deleted.
    """
    if log_file.exists():
        log_file.replace(prev_log_path(log_file))


def run_claude(prompt: str, log_file: Path, timeout: float, model: str, max_budget_usd: float) -> str:
    """Run Claude CLI with a prompt, stream output to log file, return the result text.

    Runs a cheap `model` and passes `max_budget_usd` as a hard ceiling that aborts
    the run if it overspends, to keep the token cost in check.
    Kills the process and raises TimeoutError if it runs longer than `timeout` seconds.
    Raises FileNotFoundError if claude CLI is not found.
    Raises RuntimeError if Claude exits with a non-zero code or no output.
    """
    proc = subprocess.Popen(
        [
            "claude",
            "--print",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--strict-mcp-config",
            "--tools",
            _AGENT_TOOLS,
            "--allowedTools",
            _AGENT_TOOLS,
            "--system-prompt",
            _AGENT_SYSTEM_PROMPT,
            "--model",
            model,
            "--max-budget-usd",
            str(max_budget_usd),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=tempfile.gettempdir(),
    )

    # A blocking read on proc.stdout can't honour a timeout on its own, so a timer
    # kills the process from the side; the killed read then unblocks and returns.
    timed_out = threading.Event()

    def _kill_on_timeout() -> None:
        timed_out.set()
        proc.kill()

    timer = threading.Timer(timeout, _kill_on_timeout)
    with _lock:
        _running.add(proc)
    timer.start()
    try:
        raw = _stream_to_log(proc, log_file)
        returncode = proc.returncode
    finally:
        timer.cancel()
        with _lock:
            _running.discard(proc)

    if timed_out.is_set():
        raise TimeoutError(f"Claude timed out after {int(timeout)}s")

    if returncode != 0:
        raise RuntimeError(f"Exit code {returncode}: {raw[:500]}")

    if not raw:
        raise RuntimeError("No output from Claude")

    return raw


def stop() -> bool:
    """Request a stop: flag the run to end and kill all running Claude processes.

    Returns True if any process was killed.
    """
    _stop_requested.set()
    with _lock:
        procs = list(_running)
        _running.clear()
    for proc in procs:
        proc.kill()
    return bool(procs)


def is_stopped() -> bool:
    """Whether Stop was clicked during the current run."""
    return _stop_requested.is_set()


def clear_stop() -> None:
    """Reset the stop flag at the start of a fresh run."""
    _stop_requested.clear()


def extract_json(text: str) -> str | None:
    """Extract JSON from text that may contain markdown code fences or other wrapping."""
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return text

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()

    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        candidate = text[start:end].strip()
        if candidate.startswith("{") or candidate.startswith("["):
            return candidate

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]

    return None


def _log(f: IO[str], msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    f.write(f"[{ts}] {msg}\n")
    f.flush()


def _stream_to_log(proc: subprocess.Popen, log_file: Path) -> str:  # type: ignore[type-arg]
    """Read stream-json from the process, write a human-readable log, return the final result text."""
    result_text = ""
    with open(log_file, "a") as f:
        _log(f, "=== Started ===")
        for line in proc.stdout or []:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                _log(f, f"??? {line[:200]}")
                continue

            etype = event.get("type")

            if etype == "assistant":
                msg = event.get("message", {})
                for block in msg.get("content", []):
                    btype = block.get("type")
                    if btype == "text":
                        _log(f, f"CLAUDE: {block['text'][:500]}")
                    elif btype == "tool_use":
                        tool = block.get("name", "?")
                        inp = json.dumps(block.get("input", {}))
                        if len(inp) > 300:
                            inp = inp[:300] + "..."
                        _log(f, f"TOOL CALL: {tool}({inp})")
                    elif btype == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
                        if len(content) > 300:
                            content = content[:300] + "..."
                        _log(f, f"TOOL RESULT: {content}")

            elif etype == "result":
                result_text = event.get("result", "")
                duration = event.get("duration_ms", 0)
                usage = event.get("usage", {})
                # cache_creation counts too: on a fresh run it holds most of the context
                tokens_in = (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                )
                tokens_out = usage.get("output_tokens", 0)
                cost = event.get("total_cost_usd", 0)
                _log(f, f"=== Done in {duration / 1000:.1f}s | {tokens_in} in, {tokens_out} out | ${cost:.4f} ===")

        proc.wait()
    return result_text
