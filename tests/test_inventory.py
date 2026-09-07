from copy import deepcopy
import unittest

from src.ai_first.inventory import refresh_inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.listing = [dict(id=f'ado:org/project/{i}', revision=1) for i in range(1000)]
        self.fetched = [dict(**entry, item=dict(id=entry['id'], body='original')) for entry in self.listing]

    def refresh(self, **changes):
        values = dict(listing=self.listing, fetched=self.fetched,
                      inventory_complete=True, strong_revisions=True)
        values.update(changes)
        return refresh_inventory(**values)

    def test_large_inventory_reuses_only_bodies_with_unchanged_strong_revisions(self):
        first = self.refresh()
        changed = deepcopy(self.listing)
        changed[7]['revision'] = 2
        pending = self.refresh(listing=changed, fetched=[], cache=first['cache'])
        self.assertFalse(pending['complete'])
        self.assertEqual(pending['fetch_ids'], [changed[7]['id']])
        self.assertEqual(pending['items'], [])
        body = dict(**changed[7], item=dict(id=changed[7]['id'], body='changed'))
        final = self.refresh(listing=changed, fetched=[body], cache=pending['cache'])
        self.assertTrue(final['complete'])
        self.assertEqual(final['fetched_count'], 1)
        self.assertEqual(len(final['items']), 1000)
        self.assertEqual(final['items'][7]['body'], 'changed')

    def test_timestamps_partial_listings_and_revision_conflicts_never_reuse(self):
        initial = self.refresh()
        result = self.refresh(fetched=[], cache=initial['cache'], strong_revisions=False)
        self.assertEqual(len(result['fetch_ids']), 1000)
        with self.assertRaises(ValueError):
            self.refresh(inventory_complete=False)
        changed = deepcopy(self.listing)
        changed[0]['revision'] = 2
        with self.assertRaises(ValueError):
            self.refresh(listing=changed)

    def test_deletions_and_modified_cache_are_detected(self):
        initial = self.refresh()
        result = self.refresh(listing=self.listing[1:], fetched=[], cache=initial['cache'])
        self.assertNotIn(self.listing[0]['id'], result['cache'])
        initial['cache'][self.listing[0]['id']]['item']['body'] = 'edited cache'
        with self.assertRaises(ValueError):
            self.refresh(fetched=[], cache=initial['cache'])


if __name__ == '__main__':
    unittest.main()
