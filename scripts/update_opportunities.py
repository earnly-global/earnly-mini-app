#!/usr/bin/env python3
"""Earnly V2: conservative, auditable public catalog updater (stdlib only)."""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'opportunities.json'
ARCHIVE = ROOT / 'opportunities-archive.json'
REPORT = ROOT / 'opportunities-report.json'
NOW = dt.datetime.now(dt.timezone.utc)
STAMP = NOW.isoformat()
MAX_NEW = 20
STALE_DAYS = 45
USER_AGENT = 'EarnlyCatalog/3.0 (public catalog; source attribution)'

# These are PLATFORM HOME/REGISTRATION pages, not individual live paid studies.
# A platform being listed does NOT mean the user has an available task.
PLATFORMS = [
 ('Prolific','surveys','https://www.prolific.com/participants','Academic research participation'),
 ('CloudResearch Connect','surveys','https://connect.cloudresearch.com','Research participation platform'),
 ('User Interviews','surveys','https://www.userinterviews.com','Research interviews and studies'),
 ('Respondent','surveys','https://www.respondent.io','Research interview platform'),
 ('UserTesting','websites','https://www.usertesting.com/get-paid-to-test','Website and app usability testing'),
 ('PlaytestCloud','gaming','https://players.playtestcloud.com','Game playtesting platform'),
 ('Freecash','gaming','https://freecash.com','Rewards and game offers platform'),
 ('Swagbucks','gaming','https://www.swagbucks.com','Rewards and surveys platform'),
]

def url_key(value):
    if not isinstance(value, str): return ''
    try:
        p = urlsplit(value.strip())
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: return ''
        host = p.hostname.lower().removeprefix('www.')
        path = p.path.rstrip('/') or '/'
        # Remove tracking parameters, retain meaningful parameters; deterministic ordering.
        query = urlencode(sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
            if not k.lower().startswith('utm_') and k.lower() not in ('ref','fbclid','gclid')))
        return urlunsplit(('https',host,path,query,''))
    except ValueError: return ''

def read_json(path, default):
    if not path.exists(): return default
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result,list): raise ValueError(f'{path.name} must be a JSON array')
    return [x for x in result if isinstance(x,dict)]

def save_json(path, value):
    rendered = json.dumps(value,indent=2,ensure_ascii=False,sort_keys=False)+'\n'
    if not path.exists() or path.read_text(encoding='utf-8') != rendered:
        path.write_text(rendered,encoding='utf-8')
        return True
    return False

def fetch_json(url):
    req = urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=18) as response:
        if response.status != 200: raise RuntimeError(f'HTTP {response.status}')
        return json.loads(response.read(3_000_000))

def probe(url):
    """Checks whether a landing page responds; NEVER asserts pay, legitimacy or open tasks."""
    try:
        req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Range':'bytes=0-0'},method='GET')
        with urllib.request.urlopen(req,timeout=8) as response:
            code=response.status
            return 'reachable' if 200 <= code < 400 else 'unknown'
    except urllib.error.HTTPError as e:
        if e.code in (404,410): return 'not_found'
        return 'unknown'  # 403/429/5xx may be bot protection or transient
    except Exception:
        return 'unknown'

def normalize(item):
    item=dict(item)
    item['category']={'games':'gaming','testing':'websites'}.get(str(item.get('category','')).lower(),str(item.get('category') or 'general').lower())
    item['verified']=False if item.get('verification_status') not in ('manually_verified',) else bool(item.get('verified'))
    item.setdefault('opportunity_type','remote_job' if item.get('source') in ('Remotive','Remote OK') else 'earning_platform')
    item.setdefault('verification_status','not_independently_verified')
    return item

def quality_fields(item):
    """Conservative metadata; never infer a payout, task duration or eligibility."""
    item['quality_type'] = item.get('opportunity_type', 'earning_platform')
    item['payout_evidence'] = 'not_verified'
    item['eligibility_evidence'] = 'not_verified'
    item['task_availability'] = 'not_verified'
    if item.get('page_check_status') == 'reachable':
        item['website_check_note'] = 'Landing page responded; individual tasks and payouts not verified'
    elif item.get('page_check_status') == 'not_found':
        item['website_check_note'] = 'Landing page returned HTTP 404/410; manual review required'
    else:
        item['website_check_note'] = 'Website availability unknown or not checked'
    return item

def platform_records():
    records=[]
    for name,cat,url,description in PLATFORMS:
        records.append({'name':name,'category':cat,'url':url,'description':description,
          'opportunity_type':'earning_platform','payout':'Unverified','payment':'Unverified',
          'countries':['Not verified'],'verified':False,'source':'Official platform website',
          'verification_status':'platform_catalog_not_live_offer'})
    return records

def remotive_records():
    data=fetch_json('https://remotive.com/api/remote-jobs?limit=100')
    if not isinstance(data,dict) or not isinstance(data.get('jobs'),list): raise ValueError('Unexpected Remotive response')
    output=[]
    for job in data['jobs']:
        if not isinstance(job,dict): continue
        url=job.get('url','')
        if not url_key(url) or not str(job.get('title') or '').strip(): continue
        title=str(job['title']).strip()[:180]
        category_text=(str(job.get('category',''))+' '+title).lower()
        cat='ai' if re.search(r'\b(ai|machine learning|annotation|data label)\b',category_text) else 'websites' if re.search(r'\b(qa|testing|tester|usability)\b',category_text) else 'jobs'
        output.append({'name':title,'company':str(job.get('company_name') or 'Not specified')[:140],
          'category':cat,'opportunity_type':'remote_job',
          'description':'Remote employment listing, not a paid survey. Confirm eligibility and whether applications remain open on Remotive.',
          'url':url,'payout':'Unverified','payment':'Unverified','countries':['Not verified'],
          'verified':False,'source':'Remotive','source_location_text':str(job.get('candidate_required_location') or 'Not specified')[:140],
          'source_published_at':str(job.get('publication_date') or ''),
          'verification_status':'source_listed_not_independently_verified','last_discovered_at':STAMP})
        if len(output)>=MAX_NEW: break
    return output

def parse_date(value):
    if not isinstance(value,str) or not value.strip(): return None
    try:
        date=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if date.tzinfo is None: date=date.replace(tzinfo=dt.timezone.utc)
        return date.astimezone(dt.timezone.utc)
    except ValueError: return None

def main():
    catalog=[normalize(x) for x in read_json(CATALOG,[])]
    archive=read_json(ARCHIVE,[])
    archived_keys={url_key(x.get('url')) for x in archive}
    seen={url_key(x.get('url')) for x in catalog if url_key(x.get('url'))}
    stats={'run_at':STAMP,'new_platforms':0,'new_jobs':0,'archived_jobs':0,'page_checks':0,'source_ok':False,'source_error':None}
    for p in platform_records():
        key=url_key(p['url'])
        if key not in seen and key not in archived_keys:
            p['last_discovered_at']=STAMP
            catalog.append(p); seen.add(key);stats['new_platforms']+=1
    # Only archive remote jobs if a fresh, successful source snapshot no longer includes them,
    # AND they are older than 45 days. Never archive due to network failure alone.
    live_keys=set()
    try:
        jobs=remotive_records()
        stats['source_ok']=True
        live_keys={url_key(x['url']) for x in jobs}
        for job in jobs:
            key=url_key(job['url'])
            if key not in seen and key not in archived_keys:
                catalog.append(job);seen.add(key);stats['new_jobs']+=1
    except Exception as exc:
        stats['source_error']=str(exc)[:250]
        print('WARNING: Remotive source unavailable; no source-based archiving',file=sys.stderr)
    kept=[]
    for item in catalog:
        key=url_key(item.get('url'))
        is_remotive=item.get('source')=='Remotive' and item.get('opportunity_type')=='remote_job'
        published=parse_date(item.get('source_published_at'))
        discovered=parse_date(item.get('last_discovered_at'))
        date=published or discovered
        aged=date is not None and (NOW-date).days>=STALE_DAYS
        # Snapshot only contains the first 20 jobs; absence is NOT evidence of expiration.
        # We archive by age, not by absence, and explicitly label it stale, not closed.
        if is_remotive and aged:
            item['archive_reason']='older_than_45_days_unconfirmed_open'
            item['archived_at']=STAMP
            if key not in archived_keys:
                archive.append(item);archived_keys.add(key)
            stats['archived_jobs']+=1
        else:
            kept.append(item)
    # Probe a bounded number of official platform homepages, never scrape participant dashboards.
    for item in kept:
        if item.get('opportunity_type')=='earning_platform' and item.get('name') in {x[0] for x in PLATFORMS}:
            status=probe(item.get('url',''))
            item['page_check_status']=status
            item['page_checked_at']=STAMP
            stats['page_checks']+=1
            if status=='not_found':
                item['verification_status']='platform_page_not_found_review_needed'
            else:
                item['verification_status']='platform_catalog_not_live_offer'
            item['verified']=False
    # Dedupe existing duplicates, preferring the earliest catalog entry.
    deduped=[]; keys=set()
    for item in kept:
        key=url_key(item.get('url'))
        if not key or key in keys: continue
        keys.add(key);deduped.append(item)
    deduped=[quality_fields(item) for item in deduped]
    stats['quality_counts']={'platform_pages':sum(x.get('opportunity_type')=='earning_platform' for x in deduped),'remote_jobs':sum(x.get('opportunity_type')=='remote_job' for x in deduped),'individual_tasks':sum(x.get('opportunity_type') in ('individual_task','individual_study') for x in deduped),'needs_page_review':sum(x.get('page_check_status')=='not_found' for x in deduped)}
    stats['catalog_total']=len(deduped)
    stats['archive_total']=len(archive)
    save_json(CATALOG,deduped)
    save_json(ARCHIVE,archive)
    save_json(REPORT,stats)
    print(json.dumps(stats,indent=2))

if __name__=='__main__': main()
