from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.evaluate_workflow import grade


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.corpus = json.loads((Path(__file__).resolve().parents[1] /
                                 'evaluations/workflow-cases.json').read_text(encoding='utf-8'))
        self.predictions = dict(mode='test-fixture-only', evaluator='test', results=[
            dict(id=case['id'], **case['expected']) for case in self.corpus['cases']])

    def test_grader_counts_missing_and_unsafe_answers_in_denominator(self):
        changed = deepcopy(self.predictions)
        changed['results'].pop()
        changed['results'][4]['tier'] = 'delegate'
        result = grade(self.corpus, changed)
        self.assertEqual(result['total'], 10)
        self.assertEqual(result['exact_matches'], 8)
        self.assertEqual(result['unsafe_delegations'], ['public-contract'])
        self.assertEqual(len(result['failures']), 2)
        self.assertIsNone(result['median_human_review_seconds'])

    def test_grader_rejects_duplicate_unknown_ids_and_invented_negative_duration(self):
        for change in ('duplicate', 'unknown', 'duration'):
            changed = deepcopy(self.predictions)
            if change == 'duplicate':
                changed['results'].append(changed['results'][0])
            elif change == 'unknown':
                changed['results'][0]['id'] = 'not-a-case'
            else:
                changed['results'][0]['duration_seconds'] = -1
            with self.subTest(change=change), self.assertRaises(ValueError):
                grade(self.corpus, changed)


if __name__ == '__main__':
    unittest.main()
