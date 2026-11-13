import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from crypto_hub import reviewed_crypto_records
BASE={'name':'Example paid mobile task','url':'https://example.org/tasks/123','official_source_url':'https://example.org/tasks/123','opportunity_type':'crypto_microtask','start_requirement':'apply','payout_evidence_status':'terms_reviewed','countries':['CA'],'device':'phone','last_reviewed_at':'2026-11-12','requires_deposit':False,'description':'Paid online work'}
class TestCrypto(unittest.TestCase):
 def run_items(self,items):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'input.json';p.write_text(json.dumps(items));return reviewed_crypto_records(p)
 def test_valid(self):
  good,bad=self.run_items([BASE]);self.assertEqual(len(good),1);self.assertEqual(bad,[]);self.assertFalse(good[0]['verified'])
 def test_deposit_rejected(self):
  good,bad=self.run_items([{**BASE,'requires_deposit':True}]);self.assertFalse(good);self.assertTrue(bad)
 def test_seed_phrase_rejected(self):
  good,bad=self.run_items([{**BASE,'description':'Send seed phrase'}]);self.assertFalse(good)
 def test_games_require_withdrawal_review(self):
  good,bad=self.run_items([{**BASE,'opportunity_type':'crypto_game'}]);self.assertFalse(good)
 def test_payout_evidence_needs_link(self):
  good,bad=self.run_items([{**BASE,'payout_evidence_status':'payout_evidence_reviewed'}]);self.assertFalse(good)
 def test_https_required(self):
  good,bad=self.run_items([{**BASE,'url':'http://example.org'}]);self.assertFalse(good)
if __name__=='__main__':unittest.main()
