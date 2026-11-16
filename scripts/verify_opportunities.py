
#!/usr/bin/env python3
"""Earnly V2: website checks and official-source evidence collection."""

import datetime as dt
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": KEY,
    "Authorization": "Bearer " + KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Official documentation sources. Add more only after checking
# that the URLs belong to the platform or its official help center.
OFFICIAL_SOURCES = {
    "CloudResearch Connect": [
        "https://connect-participant-help.cloudresearch.com/hc/en-us"
    ],
    "Freecash": [
        "https://freecash.com"
    ],
    "PlaytestCloud": [
        "https://players.playtestcloud.com"
    ],
    "Respondent": [
        "https://www.respondent.io"
    ],
    "Swagbucks": [
        "https://www.swagbucks.com"
    ],
    "UserTesting": [
        "https://www.usertesting.com/get-paid-to-test"
    ],
}

def api(path, method="GET", payload=None):
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

def fetch_page(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return "fail", "", "Invalid HTTPS URL"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EarnlyVerifier/2.0",
                "Accept": "text/html",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            if not 200 <= response.status < 400:
                return "unknown", "", "Unexpected HTTP status"

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower():
                return "unknown", "", "Non-HTML response"

            raw = response.read(500_001)
            if len(raw) > 500_000:
                return "unknown", "", "Page exceeds size limit"

            charset = response.headers.get_content_charset() or "utf-8"
            page = raw.decode(charset, errors="replace")

            # Strip scripts and markup; retain readable text.
            page = re.sub(
                r"<(script|style)\b[^>]*>.*?</\1>",
                " ",
                page,
                flags=re.I | re.S,
            )
            page = re.sub(r"<[^>]+>", " ", page)
            page = html.unescape(page)
            page = re.sub(r"\s+", " ", page).strip()

            return "pass", page, "Official page responded"

    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return "fail", "", f"HTTP {exc.code}"
        return "unknown", "", f"HTTP {exc.code}"
    except Exception:
        return "unknown", "", "Page could not be retrieved"

def save_evidence(listing, url, check_type, result, note):
    now = dt.datetime.now(dt.timezone.utc)

    payload = {
        "listing_id": listing["id"],
        "source_url": url,
        "source_hash": listing["source_hash"],
        "check_type": check_type,
        "result": result,
        "evidence_text": note[:2000],
        "checked_at": now.isoformat(),
        "expires_at": (
            now + dt.timedelta(hours=24)
        ).isoformat(),
    }

    api(
        "/rest/v1/earnly_verification_evidence",
        method="POST",
        payload=payload,
    )

def main():
    listings = api(
        "/rest/v1/earnly_discovery_catalog"
        "?select=id,name,url,source_hash"
        "&listing_kind=eq.platform"
        "&review_status=eq.pending_review"
        "&order=id.asc"
        "&limit=50"
    )

    summary = []

    for listing in listings:
        status, text, note = fetch_page(listing["url"])

        save_evidence(
            listing,
            listing["url"],
            "website_availability",
            status,
            note,
        )

        source_results = []

        for source_url in OFFICIAL_SOURCES.get(listing["name"], []):
            source_status, source_text, source_note = fetch_page(
                source_url
            )

            # A fetched page is evidence of accessibility,
            # not proof of eligibility or payment.
            save_evidence(
                listing,
                source_url,
                "official_document_access",
                source_status,
                source_note,
            )

            # Record possible evidence for later structured review.
            # Never turn keyword matches into automatic approval.
            excerpt = source_text[:1000] if source_text else ""

            save_evidence(
                listing,
                source_url,
                "eligibility_document_review",
                "unknown",
                "Official documentation requires structured "
                "eligibility review. Page excerpt: " + excerpt,
            )

            save_evidence(
                listing,
                source_url,
                "payout_document_review",
                "unknown",
                "Official documentation requires structured "
                "payout review. Page excerpt: " + excerpt,
            )

            source_results.append({
                "source": source_url,
                "access": source_status,
            })

        summary.append({
            "name": listing["name"],
            "website": status,
            "documentation": source_results,
        })

    print(json.dumps({
        "checked": len(summary),
        "results": summary,
        "approvals_changed": 0,
        "note": "Evidence collection only; no automatic publication."
    }, indent=2))

if __name__ == "__main__":
    main()
