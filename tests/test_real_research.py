import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('updater',ROOT/'scripts'/'update_opportunities.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class ResearchTests(unittest.TestCase):
    def test_lever_direct_application(self):
        boards=[{'provider':'lever','site_slug':'example','company':'Example'}]
        postings=[{'text':'Remote Support','hostedUrl':'https://jobs.lever.co/example/123','categories':{'location':'Remote'}}]
        with patch.object(mod,'read_json',return_value=boards),patch.object(mod,'fetch_json',return_value=postings):
            rows,errors=mod.lever_records()
        self.assertEqual(errors,[])
        self.assertEqual(rows[0]['application_path'],'employer_application')
        self.assertFalse(rows[0]['verified'])
        self.assertEqual(rows[0]['countries'],['Not verified'])
    def test_lever_bad_slug_not_fetched(self):
        with patch.object(mod,'read_json',return_value=[{'provider':'lever','site_slug':'../bad'}]),patch.object(mod,'fetch_json') as fetch:
            rows,errors=mod.lever_records()
        self.assertEqual(rows,[]);self.assertTrue(errors);fetch.assert_not_called()
    def test_task_rejects_deposit(self):
        item={'name':'Task','url':'https://example.org/task','source_url':'https://example.org/terms','opportunity_type':'individual_task','start_requirements':'Complete task','countries':['CA'],'requires_deposit':True,'requires_seed_phrase':False,'review_status':'human_reviewed'}
        with patch.object(mod,'read_json',return_value=[item]): rows,errors=mod.reviewed_direct_tasks()
        self.assertFalse(rows);self.assertTrue(errors)
    def test_task_requires_human_review(self):
        item={'name':'Task','url':'https://example.org/task','source_url':'https://example.org/terms','opportunity_type':'individual_task','start_requirements':'Complete task','countries':['CA'],'requires_deposit':False,'requires_seed_phrase':False,'review_status':'pending'}
        with patch.object(mod,'read_json',return_value=[item]): rows,errors=mod.reviewed_direct_tasks()
        self.assertFalse(rows);self.assertTrue(errors)
    def test_valid_task_does_not_claim_payout_verified(self):
        item={'name':'Task','url':'https://example.org/task','source_url':'https://example.org/terms','opportunity_type':'individual_task','start_requirements':'Complete task','countries':['CA'],'requires_deposit':False,'requires_seed_phrase':False,'review_status':'human_reviewed'}
        with patch.object(mod,'read_json',return_value=[item]): rows,errors=mod.reviewed_direct_tasks()
        self.assertFalse(errors);self.assertEqual(len(rows),1);self.assertFalse(rows[0]['verified'])
if __name__=='__main__': unittest.main()
