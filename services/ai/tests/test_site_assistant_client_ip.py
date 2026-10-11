"""Per-IP cap keys on the gateway-set client address (design.md Decision 6)."""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

REPO = Path(__file__).resolve().parents[3]
CADDYFILE = REPO / "Caddyfile"
NGINX_CONFS = [REPO / "nginx" / "nginx.conf", REPO / "nginx" / "nginx-dev.conf"]


def _client_host_app() -> TestClient:
    # Mirrors entrypoint.sh's prod flags: --proxy-headers --forwarded-allow-ips='*'.
    inner = FastAPI()

    @inner.get("/ip")
    async def ip(request: Request) -> dict:
        return {"host": request.client.host}

    return TestClient(ProxyHeadersMiddleware(inner, trusted_hosts="*"))


def test_appending_gateway_would_be_spoofable():
    # Why the Caddyfile guard below matters: '*' trust takes the leftmost, client-set entry.
    resp = _client_host_app().get("/ip", headers={"X-Forwarded-For": "198.51.100.99, 203.0.113.7"})
    assert resp.json()["host"] == "198.51.100.99"


@pytest.mark.skipif(not CADDYFILE.exists(), reason="Caddyfile not present (container run)")
def test_caddyfile_overwrites_client_forwarded_for():
    config = re.sub(r"#.*", "", CADDYFILE.read_text())
    assert "trusted_proxies" not in config
    assert not re.search(r"header_up\s+[+-]?X-Forwarded-For", config, re.IGNORECASE)


def _nginx_ai_location(conf: Path) -> str:
    text = re.sub(r"#.*", "", conf.read_text())
    match = re.search(r"location /api/v1/ai/ \{(.*?)\}", text, re.DOTALL)
    assert match, f"no /api/v1/ai/ location in {conf.name}"
    return match.group(1)


@pytest.mark.skipif(not CADDYFILE.exists(), reason="gateway configs not present (container run)")
@pytest.mark.parametrize("conf", NGINX_CONFS, ids=lambda p: p.name)
def test_nginx_ai_location_overwrites_client_forwarded_for(conf):
    block = _nginx_ai_location(conf)
    assert re.search(r"proxy_set_header\s+X-Forwarded-For\s+\$remote_addr;", block)
    assert "$proxy_add_x_forwarded_for" not in block


@pytest.mark.skipif(not CADDYFILE.exists(), reason="gateway configs not present (container run)")
@pytest.mark.parametrize("conf", [CADDYFILE, *NGINX_CONFS], ids=lambda p: p.name)
def test_gateways_expose_retry_after_to_browsers(conf):
    exposed = re.search(r"Access-Control-Expose-Headers['\"]?\s+['\"]([^'\"]+)", conf.read_text())
    assert exposed and "Retry-After" in exposed.group(1)
