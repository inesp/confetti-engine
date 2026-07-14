import subprocess

import pytest
from unittest.mock import patch

from confetti.models import Conference
from confetti.scouting import claude_runner
from confetti.scouting.confs import ScoutResult
from confetti.scouting.discover_agent import DiscoverResult, discover_conferences
from confetti.scouting.scout_agent import scout_conferences


def _conf(name: str = "TestConf") -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
    )


def test_run_claude_kills_and_raises_on_timeout(tmp_path):
    real_popen = subprocess.Popen

    def slow_popen(_cmd, **kwargs):
        return real_popen(["sleep", "5"], **kwargs)

    with patch.object(claude_runner.subprocess, "Popen", side_effect=slow_popen):
        with pytest.raises(TimeoutError):
            claude_runner.run_claude(
                "prompt", log_file=tmp_path / "log.txt", timeout=0.3, model="haiku", max_budget_usd=0.5
            )


def test_scout_runs_in_small_chunks():
    confs = [_conf(f"Conf{i}") for i in range(5)]
    prompts = []

    def record(prompt, **_kwargs):
        prompts.append(prompt)
        return '{"conferences": []}'

    with patch("confetti.scouting.scout_agent.reset_log"):
        with patch("confetti.scouting.scout_agent.run_claude", side_effect=record):
            scout_conferences(confs)
    assert len(prompts) == 2


def test_scout_stops_after_current_batch():
    confs = [_conf(f"Conf{i}") for i in range(9)]  # 3 batches of 4, 4, 1
    batches = []

    def run_then_stop(prompt, **_kwargs):
        batches.append(prompt)
        claude_runner.stop()  # user clicks Stop during the first batch
        raise RuntimeError("Exit code -9")

    with patch("confetti.scouting.scout_agent.reset_log"):
        with patch("confetti.scouting.scout_agent.run_claude", side_effect=run_then_stop):
            scout_conferences(confs)
    claude_runner.clear_stop()
    assert len(batches) == 1


def test_reset_log_keeps_previous_run(tmp_path):
    log = tmp_path / "scout_debug.log"
    log.write_text("the stopped run")
    claude_runner.reset_log(log)
    assert (tmp_path / "scout_debug.prev.log").read_text() == "the stopped run"


def test_scout_reports_timeout_as_outcome():
    conf = _conf()
    with patch("confetti.scouting.scout_agent.reset_log"):
        with patch("confetti.scouting.scout_agent.run_claude", side_effect=TimeoutError):
            result = scout_conferences([conf])
    assert result == [ScoutResult(conf=conf, outcome="Error: timed out after 5 minutes")]


def test_discover_reports_timeout_as_outcome():
    with patch("confetti.scouting.discover_agent.reset_log"):
        with patch("confetti.scouting.discover_agent.run_claude", side_effect=TimeoutError):
            result = discover_conferences([])
    assert result == [DiscoverResult(name="Error", city="", country="", website="", why="Timed out after 10 minutes")]
