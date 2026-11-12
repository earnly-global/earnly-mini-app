#!/usr/bin/env python3
"""Conservative Earnly catalog updater. No payout/eligibility verification claims."""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'opportunities.json'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
API = 'https://remotive.com/api/remote-jobs?limit=100'
MAX_NEW = 30

def clean_url(value):
    if not isinstance(value, str): return ''
    try:
        p = urlsplit(value.strip())
        if p.scheme not in ('http','https') or not p.netloc: return ''
        return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/') or '/', '', ''))
    except ValueError: return ''

def norm_category(cat):
    return {'games':'gaming','testing':'websites'}.get(str(cat or '').lower(),str(cat or 'general').lower())

def existing():
    if not CATALOG.exists(): return []
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if isinstance(data,dict): data=data.get('opportunities',[])
    if not isinstance(data,list): raise ValueError('Catalog must be an array')
    return [x for x in data if isinstance(x,dict) and clean_url(x.get('url'))]

def discover_remotive():
    req = urllib.request.Request(API,headers={'User-Agent':'EarnlyCatalogBot/1.0 (public listing aggregation)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if r.status != 200: raise RuntimeError(f'Remotive returned {r.status}')
        body = r.read(2_000_000)
    jobs=json.loads(body).get('jobs',[])
    if not isinstance(jobs,list): raise ValueError('Unexpected Remotive response')
    found=[]
    for job in jobs:
        if not isinstance(job,dict): continue
        url=clean_url(job.get('url'))
        name=str(job.get('title') or '').strip()[:180]
        if not url or not name: continue
        category_text=(str(job.get('category') or '')+' '+name).lower()
        cat='ai' if re.search(r'\b(ai|machine learning|annotation|data label)\b',category_text) else 'websites' if re.search(r'\b(qa|testing|tester|usability)\b',category_text) else 'jobs'
        company=str(job.get('company_name') or 'Not specified')[:140]
        location=str(job.get('candidate_required_location') or 'Not specified')[:140]
        found.append({
            'name':name,'company':company,'category':cat,'opportunity_type':'remote_job',
            'description':'Remote job listing. Check qualifications, location restrictions, and application status on the provider page.',
            'url':url,'payout':'Unverified','payment':'Unverified',
            'countries':['Not verified'],'verified':False,'source':'Remotive',
            'source_location_text':location,'source_published_at':str(job.get('publication_date') or ''),
            'last_discovered_at':NOW,'verification_status':'discovered_not_independently_verified'
        })
        if len(found)>=MAX_NEW: break
    return found

def main():
    catalog=existing()
    seen={clean_url(x.get('url')) for x in catalog}
    # Keep the curated catalog and existing listings. Never silently remove entries.
    for item in catalog:
        item['category']=norm_category(item.get('category'))
        item['verified']=bool(item.get('verified',False))
        item.setdefault('verification_status','not_independently_verified')
        if 'opportunity_type' not in item:
            item['opportunity_type']='remote_job' if item.get('source') in ('Remote OK','Remotive') else 'earning_platform'
    try:
        discovered=discover_remotive()
    except Exception as exc:
        print(f'WARNING: discovery unavailable ({exc}); preserving existing catalog',file=sys.stderr)
        discovered=[]
    added=0
    for item in discovered:
        key=clean_url(item['url'])
        if key in seen: continue
        catalog.append(item);seen.add(key);added+=1
    # Stable output: only write when new records or normalization actually change data.
    output=json.dumps(catalog,ensure_ascii=False,indent=2)+'\n'
    if not CATALOG.exists() or CATALOG.read_text(encoding='utf-8')!=output:
        CATALOG.write_text(output,encoding='utf-8')
    print(f'Catalog total={len(catalog)}; newly discovered={added}; timestamp={NOW}')

if __name__=='__main__': main()
