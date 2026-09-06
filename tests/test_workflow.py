import itertools
import unittest

from src.ai_first.workflow import reclassify, select_mode


class ModeTests(unittest.TestCase):
    def test_normal_brief_routes_to_decomposition(self):
        self.assertEqual(select_mode(kind='brief'), 'decompose')

    def test_existing_task_routes_directly_to_reclassification(self):
        self.assertEqual(select_mode(kind='task'), 'reclassify')
        self.assertEqual(select_mode('reclassify', kind='task'), 'reclassify')

    def test_single_item_is_explicit_with_legacy_alias(self):
        self.assertEqual(select_mode('single-item'), 'single-item')
        self.assertEqual(select_mode('single-task'), 'single-item')
        with self.assertRaises(ValueError):
            select_mode()

    def test_incompatible_mode_does_not_silently_bypass_guards(self):
        for requested, kind in [('single-item', 'brief'), ('single-item', 'task'),
                                ('reclassify', 'brief'), ('decompose', 'task'),
                                ('unknown', None), (None, 'malformed')]:
            with self.subTest(requested=requested, kind=kind), self.assertRaises(ValueError):
                select_mode(requested, kind=kind)


class ReclassificationTests(unittest.TestCase):
    def transition(self, count=0, **kwargs):
        return reclassify(2, 2, 2, 1, bounce=count,
                          failed_cycles=[f'ci:run/{i}/attempt/1' for i in range(count)],
                          verification_valid=True, **kwargs)

    def test_first_failure_counts_once_without_forcing_escalation(self):
        first = self.transition(cycle_id='ci:run/0/attempt/1')
        self.assertEqual((first['tier'], first['bounce'], first['new_failure']), ('delegate', 1, True))
        retry = self.transition(1, cycle_id='ci:run/0/attempt/1')
        self.assertEqual((retry['tier'], retry['bounce'], retry['new_failure']), ('delegate', 1, False))

    def test_second_failure_and_every_later_count_caps_delegation(self):
        for count in (1, 2, 3, 10):
            with self.subTest(count=count):
                result = self.transition(count, cycle_id='ci:new/attempt/1')
                self.assertEqual(result['tier'], 'pair')
                self.assertEqual(result['bounce'], count + 1)
                self.assertTrue(result['escalated'])

    def test_ordinary_reclassification_and_duplicate_do_not_clear_cap(self):
        for cycle in (None, 'ci:run/0/attempt/1'):
            result = self.transition(3, cycle_id=cycle, human_tier='delegate')
            self.assertEqual((result['tier'], result['bounce']), ('pair', 3))
            self.assertFalse(result['new_failure'])
            self.assertTrue(result['escalated'])

    def test_new_attempt_is_a_new_cycle(self):
        result = self.transition(1, cycle_id='ci:run/0/attempt/2')
        self.assertEqual((result['tier'], result['bounce']), ('pair', 2))

    def test_escalation_never_weakens_hard_overrides_for_any_scores(self):
        for scores in itertools.product(range(3), repeat=4):
            with self.subTest(scores=scores):
                result = reclassify(*scores, bounce=1, failed_cycles=['ci:1'],
                                    cycle_id='ci:2', hard_override=True,
                                    verification_valid=True, human_tier='delegate')
                self.assertEqual(result['tier'], 'human-only')

    def test_two_zero_rule_and_stricter_human_tier_survive(self):
        result = reclassify(0, 0, 2, 2, bounce=2, failed_cycles=['ci:1', 'ci:2'],
                            human_tier='delegate')
        self.assertEqual(result['tier'], 'human-only')
        self.assertEqual(self.transition(2, human_tier='human-only')['tier'], 'human-only')
        self.assertEqual(self.transition(human_tier='pair')['tier'], 'pair')

    def test_human_delegate_cannot_bypass_missing_verification(self):
        result = reclassify(2, 2, 2, 2, bounce=0, failed_cycles=[], human_tier='delegate')
        self.assertEqual(result['tier'], 'pair')

    def test_missing_or_conflicting_history_requires_reconciliation(self):
        cases = [(2, []), (1, ['ci:1', 'ci:1']), (-1, []), (True, []),
                 (1, ['bad,cycle']), (0, 'none')]
        for bounce, ledger in cases:
            with self.subTest(bounce=bounce, ledger=ledger), self.assertRaises(ValueError):
                reclassify(2, 2, 2, 2, bounce=bounce, failed_cycles=ledger)
        with self.assertRaises(ValueError):
            self.transition(cycle_id='')

    def test_transition_does_not_mutate_input_history(self):
        ledger = ['ci:1']
        result = reclassify(2, 2, 2, 2, bounce=1, failed_cycles=ledger, cycle_id='ci:2')
        self.assertEqual(ledger, ['ci:1'])
        self.assertEqual(result['failed_cycles'], ['ci:1', 'ci:2'])


if __name__ == '__main__':
    unittest.main()
