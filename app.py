#!/usr/bin/env python3
"""
Enrich MCP Server — domain → company contact enrichment via Elasticsearch.

Streamable HTTP transport. Bearer token optional.
Rate limited per IP (10 total, 5/min) and global (10000 total).
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Ensure sibling modules are importable regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

from es_client import query_domain
from rate_limiter import RateLimiter

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

_ACCESS_LOG = Path(__file__).parent / "access.log"
_access = logging.getLogger("access")
_access.setLevel(logging.INFO)
_fh = logging.FileHandler(str(_ACCESS_LOG))
_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_access.addHandler(_fh)
_access.propagate = False

# ── MCP server ───────────────────────────────────────────────────────────────
mcp = FastMCP("enrich")


# ── health probes (K8s readiness / liveness) ────────────────────────────────
@mcp.custom_route("/status", methods=["GET"])
async def health_status(_: Request) -> JSONResponse:
    """Readiness probe — container is ready to serve traffic."""
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/inited", methods=["GET"])
async def health_inited(_: Request) -> JSONResponse:
    """Liveness probe — container is alive."""
    return JSONResponse({"status": "ok"})


# ── rate limiter (in-memory + file persistence) ──────────────────────────────
limiter = RateLimiter(
    state_file=Path(__file__).parent / "rate_state.json",
    per_ip_limit=10,        # max total requests per IP
    per_ip_window=60,       # per-minute window (seconds)
    per_ip_window_limit=5,  # max requests per IP per window
    global_limit=10000,     # global total requests
)

# ── domain validation ────────────────────────────────────────────────────────
DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def clean_domain(raw: str) -> str:
    """Strip protocol / path / port from user input, return bare domain."""
    raw = raw.strip().lower()
    # If it has a scheme, parse with urlparse
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.netloc or parsed.path
    # Drop port
    if ":" in raw:
        raw = raw.split(":")[0]
    # Drop path
    if "/" in raw:
        raw = raw.split("/")[0]
    return raw


def validate_domain(domain: str) -> str:
    """Raise ValueError if domain is invalid; return cleaned domain."""
    cleaned = clean_domain(domain)
    if not DOMAIN_RE.match(cleaned):
        raise ValueError(f"Invalid domain: {domain!r}")
    return cleaned


# ── helpers ──────────────────────────────────────────────────────────────────


def extract_domain(result: dict) -> str:
    """Best-effort domain extraction from an ES hit."""
    src = result.get("_source", result)
    # Try common domain fields
    for key in ("domain", "formatDomains", "format_domains"):
        val = src.get(key)
        if val:
            return val[0] if isinstance(val, list) else str(val)
    # Fallback: use the first formatDomains from summary
    summary = src.get("summary", {})
    fds = summary.get("formatDomains", [])
    return fds[0] if fds else ""


def extract_contacts(result: dict) -> list[str]:
    """Extract contact emails from a hit (bare addresses only)."""
    src = result.get("_source", result)
    raw_items = src.get("summary", {}).get("contactEmails", [])
    if not isinstance(raw_items, list):
        raw_items = [raw_items]
    out = []
    for item in raw_items:
        addr = item.get("email") if isinstance(item, dict) else str(item)
        if addr:
            out.append(addr)
    return out


def extract_socials(result: dict) -> dict[str, list[str]]:
    """Extract social media profiles."""
    src = result.get("_source", result)
    summary = src.get("summary", {})
    return {
        "facebooks": summary.get("facebooks", []),
        "instagrams": summary.get("instagrams", []),
        "linkedins": summary.get("linkedins", []),
        "twitters": summary.get("twitters", []),
        "youtubes": summary.get("youtubes", []),
    }


def extract_phones(result: dict) -> list[str]:
    """Extract contact phones (bare numbers only)."""
    src = result.get("_source", result)
    raw_items = src.get("summary", {}).get("contactPhones", [])
    if not isinstance(raw_items, list):
        raw_items = [raw_items]
    out = []
    for item in raw_items:
        num = item.get("phone") if isinstance(item, dict) else str(item)
        if num:
            out.append(num)
    return out


def hit_to_enrich(result: dict) -> dict:
    """Convert an ES hit to the enrich response payload."""
    src = result.get("_source", result)
    summary = src.get("summary", {})

    # Strip metadata from raw contact items
    raw_emails = [
        {"email": e.get("email")}
        for e in (summary.get("contactEmails", []) if isinstance(summary.get("contactEmails"), list) else [])
        if isinstance(e, dict) and e.get("email")
    ]
    raw_phones = [
        {"phone": p.get("phone")}
        for p in (summary.get("contactPhones", []) if isinstance(summary.get("contactPhones"), list) else [])
        if isinstance(p, dict) and p.get("phone")
    ]

    return {
        "domain": extract_domain(result),
        "name": src.get("name", ""),
        "country": src.get("country", ""),
        "contacts": {
            "emails": extract_contacts(result),
            "phones": extract_phones(result),
        },
        "social": extract_socials(result),
        "raw": {
            "contactEmails": raw_emails,
            "facebooks": summary.get("facebooks", []),
            "instagrams": summary.get("instagrams", []),
            "linkedins": summary.get("linkedins", []),
            "twitters": summary.get("twitters", []),
            "youtubes": summary.get("youtubes", []),
            "contactPhones": raw_phones,
        },
    }


# ── MCP tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def enrich_company(domain: str):
    """Enrich a company by domain name. Returns company name, country, contact
    emails, phone numbers, and social media profiles (LinkedIn, Twitter/X,
    Facebook, Instagram, YouTube).

    Args:
        domain: Company domain, e.g. 'stripe.com' or 'https://stripe.com'
    """
    client_ip = _get_client_ip()

    # 1. validate
    try:
        clean = validate_domain(domain)
    except ValueError as e:
        _access.info("ip=%s domain=%s result=invalid_input error=%s", client_ip, domain, e)
        return json.dumps({"error": str(e), "domain": domain})

    # 2. rate limit
    allowed, reason = limiter.check(client_ip)
    if not allowed:
        _access.warning("ip=%s domain=%s result=rate_limited reason=%s", client_ip, clean, reason)
        return json.dumps({"error": f"Rate limited: {reason}", "domain": clean})

    # 3. query ES
    try:
        results = query_domain(clean)
    except Exception as e:
        _access.error("ip=%s domain=%s result=es_error error=%s", client_ip, clean, e)
        return json.dumps({"error": "Internal error", "domain": clean})

    # 4. format response
    hits = results.get("hits", {}).get("hits", []) if results else []
    if not hits:
        _access.info("ip=%s domain=%s result=not_found", client_ip, clean)
        return json.dumps({
            "domain": clean,
            "found": False,
            "message": f"No enrichment data found for domain '{clean}'",
        })

    enriched = [hit_to_enrich(h) for h in hits]
    _access.info("ip=%s domain=%s result=success total=%s", client_ip, clean, len(enriched))

    result = {
        "domain": clean,
        "found": True,
        "total": len(enriched),
        "results": enriched,
    }
    return json.dumps(result, ensure_ascii=False)


def _get_client_ip() -> str:
    try:
        req = get_http_request()
        from_ip = req.headers.get("X-From-IP", "")
        if from_ip:
            return from_ip.strip()
        return req.client.host if req.client else "unknown"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    import sys
    if "--stdio" in sys.argv:
        log.info("Starting Enrich MCP server via stdio")
        mcp.run(transport="stdio")
    else:
        log.info("Starting Enrich MCP server on http://0.0.0.0:8080/mcp")
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
