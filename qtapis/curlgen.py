"""cURL command generation with a caller-overridable endpoint.

The public-apis registry links to documentation pages, not live endpoints, so a
generated command targets the docs URL. Callers can override the endpoint (the
inspector exposes an editable field) to target a real resource.
"""

from __future__ import annotations

import shlex

from .catalog import ApiRecord

AUTH_HEADERS = {
    "apikey": ("X-API-Key", "$YOUR_API_KEY"),
    "oauth": ("Authorization", "Bearer $YOUR_ACCESS_TOKEN"),
}

# Auth schemes outside the three the registry uses most.
EXTRA_AUTH_HEADERS = {
    "x-mashape-key": ("X-Mashape-Key", "$YOUR_MASHAPE_KEY"),
    "user-agent": ("User-Agent", "$YOUR_APP_NAME"),
}

PLACEHOLDER = "$YOUR_API_KEY"


def auth_scheme(record: ApiRecord) -> str | None:
    """The auth scheme to use for a record, if any."""
    if record.auth in AUTH_HEADERS:
        return record.auth
    if record.auth in EXTRA_AUTH_HEADERS:
        return record.auth
    return None


def build_curl(record: ApiRecord, endpoint: str | None = None) -> str:
    """Render a runnable curl command.

    `endpoint` overrides the registry URL (the docs link) when the caller knows
    the real resource path.
    """
    target = (endpoint or record.url or "https://example.com").strip()

    parts = ["curl", "-sS", "-L", shlex.quote(target)]

    scheme = auth_scheme(record)
    if scheme:
        name, value = AUTH_HEADERS.get(scheme) or EXTRA_AUTH_HEADERS[scheme]
        parts += ["-H", shlex.quote(f"{name}: {value}")]

    # Flag either an insecure target or a registry entry the README marks
    # as not served over HTTPS - both are worth surfacing before running.
    if not target.lower().startswith("https://") or not record.is_https:
        parts += ["--insecure", "# WARNING: upstream is not served over HTTPS"]

    return " ".join(parts)


def auth_hint(record: ApiRecord) -> str:
    """A short note describing what the generated command will contain."""
    if auth_scheme(record):
        return f"Includes a {record.auth} header placeholder."
    if record.auth not in ("none", "unknown", ""):
        return f"Registry declares '{record.auth}' auth; no header template known."
    return "No authentication required."