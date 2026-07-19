"""
Generic parallel agent runner.
Accepts an agent_dispatch dict mapping agent names to (callable, args, fallback) tuples
and executes all agents concurrently with per-agent timeout and retry.

Refactored from the original stock-specific run_agents_parallel in Story 3.
This stub is importable and returns _EMPTY_RESULT — full dispatch logic in Op 20.
"""
import concurrent.futures

_EMPTY_RESULT = {}


def run_agents_parallel(
    agent_dispatch: dict,
    timeout_seconds: float = 30,
    max_retries: int = 2,
) -> dict:
    """
    Execute agents concurrently and return a dict of {agent_name: result}.

    agent_dispatch format:
        {
            "agent_name": (callable, args_list, fallback_value),
            ...
        }

    fallback_value is returned for any agent that times out or raises.
    If fallback_value is omitted (2-tuple), None is used as fallback.

    # TODO Story 3 Op 20 — replace this stub with full generic dispatch implementation
    """
    try:
        ts = float(timeout_seconds)
    except (TypeError, ValueError):
        return _EMPTY_RESULT.copy()
    if ts <= 0 or not isinstance(agent_dispatch, dict) or not agent_dispatch:
        return _EMPTY_RESULT.copy()

    results = {}
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(agent_dispatch))
    try:
        for _attempt in range(int(max_retries) + 1):
            unresolved = {k: v for k, v in agent_dispatch.items() if k not in results}
            if not unresolved:
                break
            pending = {}
            for name, spec in unresolved.items():
                fn = spec[0]
                args = spec[1] if len(spec) > 1 else []
                pending[name] = executor.submit(fn, *args)
            for name, future in pending.items():
                try:
                    results[name] = future.result(timeout=ts)
                except Exception:
                    future.cancel()
    finally:
        executor.shutdown(wait=False)

    for name, spec in agent_dispatch.items():
        if name not in results:
            fallback = spec[2] if len(spec) > 2 else None
            results[name] = fallback

    return results
