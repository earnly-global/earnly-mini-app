
#!/usr/bin/env python3
"""Earnly V3: collect targeted evidence without automatic approval."""

import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlencode

BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": KEY,
    "Authorization": "Bearer " + KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Candidate official pages, not confirmed evidence of specific terms.
SOURCES = {
    "CloudResearch Connect": [
        "https://connect-participant-help.cloudresearch.com/hc/en-us"
    ],
    "Freecash": ["https://freecash.com"],
    "PlaytestCloud": ["https://players.playtestcloud.com"],
    "Respondent": ["https://www.respondent.io"],
    "Swagbucks": ["https://www.swagbucks.com"],
    "UserTesting": [
        "https://www.usertesting.com/get-paid-to-test"
    ],
}

PATTERNS = {
    "country_eligibility": (
        r"\b(canada|canadian|eligible countries|"
        r"supported countries|countries supported|"
        r"country restrictions|residents of)\b"
    ),
    "payout_terms": (
        r"\b(paypal|cashout|cash out|withdrawal|"
        r"minimum payout|gift card|payment method|"
        r"paid via|payout threshold)\b"
    ),
    "registration_requirements": (
        r"\b(18 years|age requirement|sign up|"
        r"register|identity verification|"
        r"account verification|waitlist|"
        r"application process)\b"
    ),
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
        raw = response.read()
        return json.loads(raw) if raw else None


def fetch_page(url):
    parsed = urlsplit(url)

    if parsed.scheme != "https" or not parsed.hostname:
        return "fail", "", "Invalid HTTPS URL"

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EarnlyVerifier/3.0",
                "Accept": "text/html",
            },
        )

        with urllib.request.urlopen(
            request, timeout=12
        ) as response:
            final_url = response.geturl()

            # Do not accept a redirect to an unrelated domain.
            original = urlsplit(url).hostname or ""
            final = urlsplit(final_url)

            if (
                final.scheme != "https"
                or not final.hostname
                or not (
                    final.hostname == original
                    or final.hostname.endswith("." + original)
                )
            ):
                return "unknown", "", "Redirect requires review"

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" not in content_type:
                return "unknown", "", "Not an HTML page"

            raw = response.read(500_001)

            if len(raw) > 500_000:
                return "unknown", "", "Page too large"

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )
            page = raw.decode(charset, errors="replace")

        page = re.sub(
            r"<(script|style|noscript)\b[^>]*>.*?</\1>",
            " ",
            page,
            flags=re.I | re.S,
        )
        page = re.sub(r"<[^>]+>", " ", page)
        page = html.unescape(page)
        page = re.sub(r"\s+", " ", page).strip()

        if not page:
            return "unknown", "", "No readable text"

        return "pass", page, "HTML page accessible"

    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return "fail", "", f"HTTP {exc.code}"
        return "unknown", "", f"HTTP {exc.code}"
    except Exception as exc:
        return "unknown", "", (
            f"Fetch error: {type(exc).__name__}"
        )


def find_excerpts(text, pattern, limit=3):
    excerpts = []
    for match in re.finditer(pattern, text, re.I):
        start = max(0, match.start() - 130)
        end = min(len(text), match.end() + 220)
        excerpt = text[start:end].strip()

        if excerpt not in excerpts:
            excerpts.append(excerpt[:350])

        if len(excerpts) >= limit:
            break

    return excerpts


def save_evidence(listing, url, kind, result, note):
    now = dt.datetime.now(dt.timezone.utc)

    payload = {
        "listing_id": listing["id"],
        "source_url": url,
        "source_hash": listing["source_hash"],
        "check_type": kind,
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
    query = urlencode({
        "select": "id,name,url,source_hash",
        "listing_kind": "eq.platform",
        "review_status": "eq.pending_review",
        "order": "id.asc",
        "limit": "50",
    })

    listings = api(
        "/rest/v1/earnly_discovery_catalog?" + query
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

        sources = []

        for source_url in SOURCES.get(
            listing["name"], []
        ):
            source_status, source_text, source_note = (
                fetch_page(source_url)
            )

            save_evidence(
                listing,
                source_url,
                "official_document_access",
                source_status,
                source_note,
            )

            found = {}

            for kind, pattern in PATTERNS.items():
                excerpts = (
                    find_excerpts(source_text, pattern)
                    if source_status == "pass"
                    else []
                )

                note = json.dumps({
                    "page_access": source_status,
                    "candidate_excerpts": excerpts,
                    "assessment": (
                        "Evidence requires contextual validation; "
                        "keyword matches do not establish eligibility "
                        "or payment."
                    ),
                }, ensure_ascii=False)

                # Deliberately unknown: no unsupported approvals.
                save_evidence(
                    listing,
                    source_url,
                    kind,
                    "unknown",
                    note,
                )

                found[kind] = len(excerpts)

            sources.append({
                "url": source_url,
                "access": source_status,
                "candidate_excerpts": found,
            })

        summary.append({
            "name": listing["name"],
            "website": status,
            "sources": sources,
        })

    print(json.dumps({
        "checked": len(summary),
        "results": summary,
        "approvals_changed": 0,
        "note": (
            "Candidate evidence only. "
            "No automatic publication."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
