"""
Elasticsearch client — single query against cowork_global_domain_company_v2 index.

ES connection:
    hosts: 10.44.54.48:9200, 10.44.54.49:9200, 10.44.54.51:9200,
           10.44.54.52:9200, 10.44.54.53:9200
    auth:  elastic / WjKJh68vqqItSo5DHP4in/
"""

import logging

from elasticsearch import Elasticsearch

log = logging.getLogger(__name__)

# ── connection ───────────────────────────────────────────────────────────────

ES_HOSTS = [
    "http://10.44.54.48:9200",
    "http://10.44.54.49:9200",
    "http://10.44.54.51:9200",
    "http://10.44.54.52:9200",
    "http://10.44.54.53:9200",
]
ES_USER = "mcp_read"
ES_PASSWORD = "13fd1dc1f413fd1f3!#fcc1~"
ES_INDEX = "cowork_global_domain_company_v2"

es = Elasticsearch(
    hosts=ES_HOSTS,
    basic_auth=(ES_USER, ES_PASSWORD),
    request_timeout=10,
    max_retries=2,
    retry_on_timeout=True,
)

# ── query ────────────────────────────────────────────────────────────────────


def query_domain(domain: str) -> dict | None:
    """Search ES for a domain. Returns raw ES response dict or None on failure.

    Query fields (from DomainCompanyAggregateBO mapping):
        domain, name, country,
        summary.contactEmails, summary.facebooks, summary.instagrams,
        summary.linkedins, summary.twitters, summary.youtubes,
        summary.contactPhones

    Excludes records where disable=true.
    """

    body = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"summary.formatDomains.keyword": {"value": domain}}}
                ],
                "must_not": [
                    {"term": {"disable": {"value": "true"}}}
                ],
            }
        }
    }

    log.info("ES query index=%s domain=%s", ES_INDEX, domain)

    try:
        resp = es.search(index=ES_INDEX, body=body, size=20)
        log.info(
            "ES result domain=%s took=%sms total=%s hits=%s",
            domain,
            resp.get("took", "?"),
            resp.get("hits", {}).get("total", {}).get("value", 0),
            len(resp.get("hits", {}).get("hits", [])),
        )
        return resp
    except Exception:
        log.exception("ES query failed for domain=%s", domain)
        raise
