"""Browser monitoring — console and network event listeners.

Playwright only delivers console / network events *going forward*, so listeners
must be attached when the page is first created (see ``_session.get_page``).

Logs accumulate until ``clear_context()`` resets them or the tool methods
below drain them.
"""

import time


def _setup_monitoring(page, console_log: list, network_log: list) -> None:
    """Attach console and network listeners to *page*.

    *console_log* and *network_log* are plain Python lists owned by the
    ``BrowserManager`` instance.  Event handlers append entries directly.
    """
    _pending_requests: dict[int, float] = {}

    # ---- console ----------------------------------------------------------

    def _on_console(msg):
        if msg.type in ("error", "warning"):
            loc = msg.location
            console_log.append({
                "type": msg.type,
                "text": msg.text,
                "location": f"{loc.get('url', '')}:{loc.get('lineNumber', 0)}",
            })

    page.on("console", _on_console)

    # ---- network ----------------------------------------------------------

    def _on_request(request):
        _pending_requests[id(request)] = time.time()

    def _on_request_failed(request):
        err = request.failure
        network_log.append({
            "kind": "failed",
            "url": request.url,
            "error": err or "unknown",
        })

    def _on_response(response):
        req_id = id(response.request)
        start = _pending_requests.pop(req_id, None)
        duration = round(time.time() - start, 2) if start else None
        status = response.status

        if status >= 400 or (duration is not None and duration > 3.0):
            entry: dict = {"url": response.url, "status": status}
            if duration is not None:
                entry["duration"] = duration
            entry["kind"] = "error_response" if status >= 400 else "slow"
            network_log.append(entry)

    page.on("request", _on_request)
    page.on("requestfailed", _on_request_failed)
    page.on("response", _on_response)


def _drain_console_log(console_log: list, max_warnings: int = 50) -> str:
    """Read and clear *console_log*.  Returns a human-readable summary."""
    if not console_log:
        return "No console errors or warnings found."

    errors = [e for e in console_log if e["type"] == "error"]
    warnings = [e for e in console_log if e["type"] == "warning"]
    warnings_shown = warnings[:max_warnings]

    lines = [f"Console — {len(errors)} error(s), {len(warnings)} warning(s)"]

    if errors:
        lines.append("")
        lines.append("Errors:")
        for e in errors:
            lines.append(f"  • {e['text']}  ({e['location']})")

    if warnings_shown:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings_shown:
            lines.append(f"  • {w['text']}  ({w['location']})")
        if len(warnings) > max_warnings:
            lines.append(f"  … and {len(warnings) - max_warnings} more warnings")

    console_log.clear()
    return "\n".join(lines)


def _drain_network_log(network_log: list) -> str:
    """Read and clear *network_log*.  Returns a human-readable summary."""
    if not network_log:
        return "No network issues found."

    failed = [e for e in network_log if e["kind"] == "failed"]
    errors = [e for e in network_log if e["kind"] == "error_response"]
    slow = [e for e in network_log if e["kind"] == "slow"]

    sections = [f"Network — {len(failed)} failed, {len(errors)} error response(s), {len(slow)} slow request(s)"]

    if failed:
        sections.append("")
        sections.append("Failed requests:")
        for f in failed:
            sections.append(f"  • {f['url']}  ({f['error']})")

    if errors:
        sections.append("")
        sections.append("Error responses (4xx / 5xx):")
        for e in errors:
            dur = f"  {e['duration']}s" if "duration" in e else ""
            sections.append(f"  • {e['url']}  → {e['status']}{dur}")

    if slow:
        sections.append("")
        sections.append("Slow requests (> 3 s):")
        for s in slow:
            sections.append(f"  • {s['url']}  → {s['status']}  ({s['duration']}s)")

    network_log.clear()
    return "\n".join(sections)


def get_console_summary(self) -> str:
    return _drain_console_log(self._console_log)


def get_network_summary(self) -> str:
    return _drain_network_log(self._network_log)
