#!/usr/bin/env python3
"""Separate, non-destructive Earnly catalog sync. Requires service-role key only in CI secrets."""
import hashlib
import json
import os
import sys
import urllib.request
from urllib.parse import urlparse


def normalize(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError('Expected 1..1000 opportunities')
    out = []
    seen = set()
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError('Invalid opportunity')
        url = str(item.get('url') or '').strip()
        name = str(item.get('name') or '').strip()
        u = urlparse(url)
        if not name or u.scheme != 'https' or not u.netloc or u.username or u.password:
            raise ValueError('Invalid name or HTTPS URL')
        if url in seen:
            continue
        seen.add(url)
        kind = 'platform' if item.get('opportunity_type') == 'earning_platform' else 'remote_job'
        record = {
            'name': name[:300], 'company': str(item.get('company') or '')[:300],
            'description': str(item.get('description') or '')[:4000], 'url': url,
            'category': str(item.get('category') or 'other')[:80],
            'countries': item.get('countries') if isinstance(item.get('countries'), list) else [],
            'payout': str(item.get('payout') or 'Unverified')[:200],
            'source': str(item.get('source') or 'Unknown')[:200], 'listing_kind': kind,
        }
        record['hash'] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        out.append(record)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'opportunities.json'
    with open(path, encoding='utf-8') as f:
        records = normalize(json.load(f))
    print(f'Validated {len(records)} unique listings. Kind counts: '
          f'{ {kind: sum(r["listing_kind"] == kind for r in records) for kind in ("platform", "remote_job")} }')
    if '--apply' not in sys.argv:
        print('DRY RUN ONLY. Add --apply to write to Supabase.'); return
    base = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    if urlparse(base).scheme != 'https':
        raise ValueError('Supabase URL must be HTTPS')
    data = json.dumps({'p_rows': records}).encode()
    req = urllib.request.Request(base + '/rest/v1/rpc/earnly_sync_discovery_catalog', data=data, method='POST', headers={
        'apikey': key, 'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        print('Supabase sync result:', response.read().decode())


if __name__ == '__main__':
    main()
