import csv
import itertools
from pathlib import Path
import unittest

from src.ai_first.classification import classify

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'skills/setup-ai-first/assets'


class ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ASSETS / 'classification-cases.csv').open() as stream:
            cls.cases = [(tuple(int(row[k]) for k in ('V', 'B', 'C', 'A')), row['tier'])
                         for row in csv.DictReader(stream)]

    def test_fixture_covers_every_combination_once(self):
        self.assertEqual(len(self.cases), 81)
        self.assertEqual({s for s, _ in self.cases}, set(itertools.product(range(3), repeat=4)))

    def test_complete_truth_table(self):
        for scores, expected in self.cases:
            with self.subTest(scores=scores):
                self.assertEqual(classify(*scores, verification_valid=True), expected)

    def test_hard_overrides_always_win(self):
        for scores, _ in self.cases:
            for verified in (False, True):
                with self.subTest(scores=scores, verified=verified):
                    self.assertEqual(classify(*scores, hard_override=True,
                                              verification_valid=verified), 'human-only')

    def test_missing_verification_never_weakens_human_only(self):
        for scores, expected in self.cases:
            with self.subTest(scores=scores):
                self.assertEqual(classify(*scores), 'pair' if expected == 'delegate' else expected)

    def test_bounded_judgment_requires_all_other_delegate_conditions(self):
        cases = [
            ((2, 2, 2, 1), True, False, 'delegate'),
            ((2, 2, 2, 2), True, False, 'delegate'),
            ((2, 2, 2, 0), True, False, 'pair'),
            ((1, 2, 2, 1), True, False, 'pair'),
            ((2, 1, 2, 1), True, False, 'pair'),
            ((2, 0, 2, 1), True, False, 'pair'),
            ((2, 2, 1, 1), True, False, 'pair'),
            ((2, 2, 2, 1), False, False, 'pair'),
            ((2, 2, 2, 1), True, True, 'human-only'),
        ]
        for scores, verified, override, expected in cases:
            with self.subTest(scores=scores, verified=verified, override=override):
                self.assertEqual(classify(*scores, verification_valid=verified,
                                          hard_override=override), expected)

    def test_reclassification_after_prerequisite_is_completed(self):
        # Internal feature: missing acceptance check, then missing conventions,
        # then both available. Minor local implementation choices still remain.
        self.assertEqual(classify(1, 2, 1, 1), 'pair')
        self.assertEqual(classify(2, 2, 1, 1, verification_valid=True), 'pair')
        self.assertEqual(classify(2, 2, 2, 1, verification_valid=True), 'delegate')
        # Completing the same preparation cannot delegate a sensitive surface.
        self.assertEqual(classify(2, 0, 2, 1, verification_valid=True), 'pair')

    def test_invalid_scores_fail_instead_of_getting_a_tier(self):
        for invalid in (-1, 3, True, False, None, '2', 2.0):
            for axis in range(4):
                scores = [2] * 4
                scores[axis] = invalid
                with self.subTest(scores=scores), self.assertRaises(ValueError):
                    classify(*scores, hard_override=True)

    def test_policy_conditions_require_booleans(self):
        for key in ('hard_override', 'verification_valid'):
            for invalid in (None, 'false', 1):
                with self.subTest(key=key, value=invalid), self.assertRaises(ValueError):
                    classify(2, 2, 2, 2, **{key: invalid})

    def test_installed_schema_contains_the_same_table(self):
        schema = (ASSETS / 'ai-first-schema.md').read_text()
        labels = {'human-only': 'H', 'pair': 'P', 'delegate': 'D'}
        for v, b in itertools.product(range(3), repeat=2):
            row = [labels[tier] for scores, tier in self.cases if scores[:2] == (v, b)]
            self.assertIn('| ' + f'{v}{b}' + ' | ' + ' | '.join(row) + ' |', schema)


if __name__ == '__main__':
    unittest.main()
