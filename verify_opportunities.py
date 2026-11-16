
#!/usr/bin/env python3
"""Earnly V1: conservative platform availability verification."""

import datetime as dt
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
NOW = dt.datetime.now(dt.timezone.utc)

HEADERS = {
    "apikey": KEY,
    "Authorization": "Bearer " + KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def supabase_request(path, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers=HEADERS,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None

def check_website(url):
    """Check availability only; do not infer legitimacy or payouts."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return "fail", "Invalid HTTPS URL"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "EarnlyVerifier/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            if 200 <= response.status < 400:
                return "pass", "Website responded successfully"
            return "unknown", "Unexpected HTTP response"
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return "fail", f"HTTP {exc.code}"
        return "unknown", f"HTTP {exc.code}"
    except Exception:
        return "unknown", "Website availability could not be confirmed"

def main():
    listings = supabase_request(
        "/rest/v1/earnly_discovery_catalog"
        "?select=id,name,url,source_hash"
        "&listing_kind=eq.platform"
        "&review_status=eq.pending_review"
        "&order=id.asc"
        "&limit=50"
    )

    results = []

    for item in listings:
        status, note = check_website(item["url"])
        checked_at = dt.datetime.now(dt.timezone.utc)
        expires_at = checked_at + dt.timedelta(hours=24)

        evidence = {
            "listing_id": item["id"],
            "source_url": item["url"],
            "source_hash": item["source_hash"],
            "check_type": "website_availability",
            "result": status,
            "evidence_text": note,
            "checked_at": checked_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        supabase_request(
            "/rest/v1/earnly_verification_evidence",
            method="POST",
            payload=evidence,
        )

        results.append({
            "name": item["name"],
            "availability": status,
        })

    print(json.dumps({
        "checked": len(results),
        "results": results,
        "note": "No listing approvals or publication statuses changed."
    }, indent=2))

if __name__ == "__main__":
    main()
