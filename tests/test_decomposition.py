from copy import deepcopy
import unittest

from src.ai_first.decomposition import reconcile, select_plan, unit_key, validate_plan


class DecompositionTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(schema='ai-first-decomposition/v1', parent='github:org/repo#1',
                         revision='12345678-1234-4234-8234-123456789abc',
                         brief_digest='sha256:'+'a'*64, units=[])
        for i in range(3):
            self.plan['units'].append(dict(id=f'12345678-1234-4234-8234-123456789ab{i}',
                                          title=f'Unit {i}', body=f'Complete contract {i}',
                                          depends_on=[] if i == 0 else [self.plan['units'][i-1]['id']]))

    def key(self, i=0):
        return unit_key(self.plan['parent'], self.plan['revision'], self.plan['brief_digest'],
                        self.plan['units'][i]['id'])

    def item(self, i=0, **changes):
        value = dict(id=f'github:org/repo#{i+2}', parent=self.plan['parent'],
                     revision=self.plan['revision'], brief_digest=self.plan['brief_digest'],
                     key=self.key(i), title=self.plan['units'][i]['title'],
                     body=self.plan['units'][i]['body'], state='open', linked=False)
        value.update(changes)
        return value

    def resume(self, items=(), intents=None, **changes):
        return reconcile(self.plan, items, {} if intents is None else intents,
                         inventory_complete=True, **changes)

    def test_fresh_plan_creates_each_missing_unit(self):
        self.assertEqual([a['action'] for a in self.resume()], ['create']*3)

    def test_resume_after_partial_creation_reuses_existing_units(self):
        result = self.resume([self.item(0), self.item(1)])
        self.assertEqual([a['action'] for a in result], ['reuse', 'reuse', 'create'])
        self.assertEqual(result[0]['item'], 'github:org/repo#2')

    def test_closed_unlinked_and_human_edited_child_is_not_recreated(self):
        result = self.resume([self.item(state='closed', linked=False, body='Human-edited contract')])
        self.assertEqual(result[0]['action'], 'reuse')
        self.assertTrue(result[0]['content_changed'])

    def test_timeout_with_visible_child_reuses_it(self):
        result = self.resume([self.item()], {self.key(): 'pending'})
        self.assertEqual(result[0]['action'], 'reuse')

    def test_timeout_without_visible_child_blocks_even_with_complete_search(self):
        for state in ('pending', 'created'):
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.resume(intents={self.key(): state})
        result = self.resume(intents={self.key(): 'confirmed-not-created'})
        self.assertEqual(result[0]['action'], 'create')

    def test_duplicate_keys_block_instead_of_choosing_one(self):
        with self.assertRaises(ValueError):
            self.resume([self.item(), self.item(id='github:org/repo#999')])
        self.assertEqual(self.resume([self.item(), self.item()])[0]['action'], 'reuse')

    def test_incomplete_inventory_and_conflicting_intents_block(self):
        with self.assertRaises(ValueError):
            reconcile(self.plan, [], {}, inventory_complete=False)
        with self.assertRaises(ValueError):
            self.resume(intents={self.key(): 'unknown'})

    def test_prior_revision_and_legacy_children_need_disposition(self):
        for changes in ({'key': None}, {'revision': 'older', 'key': 'old-key'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.resume([self.item(**changes)])
        prior = self.item(revision='older', key='old-key')
        result = self.resume([prior], resolved_prior={prior['id']: 'comment:human-disposition'})
        self.assertEqual(result[0]['action'], 'create')
        with self.assertRaises(ValueError):
            self.resume([self.item(parent='wrong-parent')],
                        resolved_prior={prior['id']: 'cannot-suppress-current-key'})

    def test_identical_plan_retries_are_allowed_but_competing_plans_block(self):
        self.assertIsNone(select_plan([]))
        self.assertEqual(select_plan([self.plan, deepcopy(self.plan)]), self.plan)
        other = deepcopy(self.plan)
        other['units'][0]['body'] = 'Different outcome'
        with self.assertRaises(ValueError):
            select_plan([self.plan, other])

    def test_key_stable_across_titles_but_bound_to_revision_digest_and_parent(self):
        original = self.key()
        self.plan['units'][0]['title'] = 'Renamed'
        self.assertEqual(self.key(), original)
        for field, value in [('parent', 'github:org/repo#99'),
                             ('revision', '12345678-1234-4234-8234-123456789abd'),
                             ('brief_digest', 'sha256:'+'b'*64)]:
            before = self.plan[field]
            self.plan[field] = value
            self.assertNotEqual(self.key(), original)
            self.plan[field] = before

    def test_plan_rejects_duplicate_ids_and_invalid_dependencies(self):
        bad = deepcopy(self.plan)
        bad['units'][1]['id'] = bad['units'][0]['id']
        with self.assertRaises(ValueError):
            validate_plan(bad)
        bad = deepcopy(self.plan)
        bad['units'][0]['depends_on'] = [bad['units'][1]['id']]
        with self.assertRaises(ValueError):
            validate_plan(bad)

    def test_completed_run_is_read_only_on_retry(self):
        items = [self.item(i) for i in range(3)]
        before = deepcopy(items)
        result = self.resume(items)
        self.assertTrue(all(a['action'] == 'reuse' for a in result))
        self.assertEqual(items, before)


if __name__ == '__main__':
    unittest.main()
