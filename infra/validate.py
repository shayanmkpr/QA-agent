import os
import sys


class EnvError(Exception):
    """Raised when a critical environment requirement is not met."""


def check_llm_provider() -> None:
    """Ensure at least one LLM provider is configured with an API key."""
    provider = os.getenv("LLM_PROVIDER", "openrouter")

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise EnvError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai. "
                "Set it in your .env file or environment."
            )
    elif provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise EnvError(
                "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter. "
                "Set it in your .env file or environment."
            )
    else:
        raise EnvError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Supported providers: openai, openrouter."
        )


def check_persistence() -> None:
    """Ensure the data directory is writable so reference data can be persisted."""
    from infra.storage import DEFAULT_DATA_DIR

    try:
        DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        test_file = DEFAULT_DATA_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (OSError, PermissionError) as exc:
        raise EnvError(
            f"Cannot write to data directory '{DEFAULT_DATA_DIR}': {exc}. "
            "Ensure the directory is writable or configure an alternative "
            "storage backend."
        )


def check_browser() -> None:
    """Warn (but do not fail) if Playwright/Chromium is not installed."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "[WARN] Playwright is not installed. "
            "Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch()
    except Exception:
        print(
            "[WARN] Chromium could not be launched. "
            "Run: playwright install chromium",
            file=sys.stderr,
        )


def validate_all(require_browser: bool = True) -> None:
    """Run all environment checks.

    Args:
        require_browser: If True, print warnings when browser is unavailable
                         (the check is non-fatal).

    Raises:
        EnvError: If a critical requirement (LLM keys, persistence) is not met.
    """
    errors: list[str] = []

    try:
        check_llm_provider()
    except EnvError as e:
        errors.append(str(e))

    try:
        check_persistence()
    except EnvError as e:
        errors.append(str(e))

    if errors:
        print("[ERROR] Environment validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  • {err}", file=sys.stderr)
        sys.exit(1)

    if require_browser:
        check_browser()
