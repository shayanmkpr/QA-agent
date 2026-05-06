"""Centralised logging for the QA agent — just pretty-printed to stdout."""
import json
import os

VERBOSE = os.getenv("QA_VERBOSE", "true").lower() != "false"


def _log(prefix: str, msg: str, **kw) -> None:
    if not VERBOSE:
        return
    print(f"{prefix} {msg}", flush=True)
    if kw:
        for k, v in kw.items():
            val = _trunc(str(v), 500)
            print(f"       {k}={val}", flush=True)


def _trunc(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"... [{len(s)} total]"
