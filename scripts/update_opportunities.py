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
from crypto_hub import reviewed_crypto_records
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'opportunities.json'
ARCHIVE = ROOT / 'opportunities-archive.json'
REPORT = ROOT / 'opportunities-report.json'
NOW = dt.datetime.now(dt.timezone.utc)
STAMP = NOW.isoformat()
MAX_NEW = 20
DIRECT_MAX_PER_BOARD = 40
DIRECT_BOARD_CONFIG = ROOT / 'direct-job-sources.json'
DIRECT_TASK_CONFIG = ROOT / 'direct-tasks-reviewed.json'
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
    item['payout_evidence'] = item.get('payout_evidence_status', 'not_verified')
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

def greenhouse_records():
    """Official Greenhouse public job boards. Configure explicit, reviewed board tokens.

    An open job posting is NOT a promise of employment or immediate work.
    Do not scrape applications, candidate data, or pages behind authentication.
    """
    config=read_json(DIRECT_BOARD_CONFIG, [])
    records=[]; errors=[]
    for board in config[:30]:
        if str(board.get('provider','greenhouse')).lower() != 'greenhouse': continue
        token=str(board.get('board_token') or '').strip()
        if not re.fullmatch(r'[a-zA-Z0-9_-]{2,80}',token):
            errors.append('Invalid board token in direct-job-sources.json'); continue
        try:
            data=fetch_json('https://boards-api.greenhouse.io/v1/boards/'+token+'/jobs?content=true')
            if not isinstance(data,dict) or not isinstance(data.get('jobs'),list):
                raise ValueError('Unexpected Greenhouse response')
            for job in data['jobs'][:DIRECT_MAX_PER_BOARD]:
                url=job.get('absolute_url','')
                if not url_key(url) or not str(job.get('title') or '').strip(): continue
                location=str((job.get('location') or {}).get('name') or 'Not specified')[:160]
                title=str(job['title']).strip()[:180]
                label=(title+' '+str(job.get('content') or '')[:1000]).lower()
                category='ai' if re.search(r'\b(ai trainer|machine learning|data annotat|ai evaluation)\b',label) else 'jobs'
                records.append({'name':title,'company':str(board.get('company') or token)[:140],
                    'category':category,'opportunity_type':'remote_job',
                    'description':'Employer-published job posting. Remote eligibility and application status must be confirmed with the employer.',
                    'url':url,'payout':'Unverified','payment':'Unverified',
                    'countries':['Not verified'],'verified':False,'source':'Greenhouse employer board',
                    'source_location_text':location,'source_published_at':str(job.get('updated_at') or ''),
                    'verification_status':'employer_posted_not_independently_verified',
                    'application_path':'employer_application','start_speed':'application_required',
                    'last_discovered_at':STAMP})
        except Exception as exc:
            errors.append(token+': '+str(exc)[:120])
    return records,errors

def lever_records():
    """Public Lever postings from explicitly configured company slugs.

    Lever postings are employer applications, not immediate paid tasks. Country,
    device suitability and salary must not be guessed from job descriptions.
    """
    records=[]; errors=[]
    for board in read_json(DIRECT_BOARD_CONFIG, [])[:30]:
        if str(board.get('provider','greenhouse')).lower() != 'lever': continue
        slug=str(board.get('site_slug') or '').strip()
        if not re.fullmatch(r'[a-zA-Z0-9_-]{2,80}',slug):
            errors.append('Invalid Lever site slug'); continue
        try:
            data=fetch_json('https://api.lever.co/v0/postings/'+slug+'?mode=json')
            if not isinstance(data,list): raise ValueError('Unexpected Lever response')
            for job in data[:DIRECT_MAX_PER_BOARD]:
                if not isinstance(job,dict): continue
                title=str(job.get('text') or '').strip()[:180]
                url=job.get('hostedUrl') or job.get('applyUrl') or ''
                if not title or not url_key(url): continue
                categories=job.get('categories') or {}
                location=str(categories.get('location') or 'Not specified')[:160]
                records.append({'name':title,'company':str(board.get('company') or slug)[:140],
                  'category':'jobs','opportunity_type':'remote_job',
                  'description':'Employer-published Lever application. Remote status, pay and eligibility require confirmation.',
                  'url':url,'payout':'Unverified','payment':'Unverified','countries':['Not verified'],
                  'verified':False,'source':'Lever employer board','source_location_text':location,
                  'verification_status':'employer_posted_not_independently_verified',
                  'application_path':'employer_application','start_speed':'application_required',
                  'last_discovered_at':STAMP})
        except Exception as exc: errors.append(slug+': '+str(exc)[:120])
    return records,errors


def reviewed_direct_tasks():
    """Individual, manually researched offers. Reject directories and deposit scams.

    A reviewed source is NOT proof of successful payment or guaranteed availability.
    """
    records=[]; rejected=[]
    for row in read_json(DIRECT_TASK_CONFIG,[]):
        name=str(row.get('name') or '').strip()
        url=str(row.get('url') or '').strip()
        kind=str(row.get('opportunity_type') or '')
        evidence=str(row.get('source_url') or '').strip()
        terms=str(row.get('start_requirements') or '').strip()
        if kind not in ('individual_task','individual_study','gaming_reward','crypto_bounty') or not name or not url_key(url) or not url_key(evidence) or not terms:
            rejected.append(name or 'unnamed: missing source, link, requirements or valid type'); continue
        if row.get('requires_deposit') is not False or row.get('requires_seed_phrase') is not False:
            rejected.append(name+': unsafe or unknown deposit/seed requirements'); continue
        if row.get('review_status') != 'human_reviewed':
            rejected.append(name+': human review required'); continue
        countries=row.get('countries')
        if not isinstance(countries,list) or not countries:
            rejected.append(name+': country information required'); continue
        records.append({'name':name[:180], 'company':str(row.get('company') or '')[:140],
          'category':str(row.get('category') or 'general')[:80], 'opportunity_type':kind,
          'description':str(row.get('description') or '')[:1000], 'url':url_key(url),
          'source':str(row.get('source') or 'Official offer page')[:120],
          'source_url':url_key(evidence),'start_requirements':terms[:500],
          'countries':countries[:50], 'device_support':row.get('device_support',[]),
          'payout':str(row.get('payout') or 'Unverified')[:200],
          'payout_evidence_status':str(row.get('payout_evidence_status') or 'not_verified'),
          'verification_status':'human_reviewed_terms_not_payout_verified',
          'verified':False, 'start_speed':'requirements_apply',
          'last_discovered_at':STAMP})
    return records,rejected

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
    stats={'run_at':STAMP,'new_platforms':0,'new_jobs':0,'archived_jobs':0,'page_checks':0,'source_ok':False,'source_error':None,'direct_jobs_added':0,'direct_source_errors':[],'crypto_added':0,'crypto_rejected':[],'lever_added':0,'task_added':0,'task_rejected':[]}
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
    # Prefer actual employer applications over generic platform signups.
    # Only explicitly configured employer boards are fetched.
    try:
        direct_jobs,errors=greenhouse_records()
        stats['direct_source_errors']=errors
        for job in direct_jobs:
            key=url_key(job['url'])
            if key not in seen and key not in archived_keys:
                catalog.append(job);seen.add(key);stats['direct_jobs_added']+=1
    except Exception as exc:
        stats['direct_source_errors']=[str(exc)[:250]]
    lever_jobs,lever_errors=lever_records()
    stats['direct_source_errors'].extend(lever_errors)
    for job in lever_jobs:
        key=url_key(job['url'])
        if key not in seen and key not in archived_keys:
            catalog.append(job);seen.add(key);stats['lever_added']+=1
    tasks,rejected=reviewed_direct_tasks()
    stats['task_rejected']=rejected
    for task in tasks:
        key=url_key(task['url'])
        if key not in seen and key not in archived_keys:
            catalog.append(task);seen.add(key);stats['task_added']+=1
    # Crypto listings must be reviewed individual offers, never guessed from platform directories.
    crypto_offers,crypto_rejected=reviewed_crypto_records(ROOT / 'crypto-opportunities-reviewed.json')
    stats['crypto_rejected']=crypto_rejected
    for offer in crypto_offers:
        key=url_key(offer['url'])
        if key not in seen and key not in archived_keys:
            catalog.append(offer);seen.add(key);stats['crypto_added']+=1
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
    # Do not claim employer postings are currently open when they have gone stale.
    for item in kept:
        if item.get('source')=='Greenhouse employer board':
            age=parse_date(item.get('last_discovered_at'))
            if age and (NOW-age).days>=STALE_DAYS:
                item['verification_status']='stale_employer_posting_review_needed'
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
