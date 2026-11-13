import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('updater', ROOT/'scripts'/'update_opportunities.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DirectJobTests(unittest.TestCase):
    def test_employer_posting_not_claimed_verified(self):
        jobs = {'jobs':[{'title':'Remote QA Analyst','absolute_url':'https://boards.greenhouse.io/example/jobs/123','location':{'name':'Canada'},'updated_at':'2026-11-12T00:00:00Z'}]}
        with patch.object(mod,'read_json',return_value=[{'board_token':'example','company':'Example Co'}]), patch.object(mod,'fetch_json',return_value=jobs):
            rows, errors=mod.greenhouse_records()
        self.assertFalse(errors)
        self.assertEqual(rows[0]['application_path'],'employer_application')
        self.assertFalse(rows[0]['verified'])
        self.assertEqual(rows[0]['countries'],['Not verified'])
        self.assertEqual(rows[0]['start_speed'],'application_required')
    def test_invalid_board_token_not_fetched(self):
        with patch.object(mod,'read_json',return_value=[{'board_token':'../secret','company':'Invalid'}]), patch.object(mod,'fetch_json') as fetch:
            rows,errors=mod.greenhouse_records()
        self.assertEqual(rows,[])
        self.assertTrue(errors)
        fetch.assert_not_called()

if __name__=='__main__': unittest.main()
