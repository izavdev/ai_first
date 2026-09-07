from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.ai_first.adapters import check_adapter, normalize_history, tag_patch

FIXTURES = Path(__file__).parent / 'fixtures/adapters'


class AdapterTests(unittest.TestCase):
    def fixture(self, tracker):
        return json.loads((FIXTURES / f'{tracker}.json').read_text(encoding='utf-8'))

    def test_synthetic_api_pages_preserve_authorship_edits_and_creation_order(self):
        for tracker in ('github', 'ado', 'linear'):
            with self.subTest(tracker=tracker):
                result = normalize_history(**self.fixture(tracker))
                self.assertEqual([row['body'] for row in result], ['original', 'edited'])
                self.assertTrue(all(row['human'] for row in result))
                self.assertEqual([row['edited'] for row in result], [False, True])

    def test_missing_reordered_and_looping_pages_block(self):
        for tracker in ('github', 'ado', 'linear'):
            value = self.fixture(tracker)
            with self.subTest(tracker=tracker), self.assertRaises(ValueError):
                normalize_history(**dict(value, pages=value['pages'][:1]))
            with self.assertRaises(ValueError):
                normalize_history(**dict(value, pages=list(reversed(value['pages']))))

    def test_account_presence_does_not_prove_human_identity(self):
        value = self.fixture('github')
        self.assertTrue(all(not row['human'] for row in normalize_history(**dict(value, human_ids=[]))))
        value['pages'][0]['data'][0]['user']['type'] = 'Bot'
        self.assertFalse(normalize_history(**value)[0]['human'])

    def test_conflicting_duplicate_comments_and_missing_metadata_block(self):
        value = self.fixture('github')
        value['pages'][1]['data'][0]['id'] = value['pages'][0]['data'][0]['id']
        with self.assertRaises(ValueError):
            normalize_history(**value)
        value = self.fixture('github')
        del value['pages'][0]['data'][0]['updated_at']
        with self.assertRaises(KeyError):
            normalize_history(**value)

    def test_tag_removal_preserves_unrelated_tags_and_binds_revision(self):
        patch = tag_patch(12, 'customer; ai-pair; urgent', add=['ai-delegate'], remove=['ai-pair'])
        self.assertEqual(patch[0], dict(op='test', path='/rev', value=12))
        self.assertEqual(patch[1]['value'], 'customer; urgent; ai-delegate')
        self.assertEqual(patch[1]['op'], 'replace')
        with self.assertRaises(ValueError):
            tag_patch(12, 'customer', add=['x'], remove=['X'])

    def test_preflight_requires_actual_evidence_for_every_operation(self):
        contract = json.loads((Path(__file__).resolve().parents[1] /
                              'skills/setup-ai-first/assets/adapter-contract.json').read_text())
        value = dict(tracker='github', server=dict(name='synthetic-contract-fixture', version='1'),
                     concurrency='serialized', checks={name: dict(supported=True, evidence='fixture:observed')
                                                         for name in contract['required']})
        self.assertTrue(check_adapter(value)['ready'])
        for name in contract['required']:
            changed = deepcopy(value)
            changed['checks'][name]['supported'] = False
            self.assertIn(name, check_adapter(changed)['missing'])
        value['server']['version'] = ''
        with self.assertRaises(ValueError):
            check_adapter(value)


if __name__ == '__main__':
    unittest.main()
