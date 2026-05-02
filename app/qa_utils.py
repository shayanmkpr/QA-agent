"""Deterministic surface-level QA checks (no LLM involved).

TODO: add CORS header checks, console error capture, performance timing.
"""

from typing import List, Dict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def _is_internal(url: str, base_url: str) -> bool:
    """Return True if *url* shares the same netloc as *base_url*."""
    return urlparse(url).netloc == urlparse(base_url).netloc


def _check_resource(url: str, timeout: int = 10) -> tuple[int, str]:
    """Perform a HEAD request and return (status_code, error_message).

    Falls back to GET if HEAD is not allowed (405).
    """
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 405:
            resp = requests.get(url, timeout=timeout, stream=True)
        return resp.status_code, ""
    except requests.exceptions.Timeout:
        return 0, "Request timed out"
    except requests.exceptions.RequestException as exc:
        return 0, str(exc)


def check_resources(html: str, base_url: str) -> List[Dict[str, str]]:
    """Scan *html* for broken links, images, and missing assets.

    Returns a list of issue dicts with keys:
        - url: absolute URL of the resource
        - issue_type: 'broken_link' | 'broken_image' | 'missing_asset'
        - description: human-readable explanation
        - category: 'frontend' | 'backend' | 'both'
    """
    soup = BeautifulSoup(html, "html.parser")
    issues: List[Dict[str, str]] = []

    # --- Links ---
    for tag in soup.find_all("a", href=True):
        href = urljoin(base_url, tag["href"])
        status, err = _check_resource(href)
        if status >= 400 or err:
            issues.append(
                {
                    "url": href,
                    "issue_type": "broken_link",
                    "description": f"HTTP {status}" if status else err,
                    "category": "backend",
                }
            )

    # --- Images ---
    for tag in soup.find_all("img", src=True):
        src = urljoin(base_url, tag["src"])
        status, err = _check_resource(src)
        if status >= 400 or err:
            issues.append(
                {
                    "url": src,
                    "issue_type": "broken_image",
                    "description": f"HTTP {status}" if status else err,
                    "category": "backend",
                }
            )

    # --- Stylesheets ---
    for tag in soup.find_all("link", rel="stylesheet", href=True):
        href = urljoin(base_url, tag["href"])
        status, err = _check_resource(href)
        if status >= 400 or err:
            issues.append(
                {
                    "url": href,
                    "issue_type": "missing_asset",
                    "description": f"Stylesheet returned HTTP {status}" if status else err,
                    "category": "backend",
                }
            )

    # --- Scripts ---
    for tag in soup.find_all("script", src=True):
        src = urljoin(base_url, tag["src"])
        status, err = _check_resource(src)
        if status >= 400 or err:
            issues.append(
                {
                    "url": src,
                    "issue_type": "missing_asset",
                    "description": f"Script returned HTTP {status}" if status else err,
                    "category": "backend",
                }
            )

    return issues
