import unittest

from src.ai_first.payloads import preflight_payload


class PayloadPreflightTests(unittest.TestCase):
    def test_reports_utf8_bytes_and_accepts_clean_payload(self):
        result = preflight_payload('Ready café', max_bytes=20)
        self.assertTrue(result['ready'])
        self.assertEqual(result['utf8_bytes'], len('Ready café'.encode('utf-8')))
        self.assertEqual(result['issues'], [])

    def test_rejects_unresolved_markers_before_remote_write(self):
        result = preflight_payload('units: PLACEHOLDER')
        self.assertFalse(result['ready'])
        self.assertEqual(result['matched_forbidden'], ['PLACEHOLDER'])

    def test_rejects_declared_byte_limit_violation(self):
        result = preflight_payload('éé', forbidden=[], max_bytes=3)
        self.assertFalse(result['ready'])
        self.assertTrue(result['over_limit'])
        self.assertIn('4 UTF-8 bytes', result['issues'][0])

    def test_rejects_ambiguous_configuration(self):
        for kwargs in ({'payload': ''}, {'payload': 'ok', 'forbidden': 'PLACEHOLDER'},
                       {'payload': 'ok', 'max_bytes': True}, {'payload': 'ok', 'max_bytes': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                preflight_payload(**kwargs)


if __name__ == '__main__':
    unittest.main()
