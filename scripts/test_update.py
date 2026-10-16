"""Offline regression tests for unattended publishing and historical integrity."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import update


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reports = Path(self.tmp.name)
        self.previous = update.load(update.REPORTS / 'latest.json')
        self.previous['date'] = '2026-10-16'
        self.previous['edition'] = 'AM'
        self.previous['freshness'].pop('method', None)
        self.previous['evidenceUpdates'] = [{
            'title': 'Historical release', 'publisher': 'Nasdaq',
            'url': 'https://www.nasdaq.com/historical-release',
            'publishedAt': '2026-10-15', 'summary': 'Original record',
            'collector': 'Nasdaq', 'checkedAt': '2026-10-15T18:30:00+08:00',
        }]
        update.save(self.reports / 'latest.json', self.previous)
        update.save(self.reports / '2026-10-16-AM.json', self.previous)
        update.save(self.reports / 'index.json', {'entries': [{
            'id': '2026-10-16-AM', **{k: self.previous[k] for k in ('date', 'edition', 'title', 'publishedAt')},
        }]})
        for name, value in [('DATE', '2026-10-16'), ('EDITION', 'AM'), ('STAMP', '2026-10-16T11:00:00+08:00')]:
            p = patch.object(update, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.successes = {
            '中证指数': {
                'market': {'code': 'CSI 300', 'value': 4000, 'change': 1, 'changeUnit': '%',
                           'asOf': '2026-10-16 10:59:00', 'status': '官方行情 · 以显示时点为准', 'sourceIds': ['live-csi']},
                'sources': [update.source('live-csi', 'Test quote', '中证指数', 'https://www.csindex.com.cn/', '2026-10-16', '2026-10-16')],
            },
            '国家统计局': {
                'evidence': [{'title': 'Official title', 'publisher': '国家统计局', 'url': 'https://www.stats.gov.cn/test.html',
                              'publishedAt': '2026-10-16', 'summary': '官方正文已获取。', 'summaryKind': '采集说明'}],
                'sources': [update.source('test-release', 'Official title', '国家统计局', 'https://www.stats.gov.cn/test.html', '2026-10-16', '2025')],
            },
        }

    def run_publish(self, successes=None, failures=None):
        update.publish(copy.deepcopy(self.successes if successes is None else successes), failures or {}, self.reports)
        return update.load(self.reports / 'latest.json')

    def test_preserves_research_and_snapshots_same_edition(self):
        result = self.run_publish()
        for field in ('conclusions', 'macro', 'flow', 'ideas', 'companies', 'assets', 'strategy', 'tracking'):
            self.assertEqual(result[field], self.previous[field], field)
        self.assertEqual(result['freshness']['researchUpdatedAt'], self.previous['freshness']['researchUpdatedAt'])
        self.assertEqual(result['freshness']['method'], 'script')
        revisions = list((self.reports / 'revisions').glob('*.json'))
        self.assertEqual(len(revisions), 1)
        self.assertEqual(update.load(revisions[0]), self.previous)
        self.assertEqual(result, update.load(self.reports / '2026-10-16-AM.json'))
        sources = {s['id']: s for s in result['sources']}
        for source in self.previous['sources']:
            if source['id'] in sources:
                self.assertEqual(sources[source['id']], source)
        self.assertNotEqual(result['markets'][0]['sourceIds'], ['live-csi'])

    def test_repeated_run_is_idempotent(self):
        self.run_publish()
        before = (self.reports / 'latest.json').read_bytes()
        with patch.object(update, 'STAMP', '2026-10-16T11:10:00+08:00'):
            self.run_publish()
        self.assertEqual((self.reports / 'latest.json').read_bytes(), before)
        self.assertEqual(len(list((self.reports / 'revisions').glob('*.json'))), 1)
        self.assertFalse(update.load(self.reports / 'update-status.json')['contentChanged'])

    def test_failed_provider_keeps_quotes_dates_and_releases(self):
        result = self.run_publish(failures={'Nasdaq': 'TimeoutError'})
        prior = next(m for m in self.previous['markets'] if m['code'] == 'NASDAQ')
        quote = next(m for m in result['markets'] if m['code'] == 'NASDAQ')
        for k in ('value', 'change', 'asOf', 'sourceIds'):
            self.assertEqual(quote[k], prior[k])
        self.assertIn('采集', quote['status'])
        historical = next(e for e in result['evidenceUpdates'] if e['publisher'] == 'Nasdaq')
        self.assertEqual(historical['checkedAt'], '2026-10-15T18:30:00+08:00')
        for m in result['markets']:
            if m['value'] is None:
                self.assertIsNone(m['change'])

    def test_insufficient_sources_do_not_publish(self):
        before = (self.reports / 'latest.json').read_bytes()
        for successes in ({}, {'中证指数': self.successes['中证指数']}):
            with self.assertRaises(RuntimeError):
                self.run_publish(successes=successes, failures={'Nasdaq': 'TimeoutError'})
            self.assertEqual((self.reports / 'latest.json').read_bytes(), before)
        self.assertFalse((self.reports / 'revisions').exists())

    def test_next_edition_records_no_new_evidence_without_new_research(self):
        previous = self.run_publish()
        with patch.object(update, 'EDITION', 'PM'), patch.object(update, 'STAMP', '2026-10-16T18:30:00+08:00'):
            result = self.run_publish()
        self.assertIn('未发现新的', result['freshness']['reason'])
        self.assertEqual(result['freshness']['researchUpdatedAt'], previous['freshness']['researchUpdatedAt'])
        self.assertEqual(update.load(self.reports / '2026-10-16-AM.json'), previous)
        self.assertEqual(len(update.load(self.reports / 'index.json')['entries']), 2)


if __name__ == '__main__':
    unittest.main()
