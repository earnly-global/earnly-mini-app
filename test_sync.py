import unittest
from scripts.sync_discovery import normalize

class SyncTests(unittest.TestCase):
    def test_platform(self):
        self.assertEqual(normalize([{'name':'Prolific','url':'https://example.org','opportunity_type':'earning_platform'}])[0]['listing_kind'],'platform')
    def test_job(self):
        self.assertEqual(normalize([{'name':'Role','url':'https://example.org'}])[0]['listing_kind'],'remote_job')
    def test_duplicate(self):
        a={'name':'Role','url':'https://example.org'}
        self.assertEqual(len(normalize([a,a])),1)
    def test_insecure_url(self):
        with self.assertRaises(ValueError): normalize([{'name':'Bad','url':'http://example.org'}])
    def test_empty(self):
        with self.assertRaises(ValueError): normalize([])

if __name__ == '__main__': unittest.main()
