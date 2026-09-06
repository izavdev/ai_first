import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'integrations/pr-verification/verify.py'


class VerificationRunnerTests(unittest.TestCase):
    def run_config(self, config):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'verification.json'
            path.write_text(json.dumps(config))
            return subprocess.run([sys.executable, str(RUNNER), '--config', str(path)],
                                  cwd=ROOT, text=True, capture_output=True)

    def test_success_reports_actual_checkout(self):
        result = self.run_config({'argv': [sys.executable, '-c', 'print("acceptance output")'],
                                  'timeout_seconds': 10})
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        self.assertEqual(result.returncode, 0)
        self.assertIn('acceptance output', result.stdout)
        self.assertIn('PASS', result.stdout)
        self.assertIn('commit='+sha, result.stdout)

    def test_failure_stays_failed(self):
        result = self.run_config({'argv': [sys.executable, '-c', 'raise SystemExit(7)'],
                                  'timeout_seconds': 10})
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL command_exit=7', result.stdout)

    def test_empty_example_fails_until_configured(self):
        example = json.loads((RUNNER.parent / 'verification.example.json').read_text())
        self.assertEqual(self.run_config(example).returncode, 2)

    def test_invalid_and_unavailable_commands_fail(self):
        cases = [{'argv': 'echo passed', 'timeout_seconds': 10},
                 {'argv': ['echo'], 'timeout_seconds': True},
                 {'argv': ['echo'], 'timeout_seconds': 1501},
                 {'argv': ['ai-first-nonexistent-command'], 'timeout_seconds': 10}]
        for config in cases:
            with self.subTest(config=config):
                self.assertEqual(self.run_config(config).returncode, 2)

    def test_arguments_are_not_shell_interpreted(self):
        literal = '$(touch /tmp/ai-first-should-not-exist); echo nope'
        result = self.run_config({'argv': [sys.executable, '-c',
                                          'import sys; print(sys.argv[1])', literal],
                                  'timeout_seconds': 10})
        self.assertEqual(result.returncode, 0)
        self.assertIn(literal, result.stdout)

    def test_timeout_is_failure(self):
        result = self.run_config({'argv': [sys.executable, '-c', 'import time; time.sleep(5)'],
                                  'timeout_seconds': 1})
        self.assertEqual(result.returncode, 124)
        self.assertIn('TIMEOUT', result.stdout)


if __name__ == '__main__':
    unittest.main()
