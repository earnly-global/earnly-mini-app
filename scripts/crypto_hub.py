"""Conservative, reviewed crypto opportunities. No automatic endorsement of rewards."""
import json
from pathlib import Path
from urllib.parse import urlsplit

KINDS={'crypto_job','crypto_bounty','crypto_game','crypto_microtask','crypto_research','crypto_reward'}
START={'apply','task_available','registration_required','screening_required'}
EVIDENCE={'terms_reviewed','payout_evidence_reviewed','unverified'}
DANGER=('deposit to unlock','pay to withdraw','guaranteed profit','guaranteed returns','send seed phrase','recovery phrase','private key','wallet seed')

def reviewed_crypto_records(path):
    """Only hand-reviewed direct offers. Empty file is intentionally valid."""
    entries=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(entries,list): raise ValueError('crypto-opportunities-reviewed.json must be a list')
    results=[]; rejected=[]
    for index,x in enumerate(entries):
        try:
            if not isinstance(x,dict): raise ValueError('invalid object')
            name=str(x.get('name','')).strip()
            url=str(x.get('url','')).strip()
            p=urlsplit(url)
            if not name or len(name)>180 or p.scheme!='https' or not p.hostname or p.username or p.password: raise ValueError('name or HTTPS link missing')
            if x.get('opportunity_type') not in KINDS: raise ValueError('unsupported crypto category')
            if x.get('start_requirement') not in START: raise ValueError('start requirement missing')
            if x.get('payout_evidence_status') not in EVIDENCE: raise ValueError('evidence status missing')
            if not x.get('official_source_url') or urlsplit(str(x['official_source_url'])).scheme!='https': raise ValueError('official source missing')
            if not isinstance(x.get('countries'),list) or not x['countries']: raise ValueError('country eligibility missing')
            if x.get('device') not in ('phone','both','laptop'): raise ValueError('device requirement missing')
            if not x.get('last_reviewed_at'): raise ValueError('review timestamp missing')
            if x.get('requires_deposit') is not False: raise ValueError('deposit required or unknown')
            blob=' '.join(str(x.get(k,'')) for k in ('name','description','payout','requirements')).lower()
            if any(term in blob for term in DANGER): raise ValueError('high-risk claim')
            if x.get('opportunity_type')=='crypto_game' and x.get('withdrawal_terms_reviewed') is not True: raise ValueError('game withdrawal terms not reviewed')
            if x.get('payout_evidence_status')=='payout_evidence_reviewed' and not x.get('payout_evidence_url'): raise ValueError('payout evidence link missing')
            # The public catalog can render these fields. No earnings or eligibility inferred.
            item={k:x[k] for k in ('name','url','opportunity_type','start_requirement','payout_evidence_status','official_source_url','countries','device','last_reviewed_at')}
            item.update({'category':'crypto','description':str(x.get('description',''))[:2000],
                'payout':str(x.get('payout') or 'Unverified')[:160],
                'payment':str(x.get('payment') or 'Unverified')[:100],
                'company':str(x.get('company') or '')[:140],
                'source':'Earnly reviewed crypto opportunity',
                'verified':False, 'verification_status':'manually_reviewed_terms_not_payout_guaranteed',
                'application_path':'direct_offer','crypto_kind':x['opportunity_type'],
                'phone_compatible':x['device'] in ('phone','both'),
                'start_speed':x['start_requirement'],
                'payout_evidence_url':str(x.get('payout_evidence_url') or ''),
                'requires_deposit':False})
            results.append(item)
        except (ValueError,TypeError,KeyError) as exc: rejected.append({'row':index+1,'reason':str(exc)})
    return results,rejected
