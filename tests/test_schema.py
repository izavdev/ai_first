from pathlib import Path
import unittest

from src.ai_first.schema import CONTRACT, decode, encode, validate

FIXTURES = Path(__file__).parent / 'fixtures/schema'


class SchemaTests(unittest.TestCase):
    def task(self):
        return (FIXTURES / 'github-task.md').read_text()

    def test_tracker_fixtures_round_trip_with_human_text(self):
        for tracker in ('github', 'ado', 'linear'):
            text = (FIXTURES / f'{tracker}-task.md').read_text()
            with self.subTest(tracker=tracker):
                human, fields = decode(text, tracker, labels=['ai-delegate', 'unrelated'])
                self.assertEqual(human, 'Task summary: café\n\nAcceptance: approved output.')
                self.assertEqual(encode(human, fields, tracker), text)

    def test_brief_fixture_and_required_fields(self):
        text = (FIXTURES / 'github-brief.md').read_text()
        human, fields = decode(text)
        self.assertEqual(encode(human, fields), text)
        for key in CONTRACT['brief']:
            missing = dict(fields)
            missing.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(missing)

    def test_unknown_fields_survive_but_duplicates_are_rejected(self):
        text = self.task().replace('kind: task', 'kind: task\nfuture-field: some: value')
        human, fields = decode(text)
        self.assertEqual(fields['future-field'], 'some: value')
        self.assertEqual(encode(human, fields), text)
        for line in ('kind: task', 'future-field: again'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                decode(text.replace('kind: task', 'kind: task\n'+line))

    def test_last_malformed_candidate_never_falls_back(self):
        with self.assertRaises(ValueError):
            decode(self.task()+'\n---\n[ai-first:v1]\nkind: task\n')

    def test_fences_and_adapter_delimiters_are_enforced(self):
        for text in (self.task().removesuffix('```\n'), self.task().replace('---\n```', '```')):
            with self.assertRaises(ValueError):
                decode(text)
        with self.assertRaises(ValueError):
            decode(self.task(), 'linear')
        bare = self.task().replace('```\n', '')
        self.assertEqual(decode(bare)[1]['kind'], 'task')

    def test_line_endings_and_ignored_suffix(self):
        expected = decode(self.task())
        self.assertEqual(decode(self.task().replace('\n', '\r\n')), expected)
        self.assertEqual(decode(self.task()+'Ignored footer'), expected)

    def test_invalid_numbers_ledgers_and_score_deltas_fail(self):
        replacements = [('bounce: 0', 'bounce: true'), ('bounce: 0', 'bounce: -1'),
                        ('bounce: 0', 'bounce: 1'), ('V0 B0 C0 A0', 'V0 B1 C0 A0'),
                        ('raw-scores: V2 B2 C2 A1', 'raw-scores: V2 B2 C1 A1')]
        for old, new in replacements:
            with self.subTest(new=new), self.assertRaises(ValueError):
                decode(self.task().replace(old, new))

    def test_labels_tier_caps_and_conditional_fields(self):
        with self.assertRaises(ValueError):
            decode(self.task(), labels=['ai-pair'])
        with self.assertRaises(ValueError):
            decode(self.task(), labels=['ai-pair', 'ai-delegate'])
        _, fields = decode(self.task())
        for key in ('verify', 'stop-ask', 'profile'):
            missing = dict(fields)
            missing.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(missing)
        fields.update(bounce='2', **{'failed-cycles': 'ci:1, ci:2'})
        with self.assertRaises(ValueError):
            validate(fields)
        fields['tier'] = 'pair'
        self.assertEqual(validate(fields, ['ai-pair', 'ai-escalated'])['tier'], 'pair')

    def test_partial_provenance_is_not_accepted(self):
        with self.assertRaises(ValueError):
            decode(self.task().replace('kind: task', 'kind: task\ndecomposition-parent: github:org/repo#1'))

    def test_human_only_omits_profile(self):
        _, fields = decode(self.task())
        fields['tier'] = 'human-only'
        with self.assertRaises(ValueError):
            validate(fields)
        fields.pop('profile')
        self.assertEqual(validate(fields)['tier'], 'human-only')


if __name__ == '__main__':
    unittest.main()
