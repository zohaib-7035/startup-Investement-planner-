"""
Tests for data/parallel_runner.py — generic dispatch interface.
Stock-specific tests removed; new tests cover the generic agent_dispatch contract.
"""
import time
from data.parallel_runner import run_agents_parallel, _EMPTY_RESULT


def _agent_returns(value):
    return lambda: value


def _agent_raises(exc_type=RuntimeError):
    def _fn():
        raise exc_type("test error")
    return _fn


# ── Basic dispatch ────────────────────────────────────────────────────────────

def test_single_agent_returns_its_result():
    dispatch = {"greeting": (_agent_returns("hello"), [])}
    result = run_agents_parallel(dispatch)
    assert result["greeting"] == "hello"


def test_multiple_agents_all_returned():
    dispatch = {
        "a": (_agent_returns(1), []),
        "b": (_agent_returns(2), []),
        "c": (_agent_returns(3), []),
    }
    result = run_agents_parallel(dispatch)
    assert result["a"] == 1
    assert result["b"] == 2
    assert result["c"] == 3


def test_agent_with_args_receives_them():
    def _add(x, y):
        return x + y
    dispatch = {"sum": (_add, [3, 4])}
    result = run_agents_parallel(dispatch)
    assert result["sum"] == 7


# ── Fallback on failure ───────────────────────────────────────────────────────

def test_failing_agent_returns_fallback_value():
    dispatch = {"bad": (_agent_raises(), [], "fallback_value")}
    result = run_agents_parallel(dispatch)
    assert result["bad"] == "fallback_value"


def test_failing_agent_without_fallback_returns_none():
    dispatch = {"bad": (_agent_raises(), [])}
    result = run_agents_parallel(dispatch)
    assert result["bad"] is None


def test_one_failing_agent_does_not_affect_others():
    dispatch = {
        "good": (_agent_returns("ok"), []),
        "bad":  (_agent_raises(), [], "fb"),
    }
    result = run_agents_parallel(dispatch)
    assert result["good"] == "ok"
    assert result["bad"] == "fb"


# ── Guard conditions ──────────────────────────────────────────────────────────

def test_zero_timeout_returns_empty_result():
    dispatch = {"x": (_agent_returns(1), [])}
    result = run_agents_parallel(dispatch, timeout_seconds=0)
    assert result == _EMPTY_RESULT


def test_negative_timeout_returns_empty_result():
    result = run_agents_parallel({"x": (_agent_returns(1), [])}, timeout_seconds=-1)
    assert result == _EMPTY_RESULT


def test_non_numeric_timeout_returns_empty_result():
    result = run_agents_parallel({"x": (_agent_returns(1), [])}, timeout_seconds="bad")
    assert result == _EMPTY_RESULT


def test_empty_dispatch_returns_empty_result():
    result = run_agents_parallel({})
    assert result == _EMPTY_RESULT


def test_non_dict_dispatch_returns_empty_result():
    result = run_agents_parallel(None)  # type: ignore[arg-type]
    assert result == _EMPTY_RESULT


# ── Concurrency — all agents run in parallel ──────────────────────────────────

def test_agents_run_concurrently_not_sequentially():
    def _slow():
        time.sleep(0.2)
        return "done"
    dispatch = {f"agent_{i}": (_slow, []) for i in range(5)}
    start = time.time()
    result = run_agents_parallel(dispatch, timeout_seconds=5)
    elapsed = time.time() - start
    # If sequential: 5 × 0.2 s = 1 s. Parallel should be ~0.2 s.
    assert elapsed < 0.8, f"Agents appear sequential: took {elapsed:.2f}s"
    assert len(result) == 5


# ── Retry behaviour ───────────────────────────────────────────────────────────

def test_agent_succeeds_on_retry():
    call_count = {"n": 0}
    def _flaky():
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise RuntimeError("first attempt fails")
        return "success"
    dispatch = {"flaky": (_flaky, [], "fallback")}
    result = run_agents_parallel(dispatch, max_retries=2)
    assert result["flaky"] == "success"
