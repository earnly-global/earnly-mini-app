
#!/usr/bin/env python3
"""Earnly V4: configurable official-source evidence collection.

Reads verification-sources.json from the repository root.
Collects candidate evidence without automatically approving listings.
"""

import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlencode

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "verification-sources.json"

BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": KEY,
    "Authorization": "Bearer " + KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
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

SOURCE_CATEGORIES = {
    "country_eligibility": "country_eligibility",
    "payout_terms": "payout_terms",
    "registration": "registration_requirements",
}


def load_sources():
    """Load and validate the official-source configuration."""
    with CONFIG_PATH.open(encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "verification-sources.json must be an object"
        )

    for platform, categories in config.items():
        if not isinstance(categories, dict):
            raise ValueError(
                f"Invalid source categories for {platform}"
            )

        for category, urls in categories.items():
            if category not in SOURCE_CATEGORIES:
                raise ValueError(
                    f"Unknown source category: {category}"
                )

            if not isinstance(urls, list):
                raise ValueError(
                    f"{platform}/{category} must be a list"
                )

            for url in urls:
                if not isinstance(url, str):
                    raise ValueError(
                        "Source URL must be a string"
                    )

                parsed = urlsplit(url)

                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                ):
                    raise ValueError(
                        f"Invalid source URL: {url}"
                    )

    return config


def api(path, method="GET", payload=None):
    data = (
        None
        if payload is None
        else json.dumps(payload).encode("utf-8")
    )

    request = urllib.request.Request(
        BASE + path,
        data=data,
        headers=HEADERS,
        method=method,
    )

    with urllib.request.urlopen(
        request, timeout=30
    ) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def fetch_page(url):
    """Retrieve readable HTML without treating access as proof."""
    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return "fail", "", "Invalid HTTPS URL"

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EarnlyVerifier/4.0",
                "Accept": "text/html",
            },
        )

        with urllib.request.urlopen(
            request, timeout=12
        ) as response:
            final_url = response.geturl()

            original_host = parsed.hostname
            final = urlsplit(final_url)

            if (
                final.scheme != "https"
                or not final.hostname
                or not (
                    final.hostname == original_host
                    or final.hostname.endswith(
                        "." + original_host
                    )
                )
            ):
                return (
                    "unknown",
                    "",
                    "Cross-domain redirect requires review",
                )

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" not in content_type:
                return (
                    "unknown",
                    "",
                    "Response is not HTML",
                )

            raw = response.read(500_001)

            if len(raw) > 500_000:
                return (
                    "unknown",
                    "",
                    "Page exceeds size limit",
                )

            charset = (
                response.headers.get_content_charset()
                or "utf-8"
            )

            page = raw.decode(
                charset, errors="replace"
            )

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
            return (
                "unknown",
                "",
                "No readable text",
            )

        return "pass", page, "HTML page accessible"

    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return "fail", "", f"HTTP {exc.code}"

        return "unknown", "", f"HTTP {exc.code}"

    except Exception as exc:
        return (
            "unknown",
            "",
            f"Fetch error: {type(exc).__name__}",
        )


def find_excerpts(text, pattern, limit=3):
    """Extract candidate passages, not verified claims."""
    excerpts = []

    for match in re.finditer(pattern, text, re.I):
        start = max(0, match.start() - 130)
        end = min(len(text), match.end() + 220)

        excerpt = text[start:end].strip()
        excerpt = excerpt[:350]

        if excerpt and excerpt not in excerpts:
            excerpts.append(excerpt)

        if len(excerpts) >= limit:
            break

    return excerpts


def save_evidence(
    listing,
    url,
    check_type,
    result,
    note,
):
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


def collect_source_evidence(
    listing,
    source_url,
    categories,
):
    """Check one source and record only its configured categories."""
    status, text, note = fetch_page(source_url)

    save_evidence(
        listing,
        source_url,
        "official_document_access",
        status,
        note,
    )

    counts = {}

    for category in categories:
        check_type = SOURCE_CATEGORIES[category]
        pattern = PATTERNS[check_type]

        excerpts = (
            find_excerpts(text, pattern)
            if status == "pass"
            else []
        )

        evidence = {
            "source_category": category,
            "page_access": status,
            "candidate_excerpts": excerpts,
            "assessment": (
                "Candidate evidence only. "
                "Contextual validation required. "
                "No eligibility or payout claim confirmed."
            ),
        }

        save_evidence(
            listing,
            source_url,
            check_type,
            "unknown",
            json.dumps(
                evidence, ensure_ascii=False
            ),
        )

        counts[check_type] = len(excerpts)

    return {
        "url": source_url,
        "access": status,
        "candidate_excerpts": counts,
    }


def main():
    sources = load_sources()

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
        website_status, _, website_note = (
            fetch_page(listing["url"])
        )

        save_evidence(
            listing,
            listing["url"],
            "website_availability",
            website_status,
            website_note,
        )

        platform_sources = sources.get(
            listing["name"], {}
        )

        # Group identical URLs so each is fetched once.
        url_categories = {}

        for category, urls in platform_sources.items():
            for url in urls:
                url_categories.setdefault(
                    url, set()
                ).add(category)

        source_results = []

        for source_url, categories in (
            url_categories.items()
        ):
            source_results.append(
                collect_source_evidence(
                    listing,
                    source_url,
                    sorted(categories),
                )
            )

        summary.append({
            "name": listing["name"],
            "website": website_status,
            "sources": source_results,
        })

    print(json.dumps({
        "checked": len(summary),
        "results": summary,
        "approvals_changed": 0,
        "note": (
            "V4 source-specific candidate evidence "
            "collection completed. "
            "No automatic publication."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
