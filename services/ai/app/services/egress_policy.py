import json
from dataclasses import dataclass
from urllib.parse import urlsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True)
class ApprovedOrigin:
    origin: str
    allow_private: bool
    label: str | None = None


def normalize_origin(url: str) -> str | None:
    """Return "scheme://host[:port]" for a plain http(s) URL, or None if the
    URL is malformed, isn't http(s), or carries embedded credentials."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    if parts.username or parts.password:
        return None
    host = parts.hostname
    if not host:
        return None
    host = host.lower()
    if ":" in host:
        host = f"[{host}]"
    if port is None or port == _DEFAULT_PORTS[parts.scheme]:
        return f"{parts.scheme}://{host}"
    return f"{parts.scheme}://{host}:{port}"


def parse_approved_origins(raw: str | None) -> list[ApprovedOrigin]:
    """Parse AI_PROVIDER_APPROVED_ORIGINS: a JSON list of
    {"origin", "allow_private", "label"?}; any malformed value raises ValueError."""
    if not raw:
        return []
    entries = json.loads(raw)
    if not isinstance(entries, list):
        raise ValueError("AI_PROVIDER_APPROVED_ORIGINS: expected a JSON list")
    parsed = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("origin"), str):
            raise ValueError(f"AI_PROVIDER_APPROVED_ORIGINS: entry needs an origin: {entry!r}")
        normalized = normalize_origin(entry["origin"])
        if normalized is None:
            raise ValueError(f"AI_PROVIDER_APPROVED_ORIGINS: invalid origin {entry['origin']!r}")
        parsed.append(
            ApprovedOrigin(
                origin=normalized,
                allow_private=bool(entry.get("allow_private")),
                label=entry.get("label"),
            )
        )
    return parsed


def is_approved(url: str, approved: list[ApprovedOrigin]) -> ApprovedOrigin | None:
    normalized = normalize_origin(url)
    if normalized is None:
        return None
    return next((entry for entry in approved if entry.origin == normalized), None)
