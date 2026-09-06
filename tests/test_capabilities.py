from copy import deepcopy
import unittest

from src.ai_first.capabilities import adjust_scores, promotion_ready


class CapabilityTests(unittest.TestCase):
    def entry(self, **changes):
        value = dict(id='mcp:docs', version='1', effects={'C': 1}, enabled=True,
                     status='proven', applicable=True, approved=True,
                     evidence_current=True, prerequisites_met=True)
        value.update(changes)
        return value

    def trial(self, number, **changes):
        value = dict(capability_id='mcp:docs', version='1', task_id=f'task:{number}',
                     **{'class': 'internal-change'}, completed=True, reviewed=True,
                     supervised=True, used=True, prerequisites_met=True, outcome='pass',
                     execution_tier='pair', baseline_scores=dict(V=2, B=2, C=1, A=1),
                     observed_scores=dict(V=2, B=2, C=2, A=1), axis_evidence={'C': 'artifact:context'},
                     reviewer='human:alice', usage_evidence=['artifact:retrieval'],
                     prerequisite_evidence=['artifact:access'], verification_evidence=['artifact:result'],
                     unplanned_rescue=False)
        value.update(changes)
        return value

    def ready(self, trials, **changes):
        args = dict(capability_id='mcp:docs', version='1', covers=['internal-change'],
                    effects={'C': 1}, trials=trials, history_complete=True)
        args.update(changes)
        return promotion_ready(**args)

    def test_supervised_pair_tasks_can_qualify_without_delegate_label(self):
        self.assertTrue(self.ready([self.trial(i) for i in range(10)]))
        self.assertFalse(self.ready([self.trial(i) for i in range(9)]))

    def test_high_blast_radius_class_can_prove_context_without_raising_b(self):
        trials = [self.trial(i, baseline_scores=dict(V=2, B=0, C=1, A=1),
                             observed_scores=dict(V=2, B=0, C=2, A=1)) for i in range(10)]
        self.assertTrue(self.ready(trials))
        result = adjust_scores(dict(V=2, B=0, C=1, A=1), [self.entry()])
        self.assertEqual(result['scores'], dict(V=2, B=0, C=2, A=1))

    def test_already_maximal_scores_do_not_demonstrate_uplift(self):
        trials = [self.trial(i, baseline_scores=dict(V=2, B=2, C=2, A=1)) for i in range(10)]
        self.assertFalse(self.ready(trials))

    def test_actual_use_review_and_artifacts_are_required(self):
        for changes in ({'used': False}, {'reviewed': False}, {'prerequisites_met': None},
                        {'usage_evidence': []}, {'axis_evidence': {}}, {'unplanned_rescue': True},
                        {'reviewer': ''}, {'supervised': False}):
            trials = [self.trial(i) for i in range(10)]
            trials[-1].update(changes)
            with self.subTest(changes=changes):
                self.assertFalse(self.ready(trials))

    def test_failures_and_inconclusive_results_cannot_be_cherry_picked(self):
        trials = [self.trial(i) for i in range(10)]
        for outcome in ('fail', 'inconclusive'):
            self.assertFalse(self.ready(trials + [self.trial(10, outcome=outcome)]))
        self.assertFalse(self.ready(trials, history_complete=False))

    def test_retries_on_one_task_do_not_inflate_sample_size(self):
        self.assertFalse(self.ready([self.trial(1) for _ in range(10)]))
        trials = [self.trial(i) for i in range(10)]
        self.assertFalse(self.ready(trials + [self.trial(1, outcome='fail')]))

    def test_exact_version_and_each_class_and_effect_need_evidence(self):
        trials = [self.trial(i) for i in range(10)]
        self.assertFalse(self.ready(trials, version='2'))
        self.assertFalse(self.ready(trials, covers=['internal-change', 'other-class']))
        self.assertFalse(self.ready(trials, effects={'C': 1, 'A': 1}))
        self.assertFalse(self.ready(trials, effects={'B': 1}))

    def test_unclaimed_changes_make_trial_inconclusive(self):
        trials = [self.trial(i, observed_scores=dict(V=2, B=2, C=2, A=2)) for i in range(10)]
        self.assertFalse(self.ready(trials))

    def test_provisional_and_unavailable_capabilities_never_change_scores(self):
        raw = dict(V=2, B=2, C=1, A=1)
        for changes in ({'status': 'provisional'}, {'prerequisites_met': None},
                        {'enabled': False}, {'evidence_current': False},
                        {'approved': False}, {'applicable': False}):
            with self.subTest(changes=changes):
                self.assertEqual(adjust_scores(raw, [self.entry(**changes)])['scores'], raw)

    def test_zero_effect_does_not_raise_an_axis(self):
        result = adjust_scores(dict(V=1, B=2, C=1, A=1),
                               [self.entry(effects={'V': 0, 'C': 1})])
        self.assertEqual(result['scores'], dict(V=1, B=2, C=2, A=1))

    def test_audit_records_actual_delta_with_caps_and_no_b_effect(self):
        raw = dict(V=2, B=0, C=0, A=2)
        entries = [self.entry(effects={'V': 1, 'C': 1, 'A': 1}), self.entry(id='mcp:other'),
                   self.entry(id='bad', effects={'B': 1})]
        before = deepcopy(raw)
        result = adjust_scores(raw, entries)
        self.assertEqual(result['scores'], dict(V=2, B=0, C=1, A=2))
        self.assertEqual(result['capability_deltas'], dict(V=0, B=0, C=1, A=0))
        self.assertEqual(result['applied'], [dict(id='mcp:docs', version='1', deltas={'C': 1})])
        self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
